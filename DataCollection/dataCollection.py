#!/usr/bin/env python3
"""
Simple MLB Data Collection Entry Point
====================================

A clean, simple replacement for the massive comprehensive_collection_system.py

Usage:
    python dataCollection.py              # Daily collection
    python dataCollection.py --mode scores    # Score updates only  
    python dataCollection.py --mode trades    # Trade updates only
    python dataCollection.py --mode validate  # Validate setup
"""

import argparse
import sys
import os
import logging
from datetime import date

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from DataCollection import (
    run_daily_collection, 
    run_score_update,
    run_trade_update,
    run_custom_collection
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_setup() -> bool:
    """Validate the data collection setup"""
    logger.info("🔍 Validating MLB data collection setup...")
    
    try:
        # Test database connection
        from Database.config.database import test_connection
        if not test_connection():
            logger.error("❌ Database connection failed")
            return False
        logger.info("✅ Database connection: OK")
        
        # Check API keys
        from dotenv import load_dotenv
        load_dotenv(os.path.join(project_root, 'secrets.env'))
        
        odds_key = os.getenv('ODDS_API_KEY')
        weather_key = os.getenv('OPENWEATHER_API_KEY')
        
        logger.info(f"✅ Odds API key: {'OK' if odds_key else 'Missing (optional)'}")
        logger.info(f"✅ Weather API key: {'OK' if weather_key else 'Missing (optional)'}")
        
        # Check season status
        from DataCollection.utils import is_mlb_season
        today_in_season = is_mlb_season(date.today())
        logger.info(f"📅 Season status: {'Active' if today_in_season else 'Off-season'}")
        
        # Test import of core modules
        from DataCollection.games import collect_games
        from DataCollection.transactions import collect_transactions
        from DataCollection.weather import collect_weather
        logger.info("✅ All core modules import successfully")
        
        logger.info("🎉 Setup validation complete - system ready!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Setup validation failed: {e}")
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Simple MLB Data Collection')
    parser.add_argument('--mode', 
                       choices=['daily', 'scores', 'trades', 'validate'],
                       default='daily',
                       help='Collection mode (default: daily)')
    parser.add_argument('--sources', 
                       nargs='+',
                       choices=['games', 'transactions', 'weather'],
                       help='Specific sources for targeted collection')
    parser.add_argument('--days-back', 
                       type=int, 
                       default=3,
                       help='Days to look back (default: 3)')
    parser.add_argument('--no-validation', 
                       action='store_true',
                       help='Skip data validation')
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'validate':
            success = validate_setup()
            sys.exit(0 if success else 1)
        
        elif args.mode == 'daily':
            logger.info("🌅 Running daily MLB data collection")
            result = run_daily_collection()
        
        elif args.mode == 'scores':
            logger.info("⚾ Running score updates")
            result = run_score_update()
        
        elif args.mode == 'trades':
            logger.info("🔄 Running trade updates")
            result = run_trade_update()
        
        elif args.sources:
            logger.info(f"🎯 Running targeted collection for {args.sources}")
            result = run_custom_collection(args.sources, args.days_back)
        
        else:
            logger.info("🌅 Running daily collection (default)")
            result = run_daily_collection()
        
        # Print results
        print()
        print("=" * 50)
        print("📊 COLLECTION SUMMARY")
        print("=" * 50)
        print(f"Overall Success: {'✅ Yes' if result['overall_success'] else '❌ No'}")
        print(f"Total Changes: {result.get('total_changes', 0):,}")
        print(f"Dates Processed: {result.get('dates_processed', 0)}")
        
        if result.get('message'):
            print(f"Note: {result['message']}")
        
        if result.get('results'):
            print(f"\nBy Source:")
            for source_result in result['results']:
                name = source_result.get('source', 'Unknown').title()
                changes = source_result.get('inserted', 0) + source_result.get('updated', 0)
                print(f"  {name}: {changes} changes")
        
        print("=" * 50)
        
        # Exit with appropriate code
        sys.exit(0 if result['overall_success'] else 1)
        
    except KeyboardInterrupt:
        logger.info("🛑 Collection interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()