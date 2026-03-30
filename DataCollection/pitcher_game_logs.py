"""
Pitcher Game Logs Collection Module
====================================

Collects per-game pitching lines from MLB boxscores.
Enables opponent-specific ERA queries like "Freeland's ERA vs Miami."

Uses the MLB Stats API /game/{game_pk}/boxscore endpoint to pull
individual pitcher game lines for every completed game.

Usage:
    # Backfill all historical data
    python -m DataCollection.pitcher_game_logs backfill
    
    # Collect for a specific date
    python -m DataCollection.pitcher_game_logs 2025-06-15
    
    # Collect yesterday's games (daily pipeline)
    python -m DataCollection.pitcher_game_logs daily

Author: MLB Analytics Team
Version: 1.0.0
"""

import logging
import sys
import os
import time
import requests
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from Database.config.database import DatabaseConfig
from Database.models.models import PitcherGameLog, Game, Player
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, and_

logger = logging.getLogger(__name__)

# Valid MLB team abbreviations
VALID_TEAMS = {
    'ATL', 'AZ', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
    'HOU', 'KC', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'OAK',
    'PHI', 'PIT', 'SD', 'SF', 'SEA', 'STL', 'TB', 'TEX', 'TOR', 'WSH'
}

# MLB API team ID -> abbreviation
MLB_TEAM_ID_MAP = {
    108: 'LAA', 109: 'AZ', 110: 'BAL', 111: 'BOS', 112: 'CHC',
    113: 'CIN', 114: 'CLE', 115: 'COL', 116: 'DET', 117: 'HOU',
    118: 'KC', 119: 'LAD', 120: 'WSH', 121: 'NYM', 133: 'OAK',
    134: 'PIT', 135: 'SD', 136: 'SEA', 137: 'SF', 138: 'STL',
    139: 'TB', 140: 'TEX', 141: 'TOR', 142: 'MIN', 143: 'PHI',
    144: 'ATL', 145: 'CHW', 146: 'MIA', 147: 'NYY', 158: 'MIL'
}


