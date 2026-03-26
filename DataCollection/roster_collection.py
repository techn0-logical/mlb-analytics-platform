"""
MLB Roster Collection Module
===========================

Comprehensive roster data collection to fill gaps in player_team_history.
Specifically designed to fix Oakland Athletics and verify other team data.

This module:
1. Collects historical roster data from MLB API
2. Cross-references with existing player stats
3. Creates missing player_team_history records
4. Validates data consistency across the database
"""

import logging
import requests
from datetime import date, datetime
from typing import List, Dict, Tuple
from sqlalchemy import text
from Database.config.database import db_config
from .config import config
from .utils import log_result, log_error

logger = logging.getLogger(__name__)

class RosterCollector:
    """Handles comprehensive roster data collection and validation"""
    
    def __init__(self):
        self.session_generator = db_config.get_session()
        self.session = next(self.session_generator)
        self.base_url = "https://statsapi.mlb.com/api/v1"
    
    def close(self):
        """Clean up database session"""
        if self.session:
            self.session.close()
    
    def get_team_roster_for_season(self, team_id: str, season: int) -> List[Dict]:
        """
        Get roster data from MLB API for a specific team and season
        
        Args:
            team_id: MLB team abbreviation (e.g., 'OAK')
            season: Year (e.g., 2023)
            
        Returns:
            List of player dictionaries
        """
        try:
            # Try different roster endpoints
            urls_to_try = [
                f"{self.base_url}/teams/{team_id}/roster?rosterType=active&season={season}",
                f"{self.base_url}/teams/{team_id}/roster?season={season}",
                f"{self.base_url}/teams/{team_id}/players?season={season}"
            ]
            
            for url in urls_to_try:
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Extract players from different response formats
                        if 'roster' in data:
                            return data['roster']
                        elif 'people' in data:
                            return data['people']
                        elif isinstance(data, list):
                            return data
                            
                except requests.RequestException:
                    continue
            
            # If API fails, try to reconstruct from player stats
            return self._get_roster_from_stats(team_id, season)
            
        except Exception as e:
            logger.warning(f"Failed to get {team_id} roster for {season}: {e}")
            return self._get_roster_from_stats(team_id, season)
    
    def _get_roster_from_stats(self, team_id: str, season: int) -> List[Dict]:
        """
        Reconstruct roster from existing player statistics
        
        This is used when API data is unavailable
        """
        try:
            # Get all players who have stats for this team/season
            players_query = text("""
                SELECT DISTINCT 
                    pbs.player_id,
                    p.name_display,
                    p.primary_position,
                    pbs.games
                FROM player_batting_stats pbs
                JOIN players p ON pbs.player_id = p.player_id
                WHERE pbs.team_id = :team_id AND pbs.season = :season
                
                UNION
                
                SELECT DISTINCT 
                    pps.player_id,
                    p.name_display,
                    'P' as primary_position,
                    pps.games
                FROM player_pitching_stats pps
                JOIN players p ON pps.player_id = p.player_id
                WHERE pps.team_id = :team_id AND pps.season = :season
                
                ORDER BY games DESC
            """)
            
            results = self.session.execute(players_query, {
                'team_id': team_id,
                'season': season
            }).fetchall()
            
            # Convert to API-like format
            roster = []
            for result in results:
                roster.append({
                    'person': {
                        'id': result[0],
                        'fullName': result[1],
                        'primaryPosition': {'abbreviation': result[2] or 'OF'}
                    },
                    'status': {'description': 'Active'},
                    'games_played': result[3]
                })
            
            logger.info(f"Reconstructed {team_id} {season} roster from stats: {len(roster)} players")
            return roster
            
        except Exception as e:
            logger.error(f"Failed to reconstruct roster for {team_id} {season}: {e}")
            return []
    
    def create_team_history_record(self, player_id: int, team_id: str, season: int, 
                                 roster_status: str = 'active', position: str = None) -> bool:
        """
        Create a player_team_history record
        
        Args:
            player_id: Player ID
            team_id: Team abbreviation
            season: Season year
            roster_status: Roster status ('active', 'disabled', etc.)
            position: Primary position
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if record already exists
            existing_query = text("""
                SELECT COUNT(*) FROM player_team_history 
                WHERE player_id = :player_id AND team_id = :team_id AND season = :season
            """)
            
            exists = self.session.execute(existing_query, {
                'player_id': player_id,
                'team_id': team_id,
                'season': season
            }).scalar()
            
            if exists > 0:
                return True  # Already exists, no need to create
            
            # Create new record
            insert_query = text("""
                INSERT INTO player_team_history 
                (player_id, team_id, start_date, end_date, season, roster_status, 
                 primary_position, acquisition_type, is_current, is_active_roster, 
                 created_at, updated_at)
                VALUES 
                (:player_id, :team_id, :start_date, :end_date, :season, :roster_status,
                 :position, 'historical_collection', :is_current, true, 
                 NOW(), NOW())
            """)
            
            # Determine if this is current (2026 season)
            is_current = (season == 2026)
            start_date = f"{season}-01-01"
            end_date = None if is_current else f"{season}-12-31"
            
            self.session.execute(insert_query, {
                'player_id': player_id,
                'team_id': team_id,
                'start_date': start_date,
                'end_date': end_date,
                'season': season,
                'roster_status': roster_status,
                'position': position,
                'is_current': is_current
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create team history for player {player_id}: {e}")
            return False
    
    def collect_team_historical_rosters(self, team_id: str, start_year: int = 2018, 
                                      end_year: int = 2025) -> Dict:
        """
        Collect historical roster data for a specific team
        
        Args:
            team_id: Team abbreviation (e.g., 'OAK')
            start_year: Starting year for collection
            end_year: Ending year for collection
            
        Returns:
            Summary dictionary with collection results
        """
        logger.info(f"🎯 Collecting historical rosters for {team_id}: {start_year}-{end_year}")
        
        total_processed = 0
        total_created = 0
        seasons_processed = 0
        
        for year in range(start_year, end_year + 1):
            try:
                logger.info(f"📅 Processing {team_id} {year} roster...")
                
                # Get roster for this season
                roster_data = self.get_team_roster_for_season(team_id, year)
                
                if not roster_data:
                    logger.warning(f"No roster data found for {team_id} {year}")
                    continue
                
                season_created = 0
                for player_data in roster_data:
                    try:
                        # Extract player info
                        if 'person' in player_data:
                            player_id = player_data['person']['id']
                            position = player_data['person'].get('primaryPosition', {}).get('abbreviation', 'OF')
                        else:
                            player_id = player_data.get('id')
                            position = player_data.get('primaryPosition', 'OF')
                        
                        if not player_id:
                            continue
                        
                        # Create team history record
                        if self.create_team_history_record(player_id, team_id, year, 'active', position):
                            season_created += 1
                        
                        total_processed += 1
                        
                    except Exception as e:
                        logger.warning(f"Error processing player in {team_id} {year}: {e}")
                        continue
                
                total_created += season_created
                seasons_processed += 1
                
                logger.info(f"✅ {team_id} {year}: {season_created} players added")
                
                # Commit after each season
                self.session.commit()
                
            except Exception as e:
                self.session.rollback()
                logger.error(f"Error processing {team_id} {year}: {e}")
                continue
        
        return {
            'team_id': team_id,
            'seasons_processed': seasons_processed,
            'total_processed': total_processed,
            'total_created': total_created,
            'success': True
        }
    
    def validate_team_data_consistency(self, team_id: str) -> Dict:
        """
        Validate that team roster data is consistent with player stats
        
        Args:
            team_id: Team abbreviation
            
        Returns:
            Validation report
        """
        try:
            # Check for players with stats but no team history
            missing_history_query = text("""
                SELECT DISTINCT 
                    pbs.player_id, 
                    p.name_display, 
                    pbs.season,
                    pbs.games
                FROM player_batting_stats pbs
                JOIN players p ON pbs.player_id = p.player_id
                WHERE pbs.team_id = :team_id
                AND NOT EXISTS (
                    SELECT 1 FROM player_team_history pth 
                    WHERE pth.player_id = pbs.player_id 
                    AND pth.team_id = :team_id 
                    AND pth.season = pbs.season
                )
                ORDER BY pbs.season DESC, pbs.games DESC
            """)
            
            missing_history = self.session.execute(missing_history_query, {
                'team_id': team_id
            }).fetchall()
            
            # Check for team history without corresponding stats
            orphaned_history_query = text("""
                SELECT DISTINCT 
                    pth.player_id,
                    p.name_display,
                    pth.season
                FROM player_team_history pth
                JOIN players p ON pth.player_id = p.player_id
                WHERE pth.team_id = :team_id
                AND pth.season IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM player_batting_stats pbs 
                    WHERE pbs.player_id = pth.player_id 
                    AND pbs.team_id = :team_id 
                    AND pbs.season = pth.season
                )
                AND NOT EXISTS (
                    SELECT 1 FROM player_pitching_stats pps 
                    WHERE pps.player_id = pth.player_id 
                    AND pps.team_id = :team_id 
                    AND pps.season = pth.season
                )
                ORDER BY pth.season DESC
            """)
            
            orphaned_history = self.session.execute(orphaned_history_query, {
                'team_id': team_id
            }).fetchall()
            
            return {
                'team_id': team_id,
                'missing_history': len(missing_history),
                'orphaned_history': len(orphaned_history),
                'missing_details': missing_history[:10],  # First 10 for review
                'orphaned_details': orphaned_history[:10],
                'is_consistent': len(missing_history) == 0 and len(orphaned_history) == 0
            }
            
        except Exception as e:
            logger.error(f"Validation error for {team_id}: {e}")
            return {'team_id': team_id, 'error': str(e), 'is_consistent': False}

def collect_oakland_historical_data() -> Dict:
    """
    Main function to collect comprehensive Oakland Athletics historical data
    """
    collector = RosterCollector()
    
    try:
        logger.info("🚀 Starting comprehensive Oakland Athletics data collection")
        
        # First validate current state
        validation = collector.validate_team_data_consistency('OAK')
        logger.info(f"📊 Pre-collection validation: {validation['missing_history']} missing records")
        
        # Collect historical roster data for missing seasons
        results = collector.collect_team_historical_rosters('OAK', 2018, 2025)
        
        # Post-collection validation
        post_validation = collector.validate_team_data_consistency('OAK')
        logger.info(f"✅ Post-collection validation: {post_validation['missing_history']} missing records")
        
        return {
            'success': True,
            'pre_collection': validation,
            'collection_results': results,
            'post_collection': post_validation,
            'improvement': validation['missing_history'] - post_validation['missing_history']
        }
        
    except Exception as e:
        logger.error(f"Oakland collection failed: {e}")
        return {'success': False, 'error': str(e)}
    
    finally:
        collector.close()

def validate_all_teams_data() -> Dict:
    """
    Run data validation across all MLB teams
    """
    collector = RosterCollector()
    
    try:
        logger.info("🔍 Running database-wide validation")
        
        # Get all team IDs
        teams_query = text("SELECT team_id, team_name FROM teams ORDER BY team_name")
        teams = collector.session.execute(teams_query).fetchall()
        
        validation_results = []
        inconsistent_teams = []
        
        for team in teams:
            team_id = team[0]
            validation = collector.validate_team_data_consistency(team_id)
            validation_results.append(validation)
            
            if not validation.get('is_consistent', False):
                inconsistent_teams.append(team_id)
        
        return {
            'success': True,
            'teams_checked': len(teams),
            'inconsistent_teams': inconsistent_teams,
            'validation_details': validation_results
        }
        
    except Exception as e:
        logger.error(f"Database validation failed: {e}")
        return {'success': False, 'error': str(e)}
    
    finally:
        collector.close()

# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == 'oakland':
            result = collect_oakland_historical_data()
            print(f"Oakland Collection: {'✅' if result['success'] else '❌'}")
            if result['success']:
                print(f"Records created: {result['collection_results']['total_created']}")
                print(f"Missing records fixed: {result['improvement']}")
        
        elif mode == 'validate':
            result = validate_all_teams_data()
            print(f"Validation: {'✅' if result['success'] else '❌'}")
            if result['success']:
                print(f"Inconsistent teams: {len(result['inconsistent_teams'])}")
                if result['inconsistent_teams']:
                    print(f"Teams needing fixes: {', '.join(result['inconsistent_teams'])}")
        
        else:
            print("Usage: python roster_collection.py [oakland|validate]")
    
    else:
        print("Running comprehensive Oakland data collection...")
        result = collect_oakland_historical_data()
        print(f"Success: {result['success']}")