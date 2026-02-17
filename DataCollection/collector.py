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
except ImportError:
    # Fallback for command line usage
    from DataCollection.utils import get_collection_dates, is_mlb_season, log_error
    from DataCollection.games import collect_games
    from DataCollection.transactions import collect_transactions  
    from DataCollection.weather import collect_weather

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_daily_collection() -> Dict:
    """
    Run the standard daily collection
    Collects yesterday, today, and tomorrow
    """
    logger.info("🌅 Starting daily MLB data collection")
    
    # Get dates
    yesterday, today, tomorrow = get_collection_dates()
    dates = [yesterday, today, tomorrow]
    
    # Filter for MLB season dates only
    active_dates = [d for d in dates if is_mlb_season(d)]
    
    if not active_dates:
        logger.info("🚫 No collection needed - outside MLB season")
        return {'overall_success': True, 'message': 'Off-season'}
    
    logger.info(f"📅 Collecting data for {len(active_dates)} dates in season")
    
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
        
    except Exception as e:
        log_error("Daily Collection", f"Collection failed: {e}")
        overall_success = False
    
    # Summary
    total_changes = sum(r.get('inserted', 0) + r.get('updated', 0) for r in results)
    
    logger.info(f"📊 Daily collection complete: {total_changes} total changes")
    
    return {
        'overall_success': overall_success,
        'total_changes': total_changes,
        'results': results,
        'dates_processed': len(active_dates)
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
            result = run_daily_collection()
        elif mode == 'scores':
            result = run_score_update()
        elif mode == 'trades':
            result = run_trade_update()
        else:
            print("Usage: python collector.py [daily|scores|trades]")
            sys.exit(1)
    else:
        result = run_daily_collection()
    
    print(f"✅ Success: {result['overall_success']}")
    print(f"📊 Changes: {result.get('total_changes', 0)}")
    
    sys.exit(0 if result['overall_success'] else 1)