class PitcherGameLogCollector:
    """Collects per-game pitching lines from MLB boxscores"""

    def __init__(self):
        self.db_config = DatabaseConfig()
        self.engine = self.db_config.create_engine()
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.rate_limit_delay = 0.25  # Be polite to the API

    def _make_api_request(self, url: str, params: dict = None) -> Optional[dict]:
        """Make an API request with retry logic"""
        for attempt in range(3):
            try:
                resp = requests.get(url, params=params or {}, timeout=30)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.HTTPError as e:
                if resp.status_code == 404:
                    return None
                logger.warning(f"HTTP {resp.status_code} on attempt {attempt+1}: {e}")
            except Exception as e:
                logger.warning(f"Request failed attempt {attempt+1}: {e}")
            time.sleep(1 * (attempt + 1))
        return None

    def _get_team_abbr(self, mlb_team_id: int) -> Optional[str]:
        """Convert MLB API team ID to our abbreviation"""
        return MLB_TEAM_ID_MAP.get(mlb_team_id)

    def _ensure_player_exists(self, player_id: int, player_info: dict) -> bool:
        """Ensure a player exists in the players table"""
        existing = self.session.query(Player).filter_by(player_id=player_id).first()
        if existing:
            return True

        try:
            full_name = player_info.get('fullName', 'Unknown Player')
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else 'Unknown'
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else 'Player'

            new_player = Player(
                player_id=player_id,
                name_first=first_name,
                name_last=last_name,
                name_display=full_name,
                is_active=True
            )
            self.session.add(new_player)
            self.session.flush()
            logger.debug(f"Created player: {full_name} ({player_id})")
            return True
        except Exception as e:
            self.session.rollback()
            logger.warning(f"Could not create player {player_id}: {e}")
            return False

    def collect_game_pitching(self, game_pk: int, game_date: date,
                               home_team_id: str, away_team_id: str) -> int:
        """
        Collect all pitcher game logs for a single game from the boxscore.
        Returns the number of pitcher logs inserted.
        """
        url = f"{self.base_url}/game/{game_pk}/boxscore"
        data = self._make_api_request(url)
        if not data:
            return 0

        inserted = 0
        season = game_date.year

        for side, team_id, opp_id in [('home', home_team_id, away_team_id),
                                       ('away', away_team_id, home_team_id)]:
            team_data = data.get('teams', {}).get(side, {})
            pitcher_ids = team_data.get('pitchers', [])
            players_dict = team_data.get('players', {})

            for idx, pid in enumerate(pitcher_ids):
                player_data = players_dict.get(f'ID{pid}', {})
                if not player_data:
                    continue

                pitching_stats = player_data.get('stats', {}).get('pitching', {})
                if not pitching_stats:
                    continue

                ip = float(pitching_stats.get('inningsPitched', 0) or 0)
                if ip == 0 and int(pitching_stats.get('battersFaced', 0) or 0) == 0:
                    continue

                person = player_data.get('person', {})
                pitcher_id = person.get('id', pid)

                # Ensure player exists
                if not self._ensure_player_exists(pitcher_id, person):
                    continue

                # Check for duplicate
                existing = self.session.query(PitcherGameLog).filter_by(
                    game_pk=game_pk, pitcher_id=pitcher_id
                ).first()
                if existing:
                    continue

                # Parse stats
                er = int(pitching_stats.get('earnedRuns', 0) or 0)
                h = int(pitching_stats.get('hits', 0) or 0)
                bb = int(pitching_stats.get('baseOnBalls', 0) or 0)
                is_starter = (idx == 0)  # First pitcher listed is the starter
                is_qs = is_starter and ip >= 6.0 and er <= 3

                log = PitcherGameLog(
                    game_pk=game_pk,
                    pitcher_id=pitcher_id,
                    pitcher_team_id=team_id,
                    opposing_team_id=opp_id,
                    game_date=game_date,
                    season=season,
                    is_starter=is_starter,
                    is_winner=(int(pitching_stats.get('wins', 0) or 0) > 0),
                    is_loser=(int(pitching_stats.get('losses', 0) or 0) > 0),
                    is_save=(int(pitching_stats.get('saves', 0) or 0) > 0),
                    is_hold=(int(pitching_stats.get('holds', 0) or 0) > 0),
                    innings_pitched=ip,
                    hits_allowed=h,
                    runs_allowed=int(pitching_stats.get('runs', 0) or 0),
                    earned_runs=er,
                    walks=bb,
                    strikeouts=int(pitching_stats.get('strikeOuts', 0) or 0),
                    home_runs_allowed=int(pitching_stats.get('homeRuns', 0) or 0),
                    pitches_thrown=int(pitching_stats.get('pitchesThrown',
                                      pitching_stats.get('numberOfPitches', 0)) or 0),
                    strikes=int(pitching_stats.get('strikes', 0) or 0),
                    batters_faced=int(pitching_stats.get('battersFaced', 0) or 0),
                    ground_outs=int(pitching_stats.get('groundOuts', 0) or 0),
                    fly_outs=int(pitching_stats.get('flyOuts', 0) or 0),
                    wild_pitches=int(pitching_stats.get('wildPitches', 0) or 0),
                    hit_batsmen=int(pitching_stats.get('hitBatsmen',
                                    pitching_stats.get('hitByPitch', 0)) or 0),
                    inherited_runners=int(pitching_stats.get('inheritedRunners', 0) or 0),
                    inherited_runners_scored=int(pitching_stats.get('inheritedRunnersScored', 0) or 0),
                    is_quality_start=is_qs,
                    summary=pitching_stats.get('summary')
                )
                self.session.add(log)
                inserted += 1

        return inserted

    def collect_for_date(self, target_date: date) -> Dict[str, Any]:
        """Collect pitcher game logs for all completed games on a date"""
        games = self.session.query(Game).filter(
            and_(
                Game.game_date == target_date,
                Game.game_status.like('completed%')
            )
        ).all()

        if not games:
            return {'success': True, 'date': str(target_date), 'games': 0, 'inserted': 0}

        total_inserted = 0
        games_processed = 0

        for game in games:
            if game.home_team_id not in VALID_TEAMS or game.away_team_id not in VALID_TEAMS:
                continue
            try:
                count = self.collect_game_pitching(
                    game.game_pk, game.game_date,
                    game.home_team_id, game.away_team_id
                )
                total_inserted += count
                games_processed += 1

                if games_processed % 5 == 0:
                    self.session.commit()
                    time.sleep(self.rate_limit_delay)

            except Exception as e:
                self.session.rollback()
                logger.error(f"Error processing game {game.game_pk}: {e}")

        self.session.commit()
        return {
            'success': True,
            'date': str(target_date),
            'games': games_processed,
            'inserted': total_inserted
        }

    def backfill_season(self, season: int) -> Dict[str, Any]:
        """Backfill all pitcher game logs for an entire season"""
        logger.info(f"📋 Backfilling pitcher game logs for {season}...")

        # Get all completed game dates for this season that we don't already have
        result = self.session.execute(text('''
            SELECT DISTINCT g.game_date
            FROM games g
            WHERE EXTRACT(YEAR FROM g.game_date) = :season
            AND g.game_status LIKE 'completed%%'
            AND g.home_team_id IN :teams
            AND NOT EXISTS (
                SELECT 1 FROM pitcher_game_logs pgl 
                WHERE pgl.game_pk = g.game_pk
            )
            ORDER BY g.game_date
        '''), {'season': season, 'teams': tuple(VALID_TEAMS)}).fetchall()

        dates = [r[0] for r in result]

        if not dates:
            logger.info(f"   ✅ {season}: All games already collected")
            return {'success': True, 'season': season, 'dates': 0, 'inserted': 0}

        logger.info(f"   📅 {season}: {len(dates)} dates to process ({dates[0]} → {dates[-1]})")

        total_inserted = 0
        total_games = 0

        for i, d in enumerate(dates):
            result = self.collect_for_date(d)
            total_inserted += result['inserted']
            total_games += result['games']

            if (i + 1) % 20 == 0:
                logger.info(f"   📅 {season}: {i+1}/{len(dates)} dates done "
                           f"({total_inserted} pitching lines so far)")
                time.sleep(self.rate_limit_delay)

        logger.info(f"   ✅ {season}: {total_inserted} pitching lines from {total_games} games")

        return {
            'success': True,
            'season': season,
            'dates': len(dates),
            'games': total_games,
            'inserted': total_inserted
        }

    def backfill_all(self, seasons: List[int] = None) -> Dict[str, Any]:
        """Backfill pitcher game logs for multiple seasons"""
        if seasons is None:
            seasons = [2022, 2023, 2024, 2025]

        logger.info(f"🏆 Starting pitcher game log backfill for seasons: {seasons}")

        results = {}
        grand_total = 0

        for season in seasons:
            result = self.backfill_season(season)
            results[season] = result
            grand_total += result.get('inserted', 0)

        logger.info(f"🏆 Backfill complete: {grand_total} total pitching lines across {len(seasons)} seasons")

        return {
            'success': True,
            'total_inserted': grand_total,
            'seasons': results
        }

    def collect_daily(self, target_date: date = None) -> Dict[str, Any]:
        """Collect pitcher game logs for yesterday's games (daily pipeline use)"""
        target_date = target_date or (date.today() - timedelta(days=1))
        logger.info(f"📋 Collecting pitcher game logs for {target_date}")
        return self.collect_for_date(target_date)

    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()


