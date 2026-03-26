"""
Main collection orchestrator - simple and clean
"""
import logging
import sys
import os
from datetime import date
from typing import List, Dict

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import functions
try:
    from .utils import get_collection_dates, is_mlb_season, log_error
    from .games import collect_games
    from .transactions import collect_transactions  
    from .weather import collect_weather
    from .player_stats import collect_all_player_stats, collect_daily_player_status
    from .roster_collection import validate_all_teams_data
except ImportError:
    # Fallback for command line usage
    from DataCollection.utils import get_collection_dates, is_mlb_season, log_error
    from DataCollection.games import collect_games
    from DataCollection.transactions import collect_transactions  
    from DataCollection.weather import collect_weather
    from DataCollection.player_stats import collect_all_player_stats, collect_daily_player_status
    from DataCollection.roster_collection import validate_all_teams_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_daily_collection() -> Dict:
    """
    Run the COMPREHENSIVE daily collection
    Collects ALL available MLB data for maximum analytics coverage:
    - Games (yesterday scores, today status, tomorrow schedule) 
    - Transactions (trades, signings, IL moves)
    - Weather (game conditions and forecasts)
    - Player Statistics (current season batting/pitching)
    - Daily Player Status (roster, injury, availability)
    - Roster Management (team validation and consistency)
    """
    logger.info("🌅 Starting COMPREHENSIVE daily MLB data collection")
    
    # Get dates
    yesterday, today, tomorrow = get_collection_dates()
    dates = [yesterday, today, tomorrow]
    
    # Filter for MLB season dates only
    active_dates = [d for d in dates if is_mlb_season(d)]
    
    if not active_dates:
        logger.info("🚫 No collection needed - outside MLB season")
        return {'overall_success': True, 'message': 'Off-season'}
    
    logger.info(f"📅 Collecting COMPREHENSIVE data for {len(active_dates)} dates in season")
    
    # Run collections
    results = []
    overall_success = True
    
    try:
        # Core Game Data (highest priority)
        logger.info("🏟️ Collecting game data (scores, schedules, status)")
        games_result = collect_games(active_dates)
        results.append(games_result)
        
        # Transaction Data (roster changes)
        logger.info("🔄 Collecting transaction data (trades, signings, IL moves)")
        trans_result = collect_transactions(active_dates)
        results.append(trans_result)
        
        # Weather Data (game conditions) - temporarily disabled due to API timeout
        logger.info("🌤️ Collecting weather data (conditions, forecasts)")
        weather_result = collect_weather(active_dates)
        results.append(weather_result)
        
        # Player Statistics (current season performance)
        logger.info("📊 Collecting current season player statistics")
        player_stats_result = collect_all_player_stats()
        results.append(player_stats_result)
        
        # Daily Player Status (availability, roster status, injuries)
        if today in active_dates:
            logger.info("👥 Collecting daily player status (roster, injuries, availability)")
            player_status_result = collect_daily_player_status(today)
            results.append(player_status_result)
        
        # Team and Roster Management (data validation and consistency)
        logger.info("🏟️ Validating team data and roster consistency")
        try:
            team_validation_result = validate_all_teams_data()
            results.append(team_validation_result)
        except Exception as e:
            log_error("Team Validation", f"Team validation failed (non-critical): {e}")
            # Don't fail entire collection for team validation issues
        
    except Exception as e:
        log_error("Daily Collection", f"Collection failed: {e}")
        overall_success = False
    
    # Summary
    total_changes = sum(r.get('inserted', 0) + r.get('updated', 0) for r in results if isinstance(r, dict))
    
    logger.info(f"📊 COMPREHENSIVE daily collection complete: {total_changes} total changes")
    
    return {
        'overall_success': overall_success,
        'total_changes': total_changes,
        'results': results,
        'dates_processed': len(active_dates),
        'collection_type': 'comprehensive'
    }

def run_lightweight_collection() -> Dict:
    """
    Run the original lightweight daily collection (backward compatibility)
    Collects only: games, transactions, weather, and daily player status
    """
    logger.info("🌅 Starting lightweight daily MLB data collection")
    
    # Get dates
    yesterday, today, tomorrow = get_collection_dates()
    dates = [yesterday, today, tomorrow]
    
    # Filter for MLB season dates only
    active_dates = [d for d in dates if is_mlb_season(d)]
    
    if not active_dates:
        logger.info("🚫 No collection needed - outside MLB season")
        return {'overall_success': True, 'message': 'Off-season'}
    
    logger.info(f"📅 Collecting lightweight data for {len(active_dates)} dates in season")
    
    # Run collections
    results = []
    overall_success = True
    
    try:
        # Games (most important)
        games_result = collect_games(active_dates)
        results.append(games_result)
        
        # Transactions
        trans_result = collect_transactions(active_dates)
        results.append(trans_result)
        
        # Weather
        weather_result = collect_weather(active_dates)
        results.append(weather_result)
        
        # Player daily status (for today only)
        if today in active_dates:
            player_status_result = collect_daily_player_status(today)
            results.append(player_status_result)
        
    except Exception as e:
        log_error("Lightweight Collection", f"Collection failed: {e}")
        overall_success = False
    
    # Summary
    total_changes = sum(r.get('inserted', 0) + r.get('updated', 0) for r in results)
    
    logger.info(f"📊 Lightweight collection complete: {total_changes} total changes")
    
    return {
        'overall_success': overall_success,
        'total_changes': total_changes,
        'results': results,
        'dates_processed': len(active_dates),
        'collection_type': 'lightweight'
    }

