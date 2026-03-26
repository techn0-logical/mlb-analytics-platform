#!/usr/bin/env python3
"""
Populate Players Table

This script populates the players table with all MLB players who have stats
in the batting_stats and pitching_stats tables but don't exist in players table.

This is a one-time setup script to resolve foreign key constraints.
"""

import logging
import sys
import os
from datetime import datetime
from typing import Set, List

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import database components
try:
    from Database.config.database import db_config
    from Database.models.models import Player, PlayerBattingStats, PlayerPitchingStats
except ImportError as e:
    print(f"❌ Could not import database models: {e}")
    print("Check your database setup and ensure all dependencies are installed.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_missing_player_ids() -> Set[int]:
    """Get all player IDs that exist in stats tables but not in players table"""
    
    SessionLocal = db_config.create_session_factory()
    session = SessionLocal()
    try:
        # Get all player IDs from batting stats
        batting_players = session.query(PlayerBattingStats.player_id).distinct().all()
        batting_ids = {pid[0] for pid in batting_players}
        
        # Get all player IDs from pitching stats  
        pitching_players = session.query(PlayerPitchingStats.player_id).distinct().all()
        pitching_ids = {pid[0] for pid in pitching_players}
        
        # Combine all stats player IDs
        all_stats_ids = batting_ids.union(pitching_ids)
        
        # Get existing player IDs from players table
        existing_players = session.query(Player.player_id).all()
        existing_ids = {pid[0] for pid in existing_players}
        
        # Find missing players
        missing_ids = all_stats_ids - existing_ids
        
        logger.info(f"📊 Found {len(batting_ids)} players in batting stats")
        logger.info(f"📊 Found {len(pitching_ids)} players in pitching stats")
        logger.info(f"📊 Total unique players in stats: {len(all_stats_ids)}")
        logger.info(f"📊 Existing players in players table: {len(existing_ids)}")
        logger.info(f"📊 Missing players to create: {len(missing_ids)}")
        
        return missing_ids
        
    finally:
        session.close()


def fetch_player_data_from_api(player_id: int) -> dict:
    """Fetch player biographical data from MLB Stats API"""
    
    try:
        import urllib.request
        import json
        
        # Get player data from MLB Stats API
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
        
        if not data.get('people'):
            return None
        
        player_info = data['people'][0]
        
        # Parse height (e.g., "6' 2\"" -> 74 inches)
        height_str = player_info.get('height', '')
        height_inches = None
        if height_str and "'" in height_str:
            try:
                parts = height_str.replace('"', '').replace("'", ' ').split()
                if len(parts) >= 2:
                    feet = int(parts[0])
                    inches = int(parts[1])
                    height_inches = feet * 12 + inches
            except (ValueError, IndexError):
                pass
        
        # Parse birth date
        birth_date = None
        birth_date_str = player_info.get('birthDate')
        if birth_date_str:
            try:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # Parse debut date
        debut_date = None
        debut_str = player_info.get('mlbDebutDate')
        if debut_str:
            try:
                debut_date = datetime.strptime(debut_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        return {
            'player_id': player_id,
            'first_name': player_info.get('firstName'),
            'last_name': player_info.get('lastName'),
            'full_name': player_info.get('fullName'),
            'birth_date': birth_date,
            'birth_city': player_info.get('birthCity'),
            'birth_state': player_info.get('birthStateProvince'),
            'birth_country': player_info.get('birthCountry'),
            'height_inches': height_inches,
            'weight_lbs': player_info.get('weight'),
            'bats': player_info.get('batSide', {}).get('code'),
            'throws': player_info.get('pitchHand', {}).get('code'),
            'position': player_info.get('primaryPosition', {}).get('abbreviation'),
            'jersey_number': player_info.get('primaryNumber'),
            'debut_date': debut_date,
            'is_active': player_info.get('active', True),
            'last_updated': datetime.now()
        }
        
    except Exception as e:
        logger.warning(f"Failed to fetch data for player {player_id}: {str(e)}")
        return None


def create_player_record(player_data: dict, session) -> bool:
    """Create a player record in the database"""
    
    try:
        # Create player record
        player = Player(**player_data)
        session.add(player)
        return True
        
    except Exception as e:
        logger.warning(f"Failed to create player {player_data['player_id']}: {str(e)}")
        return False


def populate_players_table(batch_size: int = 50) -> dict:
    """Populate the players table with missing players"""
    
    logger.info("🏗️  Starting players table population...")
    
    # Get missing player IDs
    missing_ids = get_missing_player_ids()
    
    if not missing_ids:
        logger.info("✅ No missing players found - players table is already populated!")
        return {
            'success': True,
            'total_processed': 0,
            'created': 0,
            'skipped': 0,
            'errors': 0
        }
    
    SessionLocal = db_config.create_session_factory()
    session = SessionLocal()
    
    created = 0
    skipped = 0
    errors = 0
    processed = 0
    
    try:
        missing_list = list(missing_ids)
        total_missing = len(missing_list)
        
        logger.info(f"👥 Processing {total_missing} missing players...")
        
        # Process in batches
        for i in range(0, total_missing, batch_size):
            batch = missing_list[i:i + batch_size]
            batch_created = 0
            batch_skipped = 0
            batch_errors = 0
            
            logger.info(f"📦 Processing batch {i//batch_size + 1}: players {i+1}-{min(i+batch_size, total_missing)}")
            
            for player_id in batch:
                processed += 1
                
                # Fetch player data from API
                player_data = fetch_player_data_from_api(player_id)
                
                if not player_data:
                    logger.warning(f"   ⚠️  Skipping player {player_id} - no API data")
                    skipped += 1
                    batch_skipped += 1
                    continue
                
                # Create player record
                if create_player_record(player_data, session):
                    created += 1
                    batch_created += 1
                    logger.debug(f"   ✅ Created: {player_data.get('full_name', 'Unknown')} ({player_id})")
                else:
                    errors += 1
                    batch_errors += 1
                
                # Progress indicator
                if processed % 10 == 0:
                    logger.info(f"   📊 Progress: {processed}/{total_missing} ({processed/total_missing*100:.1f}%)")
            
            # Commit batch
            try:
                session.commit()
                logger.info(f"   💾 Batch complete: {batch_created} created, {batch_skipped} skipped, {batch_errors} errors")
            except Exception as e:
                session.rollback()
                logger.error(f"   ❌ Batch commit failed: {str(e)}")
                errors += len(batch)
                created -= batch_created  # Rollback the count
        
        logger.info("🏗️  Players table population complete!")
        logger.info(f"   📊 Total processed: {processed}")
        logger.info(f"   ✅ Created: {created}")
        logger.info(f"   ⚠️  Skipped: {skipped}")
        logger.info(f"   ❌ Errors: {errors}")
        
        return {
            'success': errors == 0,
            'total_processed': processed,
            'created': created,
            'skipped': skipped,
            'errors': errors
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Population failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'total_processed': processed,
            'created': created,
            'skipped': skipped,
            'errors': errors
        }
    
    finally:
        session.close()


def verify_population() -> dict:
    """Verify that all players with stats now exist in players table"""
    
    logger.info("🔍 Verifying players table population...")
    
    missing_ids = get_missing_player_ids()
    
    if not missing_ids:
        logger.info("✅ Verification passed - no missing players!")
        return {'success': True, 'missing_count': 0}
    else:
        logger.warning(f"⚠️  Verification found {len(missing_ids)} still missing players")
        logger.warning(f"   Missing IDs: {sorted(list(missing_ids))[:10]}...")  # Show first 10
        return {'success': False, 'missing_count': len(missing_ids), 'missing_ids': list(missing_ids)}


if __name__ == "__main__":
    
    logger.info("🚀 Starting MLB Players Table Population")
    
    # Populate players table
    result = populate_players_table()
    
    if result['success']:
        logger.info("✅ Population completed successfully!")
        
        # Verify the population
        verification = verify_population()
        
        if verification['success']:
            logger.info("🎉 All done! Players table is now fully populated.")
            logger.info("   You can now run player stats collection without foreign key errors.")
        else:
            logger.warning(f"⚠️  {verification['missing_count']} players still missing after population")
    
    else:
        logger.error("❌ Population failed")
        if 'error' in result:
            logger.error(f"   Error: {result['error']}")
    
    # Print summary
    print("\n" + "="*60)
    print("POPULATION SUMMARY")
    print("="*60)
    print(f"Success: {result['success']}")
    print(f"Total Processed: {result['total_processed']}")
    print(f"Created: {result['created']}")
    print(f"Skipped: {result['skipped']}")
    print(f"Errors: {result['errors']}")
    print("="*60)
    
    sys.exit(0 if result['success'] else 1)