# ============================================================
# Convenience functions for the daily pipeline
# ============================================================

def collect_pitcher_game_logs(target_date: date = None) -> Dict[str, Any]:
    """Collect pitcher game logs — called from the daily pipeline"""
    collector = PitcherGameLogCollector()
    return collector.collect_daily(target_date)


def backfill_pitcher_game_logs(seasons: List[int] = None) -> Dict[str, Any]:
    """Backfill historical pitcher game logs"""
    collector = PitcherGameLogCollector()
    return collector.backfill_all(seasons)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    collector = PitcherGameLogCollector()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m DataCollection.pitcher_game_logs backfill          # All seasons (2022-2025)")
        print("  python -m DataCollection.pitcher_game_logs backfill 2024     # Specific season")
        print("  python -m DataCollection.pitcher_game_logs daily             # Yesterday's games")
        print("  python -m DataCollection.pitcher_game_logs 2025-06-15        # Specific date")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == 'backfill':
        if len(sys.argv) > 2:
            seasons = [int(s) for s in sys.argv[2:]]
        else:
            seasons = [2022, 2023, 2024, 2025]
        result = collector.backfill_all(seasons)
        print(f"\n✅ Backfill complete: {result['total_inserted']} pitching lines")
        for season, data in result['seasons'].items():
            print(f"   {season}: {data.get('inserted', 0)} lines from {data.get('games', 0)} games")

    elif mode == 'daily':
        result = collector.collect_daily()
        print(f"✅ Daily: {result['inserted']} pitching lines from {result['games']} games on {result['date']}")

    else:
        # Assume it's a date
        try:
            target = datetime.strptime(mode, '%Y-%m-%d').date()
            result = collector.collect_for_date(target)
            print(f"✅ {result['date']}: {result['inserted']} pitching lines from {result['games']} games")
        except ValueError:
            print(f"Unknown argument: {mode}")
            sys.exit(1)
