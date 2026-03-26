"""
Simple games data collection
"""
import requests
from datetime import date, datetime, timezone
from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_
from Database.config.database import DatabaseConfig
from Database.models.models import Game
from .utils import normalize_team_name, make_api_request, log_result, log_error
import logging

logger = logging.getLogger(__name__)

def collect_games_for_date(target_date: date) -> tuple[int, int, int]:
    """
    Collect games for a single date
    Returns: (processed, inserted, updated)
    """
    db_config = DatabaseConfig()
    session = sessionmaker(bind=db_config.create_engine())()
    
    processed = inserted = updated = 0
    
    try:
        # Get games from MLB API
        url = "https://statsapi.mlb.com/api/v1/schedule"
        params = {
            'sportId': 1,
            'date': target_date.strftime('%Y-%m-%d'),
            'hydrate': 'team'
        }
        
        response = make_api_request(url, params)
        data = response.json()
        
        if 'dates' not in data or not data['dates']:
            return processed, inserted, updated
        
        for date_entry in data['dates']:
            for game in date_entry.get('games', []):
                try:
                    game_pk = game.get('gamePk')
                    if not game_pk:
                        continue
                    
                    # Extract team data
                    teams = game.get('teams', {})
                    home_team = teams.get('home', {}).get('team', {})
                    away_team = teams.get('away', {}).get('team', {})
                    
                    home_team_id = normalize_team_name(home_team.get('abbreviation'))
                    away_team_id = normalize_team_name(away_team.get('abbreviation'))
                    
                    if not home_team_id or not away_team_id:
                        continue
                    
                    # Skip exhibition games and non-MLB teams
                    game_type = game.get('gameType', '')
                    if game_type == 'E':  # Skip exhibition games
                        continue
                        
                    # Verify both teams are valid MLB teams (after normalization)
                    valid_mlb_teams = {
                        'ATL', 'AZ', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
                        'HOU', 'KC', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'OAK',
                        'PHI', 'PIT', 'SD', 'SF', 'SEA', 'STL', 'TB', 'TEX', 'TOR', 'WSH'
                    }
                    
                    if home_team_id not in valid_mlb_teams or away_team_id not in valid_mlb_teams:
                        continue
                    
                    # Extract scores
                    home_score = teams.get('home', {}).get('score')
                    away_score = teams.get('away', {}).get('score')
                    
                    # Determine winner
                    winner_id = None
                    if home_score is not None and away_score is not None:
                        if home_score > away_score:
                            winner_id = home_team_id
                        elif away_score > home_score:
                            winner_id = away_team_id
                    
                    # Get game status
                    game_status = game.get('status', {}).get('detailedState', 'Scheduled').lower()
                    if game_status == 'final':
                        game_status = 'completed'
                    
                    # Check if game exists
                    existing_game = session.query(Game).filter(
                        and_(
                            Game.game_date == target_date,
                            Game.home_team_id == home_team_id,
                            Game.away_team_id == away_team_id
                        )
                    ).first()
                    
                    processed += 1
                    
                    if existing_game:
                        # Update existing game
                        changes_made = False
                        
                        if existing_game.game_pk != game_pk:
                            existing_game.game_pk = game_pk
                            changes_made = True
                        
                        if home_score is not None and existing_game.home_score != home_score:
                            existing_game.home_score = home_score
                            changes_made = True
                        
                        if away_score is not None and existing_game.away_score != away_score:
                            existing_game.away_score = away_score
                            changes_made = True
                        
                        if winner_id and existing_game.winner_team_id != winner_id:
                            existing_game.winner_team_id = winner_id
                            changes_made = True
                        
                        if existing_game.game_status != game_status:
                            existing_game.game_status = game_status
                            changes_made = True
                        
                        if changes_made:
                            existing_game.updated_at = datetime.now(timezone.utc)
                            updated += 1
                    else:
                        # Create new game
                        new_game = Game(
                            game_pk=game_pk,
                            game_date=target_date,
                            home_team_id=home_team_id,
                            away_team_id=away_team_id,
                            home_score=home_score,
                            away_score=away_score,
                            winner_team_id=winner_id,
                            game_status=game_status,
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc)
                        )
                        session.add(new_game)
                        inserted += 1
                
                except Exception as e:
                    log_error("Games", f"Error processing game {game.get('gamePk', 'unknown')}: {e}")
                    continue
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        log_error("Games", f"Failed to collect games for {target_date}: {e}")
    
    finally:
        session.close()
    
    return processed, inserted, updated

def collect_games(dates: list[date]) -> dict:
    """
    Collect games for multiple dates
    Returns summary dictionary
    """
    total_processed = total_inserted = total_updated = 0
    
    logger.info(f"🏟️ Collecting games for {len(dates)} dates")
    
    for target_date in dates:
        processed, inserted, updated = collect_games_for_date(target_date)
        total_processed += processed
        total_inserted += inserted
        total_updated += updated
    
    log_result("Games", total_processed, total_inserted, total_updated)
    
    return {
        'source': 'games',
        'success': True,
        'processed': total_processed,
        'inserted': total_inserted,
        'updated': total_updated
    }