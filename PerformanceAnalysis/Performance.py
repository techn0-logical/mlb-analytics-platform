#!/usr/bin/env python3
"""
PREDICTION PERFORMANCE ANALYZER
==============================

Analyzes MLB betting predictions against actual game results and populates
the performance tracking tables for comprehensive model evaluation.

Features:
- Retrieves predictions from daily_predictions table
- Gets actual game results from games table
- Calculates accuracy metrics across different dimensions
- Populates all 4 performance tracking tables
- Supports historical and daily analysis

Author: MLB Analytics Performance Team
Version: v1.0
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class PredictionPerformanceAnalyzer:
    """Analyzes prediction performance and updates tracking tables"""
    
    def __init__(self):
        """Initialize with database connection"""
        load_dotenv('secrets.env')
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment")
        
        self.engine = create_engine(database_url)
        print("✅ Connected to database for performance analysis")
    
    def get_predictions_for_date(self, analysis_date):
        """Get all predictions for a specific date"""
        with self.engine.connect() as conn:
            query = text("""
                SELECT 
                    game_pk, away_team, home_team, predicted_winner,
                    confidence, betting_recommendation, is_betting_opportunity,
                    data_quality, h2h_sample_size, model_version,
                    prediction_timestamp
                FROM daily_predictions 
                WHERE prediction_date = :date
                ORDER BY game_pk;
            """)
            
            result = conn.execute(query, {'date': analysis_date}).fetchall()
            print(f"📊 Found {len(result)} predictions for {analysis_date}")
            return result
    
    def get_actual_results_for_date(self, analysis_date):
        """Get actual game results for a specific date"""
        with self.engine.connect() as conn:
            query = text("""
                SELECT 
                    game_pk, away_team_id, home_team_id, 
                    away_score, home_score, game_status,
                    CASE 
                        WHEN away_score > home_score THEN away_team_id
                        WHEN home_score > away_score THEN home_team_id
                        ELSE NULL 
                    END as actual_winner
                FROM games 
                WHERE game_date = :date 
                AND game_status = 'completed'
                AND away_score IS NOT NULL 
                AND home_score IS NOT NULL
                ORDER BY game_pk;
            """)
            
            result = conn.execute(query, {'date': analysis_date}).fetchall()
            print(f"🏟️  Found {len(result)} completed games for {analysis_date}")
            return result
    
    def match_predictions_with_results(self, predictions, results):
        """Match predictions with actual game results"""
        results_dict = {result.game_pk: result for result in results}
        matched_data = []
        
        for pred in predictions:
            game_pk = pred.game_pk
            if game_pk in results_dict:
                result = results_dict[game_pk]
                
                # Determine if prediction was correct
                is_correct = pred.predicted_winner == result.actual_winner
                
                matched_data.append({
                    'game_pk': game_pk,
                    'away_team': pred.away_team,
                    'home_team': pred.home_team,
                    'predicted_winner': pred.predicted_winner,
                    'actual_winner': result.actual_winner,
                    'confidence': pred.confidence,
                    'betting_recommendation': pred.betting_recommendation,
                    'is_betting_opportunity': pred.is_betting_opportunity,
                    'is_correct': is_correct,
                    'away_score': result.away_score,
                    'home_score': result.home_score,
                    'final_score': f"{result.away_score}-{result.home_score}",
                    'model_version': pred.model_version,
                    'h2h_sample_size': pred.h2h_sample_size,
                    'data_quality': pred.data_quality
                })
        
        print(f"🔗 Matched {len(matched_data)} predictions with results")
        return matched_data
    
    def calculate_overall_performance(self, matched_data, analysis_date):
        """Calculate overall prediction performance"""
        if not matched_data:
            print("❌ No matched data for overall performance calculation")
            return None
        
        total_games = len(matched_data)
        correct_predictions = sum(1 for game in matched_data if game['is_correct'])
        overall_accuracy = round((correct_predictions / total_games) * 100, 2)
        expected_accuracy = 51.9  # Model's expected accuracy
        performance_vs_expected = round(overall_accuracy - expected_accuracy, 2)
        
        model_version = matched_data[0]['model_version']
        
        performance_data = {
            'date': analysis_date,
            'model_version': model_version,
            'total_games': total_games,
            'correct_predictions': correct_predictions,
            'overall_accuracy': overall_accuracy,
            'expected_accuracy': expected_accuracy,
            'performance_vs_expected': performance_vs_expected
        }
        
        print(f"📈 Overall performance: {correct_predictions}/{total_games} = {overall_accuracy}% (vs {expected_accuracy}% expected)")
        return performance_data
    
    def calculate_confidence_performance(self, matched_data, analysis_date):
        """Calculate performance by confidence level ranges"""
        if not matched_data:
            return []
        
        confidence_ranges = {
            '50-60%': (50.0, 60.0),
            '60-70%': (60.0, 70.0),
            '70-80%': (70.0, 80.0),
            '80-90%': (80.0, 90.0),
            '90%+': (90.0, 100.0)
        }
        
        confidence_performance = []
        model_version = matched_data[0]['model_version']
        
        for range_name, (min_conf, max_conf) in confidence_ranges.items():
            # Filter games in this confidence range
            range_games = [
                game for game in matched_data 
                if min_conf <= game['confidence'] < max_conf or (range_name == '90%+' and game['confidence'] >= min_conf)
            ]
            
            if range_games:
                total_games = len(range_games)
                correct_predictions = sum(1 for game in range_games if game['is_correct'])
                accuracy = round((correct_predictions / total_games) * 100, 2)
                
                confidences = [game['confidence'] for game in range_games]
                avg_confidence = round(sum(confidences) / len(confidences), 2)
                min_confidence = round(min(confidences), 2)
                max_confidence = round(max(confidences), 2)
                
                confidence_performance.append({
                    'date': analysis_date,
                    'model_version': model_version,
                    'confidence_range': range_name,
                    'total_games': total_games,
                    'correct_predictions': correct_predictions,
                    'accuracy': accuracy,
                    'avg_confidence': avg_confidence,
                    'min_confidence': min_confidence,
                    'max_confidence': max_confidence
                })
                
                print(f"   📊 {range_name}: {correct_predictions}/{total_games} = {accuracy}% (avg: {avg_confidence}%)")
        
        return confidence_performance
    
    def calculate_betting_performance(self, matched_data, analysis_date):
        """Calculate performance by betting recommendation type"""
        if not matched_data:
            return []
        
        bet_types = ['STRONG', 'MODERATE', 'WEAK', 'AVOID']
        betting_performance = []
        model_version = matched_data[0]['model_version']
        
        for bet_type in bet_types:
            # Filter games with this betting recommendation
            type_games = [game for game in matched_data if game['betting_recommendation'] == bet_type]
            
            if type_games:
                total_bets = len(type_games)
                correct_bets = sum(1 for game in type_games if game['is_correct'])
                accuracy = round((correct_bets / total_bets) * 100, 2)
                
                confidences = [game['confidence'] for game in type_games]
                avg_confidence = round(sum(confidences) / len(confidences), 2)
                
                is_betting_opportunity = bet_type in ['STRONG', 'MODERATE']
                
                betting_performance.append({
                    'date': analysis_date,
                    'model_version': model_version,
                    'bet_type': bet_type,
                    'total_bets': total_bets,
                    'correct_bets': correct_bets,
                    'accuracy': accuracy,
                    'avg_confidence': avg_confidence,
                    'is_betting_opportunity': is_betting_opportunity,
                    'profit_loss': 0  # Future ROI calculation
                })
                
                bet_emoji = '🎯' if is_betting_opportunity else '📊'
                print(f"   {bet_emoji} {bet_type}: {correct_bets}/{total_bets} = {accuracy}% (avg: {avg_confidence}%)")
        
        return betting_performance
    
    def save_performance_to_database(self, overall_perf, confidence_perf, betting_perf, game_results, analysis_date):
        """Save all performance data to database tables"""
        with self.engine.connect() as conn:
            try:
                print(f"\n💾 Saving performance data to database...")
                
                # 1. Save overall performance
                if overall_perf:
                    conn.execute(text("""
                        INSERT INTO prediction_performance 
                        (date, model_version, total_games, correct_predictions, overall_accuracy, 
                         expected_accuracy, performance_vs_expected)
                        VALUES 
                        (:date, :model_version, :total_games, :correct_predictions, :overall_accuracy,
                         :expected_accuracy, :performance_vs_expected)
                        ON CONFLICT (date, model_version) DO UPDATE SET
                            total_games = EXCLUDED.total_games,
                            correct_predictions = EXCLUDED.correct_predictions,
                            overall_accuracy = EXCLUDED.overall_accuracy,
                            expected_accuracy = EXCLUDED.expected_accuracy,
                            performance_vs_expected = EXCLUDED.performance_vs_expected,
                            updated_at = CURRENT_TIMESTAMP;
                    """), overall_perf)
                    print(f"   ✅ Overall performance saved")
                
                # 2. Save confidence level performance
                if confidence_perf:
                    for conf_data in confidence_perf:
                        conn.execute(text("""
                            INSERT INTO confidence_level_performance 
                            (date, model_version, confidence_range, total_games, correct_predictions,
                             accuracy, avg_confidence, min_confidence, max_confidence)
                            VALUES 
                            (:date, :model_version, :confidence_range, :total_games, :correct_predictions,
                             :accuracy, :avg_confidence, :min_confidence, :max_confidence)
                            ON CONFLICT (date, model_version, confidence_range) DO UPDATE SET
                                total_games = EXCLUDED.total_games,
                                correct_predictions = EXCLUDED.correct_predictions,
                                accuracy = EXCLUDED.accuracy,
                                avg_confidence = EXCLUDED.avg_confidence,
                                min_confidence = EXCLUDED.min_confidence,
                                max_confidence = EXCLUDED.max_confidence;
                        """), conf_data)
                    print(f"   ✅ Confidence performance saved ({len(confidence_perf)} ranges)")
                
                # 3. Save betting performance
                if betting_perf:
                    for bet_data in betting_perf:
                        conn.execute(text("""
                            INSERT INTO betting_performance 
                            (date, model_version, bet_type, total_bets, correct_bets,
                             accuracy, avg_confidence, is_betting_opportunity, profit_loss)
                            VALUES 
                            (:date, :model_version, :bet_type, :total_bets, :correct_bets,
                             :accuracy, :avg_confidence, :is_betting_opportunity, :profit_loss)
                            ON CONFLICT (date, model_version, bet_type) DO UPDATE SET
                                total_bets = EXCLUDED.total_bets,
                                correct_bets = EXCLUDED.correct_bets,
                                accuracy = EXCLUDED.accuracy,
                                avg_confidence = EXCLUDED.avg_confidence,
                                is_betting_opportunity = EXCLUDED.is_betting_opportunity,
                                profit_loss = EXCLUDED.profit_loss;
                        """), bet_data)
                    print(f"   ✅ Betting performance saved ({len(betting_perf)} types)")
                
                # 4. Save individual game results
                if game_results:
                    for game_data in game_results:
                        game_record = {
                            'date': analysis_date,
                            **game_data
                        }
                        conn.execute(text("""
                            INSERT INTO game_prediction_results 
                            (date, game_pk, away_team, home_team, predicted_winner, actual_winner,
                             confidence, betting_recommendation, is_betting_opportunity, is_correct,
                             final_score, away_score, home_score, model_version, h2h_sample_size, data_quality)
                            VALUES 
                            (:date, :game_pk, :away_team, :home_team, :predicted_winner, :actual_winner,
                             :confidence, :betting_recommendation, :is_betting_opportunity, :is_correct,
                             :final_score, :away_score, :home_score, :model_version, :h2h_sample_size, :data_quality)
                            ON CONFLICT (date, game_pk, model_version) DO UPDATE SET
                                actual_winner = EXCLUDED.actual_winner,
                                is_correct = EXCLUDED.is_correct,
                                final_score = EXCLUDED.final_score,
                                away_score = EXCLUDED.away_score,
                                home_score = EXCLUDED.home_score;
                        """), game_record)
                    print(f"   ✅ Game results saved ({len(game_results)} games)")
                
                conn.commit()
                print(f"✅ All performance data committed to database")
                return True
                
            except Exception as e:
                print(f"❌ Error saving performance data: {e}")
                conn.rollback()
                return False
    
    def analyze_date(self, analysis_date):
        """Run complete performance analysis for a specific date"""
        print(f"\n🔍 ANALYZING PREDICTIONS FOR {analysis_date}")
        print("=" * 50)
        
        # Get predictions and results
        predictions = self.get_predictions_for_date(analysis_date)
        if not predictions:
            print(f"📭 No predictions found for {analysis_date}")
            return False
        
        results = self.get_actual_results_for_date(analysis_date)
        if not results:
            print(f"⏳ No completed games found for {analysis_date} - results may not be final yet")
            return False
        
        # Match predictions with results
        matched_data = self.match_predictions_with_results(predictions, results)
        if not matched_data:
            print(f"🔗 No matching predictions and results for {analysis_date}")
            return False
        
        # Calculate performance metrics
        print(f"\n📊 CALCULATING PERFORMANCE METRICS")
        print("-" * 40)
        
        overall_perf = self.calculate_overall_performance(matched_data, analysis_date)
        
        print(f"\n📈 Confidence Level Breakdown:")
        confidence_perf = self.calculate_confidence_performance(matched_data, analysis_date)
        
        print(f"\n🎯 Betting Recommendation Breakdown:")
        betting_perf = self.calculate_betting_performance(matched_data, analysis_date)
        
        # Save to database
        success = self.save_performance_to_database(
            overall_perf, confidence_perf, betting_perf, matched_data, analysis_date
        )
        
        if success:
            print(f"\n✅ Performance analysis completed for {analysis_date}")
            self.show_summary(overall_perf, confidence_perf, betting_perf)
        else:
            print(f"\n❌ Performance analysis failed for {analysis_date}")
        
        return success
    
    def show_summary(self, overall_perf, confidence_perf, betting_perf):
        """Show performance analysis summary"""
        print(f"\n📋 PERFORMANCE SUMMARY")
        print("=" * 25)
        
        if overall_perf:
            print(f"📊 Overall: {overall_perf['correct_predictions']}/{overall_perf['total_games']} = {overall_perf['overall_accuracy']}%")
            print(f"📈 vs Expected: {overall_perf['performance_vs_expected']:+.1f}%")
        
        if confidence_perf:
            print(f"\n🎯 Top Confidence Ranges:")
            sorted_conf = sorted(confidence_perf, key=lambda x: x['accuracy'], reverse=True)[:3]
            for conf in sorted_conf:
                print(f"   {conf['confidence_range']}: {conf['accuracy']}% ({conf['total_games']} games)")
        
        if betting_perf:
            print(f"\n💰 Betting Performance:")
            betting_ops = [bet for bet in betting_perf if bet['is_betting_opportunity']]
            for bet in betting_ops:
                print(f"   {bet['bet_type']}: {bet['accuracy']}% ({bet['total_bets']} games)")
    
    def analyze_recent_days(self, days=7):
        """Analyze performance for the last N days"""
        print(f"\n🔍 ANALYZING LAST {days} DAYS OF PREDICTIONS")
        print("=" * 50)
        
        success_count = 0
        today = date.today()
        
        for i in range(days):
            analysis_date = today - timedelta(days=i)
            print(f"\n📅 Date: {analysis_date}")
            
            if self.analyze_date(analysis_date):
                success_count += 1
        
        print(f"\n📊 BULK ANALYSIS COMPLETE")
        print(f"✅ Successfully analyzed {success_count}/{days} days")
        return success_count

def main():
    """Main performance analysis workflow"""
    print("📊 PREDICTION PERFORMANCE ANALYZER")
    print("=" * 40)
    print("Analyzes predictions vs actual results")
    print("Populates performance tracking tables")
    print("=" * 40)
    
    try:
        analyzer = PredictionPerformanceAnalyzer()
        
        # Analyze today's predictions since we have completed games
        today_analysis = date.today()
        
        print(f"\n🎯 Analyzing predictions for {today_analysis}")
        print("(Today's games with completed results)")
        
        success = analyzer.analyze_date(today_analysis)
        
        if success:
            print(f"\n🎉 Performance analysis complete!")
            print("✅ All tracking tables updated")
            print("📊 Ready for trend analysis queries")
        else:
            print(f"\n⚠️  Analysis incomplete - check if games have finished")
            print("💡 Try running again later when all results are final")
        
        # Optional: analyze recent days
        print(f"\n❓ Want to analyze more days? Uncomment the line below:")
        print(analyzer.analyze_recent_days(7))
        
    except KeyboardInterrupt:
        print(f"\n👋 Performance analysis cancelled")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()