def run_score_update() -> Dict:
    """Update just game scores for yesterday and today"""
    logger.info("⚾ Running score update")
    
    yesterday, today, _ = get_collection_dates()
    dates = [d for d in [yesterday, today] if is_mlb_season(d)]
    
    if not dates:
        return {'overall_success': True, 'message': 'No active season dates'}
    
    result = collect_games(dates)
    
    return {
        'overall_success': result['success'],
        'total_changes': result['inserted'] + result['updated'],
        'results': [result]
    }
    """Update just game scores for yesterday and today"""
    logger.info("⚾ Running score update")
    
    yesterday, today, _ = get_collection_dates()
    dates = [d for d in [yesterday, today] if is_mlb_season(d)]
    
    if not dates:
        return {'overall_success': True, 'message': 'No active season dates'}
    
    result = collect_games(dates)
    
    return {
        'overall_success': result['success'],
        'total_changes': result['inserted'] + result['updated'],
        'results': [result]
    }

def run_trade_update() -> Dict:
    """Update just transactions for today"""
    logger.info("🔄 Running trade update")
    
    _, today, _ = get_collection_dates()
    
    if not is_mlb_season(today):
        return {'overall_success': True, 'message': 'Off-season'}
    
    result = collect_transactions([today])
    
    return {
        'overall_success': result['success'],
        'total_changes': result['inserted'] + result['updated'],
        'results': [result]
    }

def run_player_stats_update(season: int = None) -> Dict:
    """Update player statistics for current season"""
    logger.info("⚾ Running player stats update")
    
    result = collect_all_player_stats(season)
    
    return {
        'overall_success': result['overall_success'],
        'total_changes': result.get('total_inserted', 0) + result.get('total_updated', 0),
        'results': result.get('results', [])
    }

def run_multi_season_player_stats(seasons: List[int] = None) -> Dict:
    """
    Run player stats collection for multiple seasons
    
    Args:
        seasons: List of seasons to collect. Defaults to [2023, 2024, 2025]
    """
    if seasons is None:
        seasons = [2023, 2024, 2025]
    
    logger.info(f"🏆 Running multi-season player stats collection for {seasons}")
    
    try:
        from .player_stats import PlayerStatsCollector
    except ImportError:
        from DataCollection.player_stats import PlayerStatsCollector
    
    collector = PlayerStatsCollector()
    result = collector.collect_multi_season_stats(seasons)
    
    return {
        'overall_success': result['success'],
        'total_changes': result.get('total_records', 0),
        'batting_records': result.get('batting_records', 0),
        'pitching_records': result.get('pitching_records', 0),
        'seasons_processed': result.get('seasons_processed', []),
        'errors': result.get('total_errors', 0)
    }

def run_custom_collection(sources: List[str], days_back: int = 3) -> Dict:
    """
    Run collection for specific sources
    
    Args:
        sources: List of sources ['games', 'transactions', 'weather']
        days_back: Number of days to go back
    """
    logger.info(f"🎯 Running custom collection for {sources}")
    
    # Get dates
    today = date.today()
    dates = []
    for i in range(days_back):
        check_date = date(today.year, today.month, today.day - i) if today.day > i else date(today.year, today.month - 1, 28 + today.day - i)
        if is_mlb_season(check_date):
            dates.append(check_date)
    
    if not dates:
        return {'overall_success': True, 'message': 'No active season dates'}
    
    results = []
    overall_success = True
    
    try:
        if 'games' in sources:
            results.append(collect_games(dates))
        
        if 'transactions' in sources:
            results.append(collect_transactions(dates))
        
        if 'weather' in sources:
            results.append(collect_weather(dates))
        
        if 'players' in sources:
            results.append(collect_all_player_stats())
            
    except Exception as e:
        log_error("Custom Collection", f"Failed: {e}")
        overall_success = False
    
    total_changes = sum(r.get('inserted', 0) + r.get('updated', 0) for r in results)
    
    return {
        'overall_success': overall_success,
        'total_changes': total_changes,
        'results': results,
        'dates_processed': len(dates)
    }

# Simple command line interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == 'daily':
            result = run_daily_collection()  # Comprehensive collection
        elif mode == 'lightweight':
            result = run_lightweight_collection()  # Original collection
        elif mode == 'scores':
            result = run_score_update()
        elif mode == 'trades':
            result = run_trade_update()
        elif mode == 'players':
            result = run_player_stats_update()
        elif mode == 'multi-season':
            # Allow specifying seasons as additional arguments
            if len(sys.argv) > 2:
                seasons = [int(year) for year in sys.argv[2:]]
                result = run_multi_season_player_stats(seasons)
            else:
                result = run_multi_season_player_stats()  # Use default [2023, 2024, 2025]
        else:
            print("Usage: python collector.py [daily|lightweight|scores|trades|players|multi-season [year1 year2 ...]]")
            print("  daily: Comprehensive collection (games, transactions, weather, player stats, roster)")
            print("  lightweight: Original collection (games, transactions, weather, daily status)")
            print("  scores: Game scores only")
            print("  trades: Transactions only") 
            print("  players: Player statistics only")
            print("  multi-season: Multi-season player stats")
            sys.exit(1)
    else:
        result = run_daily_collection()  # Default to comprehensive collection
    
    print(f"✅ Success: {result['overall_success']}")
    print(f"📊 Changes: {result.get('total_changes', 0)}")
    print(f"🎯 Type: {result.get('collection_type', 'unknown')}")
    
    sys.exit(0 if result['overall_success'] else 1)