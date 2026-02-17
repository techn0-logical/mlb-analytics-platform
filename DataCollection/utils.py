"""
Utility functions for MLB data collection
"""
import time
import requests
import logging
from typing import Optional
from datetime import date
from .config import config

logger = logging.getLogger(__name__)

def normalize_team_name(team_name: str) -> Optional[str]:
    """Convert team name to standard format"""
    if not team_name:
        return None
    
    team_name = str(team_name).strip().upper()
    return config.team_mapping.get(team_name, team_name[:3] if len(team_name) >= 2 else None)

def is_mlb_season(check_date: date) -> bool:
    """Check if date is during MLB season"""
    return 2 <= check_date.month <= 11

def get_collection_dates() -> tuple[date, date, date]:
    """Get yesterday, today, tomorrow"""
    today = date.today()
    yesterday = date(today.year, today.month, today.day - 1) if today.day > 1 else date(today.year, today.month - 1, 28)
    tomorrow = date(today.year, today.month, today.day + 1)
    return yesterday, today, tomorrow

def make_api_request(url: str, params: dict = None) -> requests.Response:
    """Make a rate-limited API request with retries"""
    
    for attempt in range(config.max_retries):
        try:
            # Rate limiting
            time.sleep(config.rate_limit_delay)
            
            response = requests.get(
                url, 
                params=params,
                timeout=config.api_timeout,
                headers={'User-Agent': 'MLB-Analytics/1.0'}
            )
            response.raise_for_status()
            return response
            
        except requests.RequestException as e:
            if attempt == config.max_retries - 1:
                raise
            logger.warning(f"API request failed (attempt {attempt + 1}): {e}")
            time.sleep(2 ** attempt)  # Exponential backoff

def log_result(source: str, processed: int, inserted: int, updated: int):
    """Log collection results in a standard format"""
    total_changes = inserted + updated
    logger.info(f"✅ {source}: {processed} processed, {inserted} new, {updated} updated ({total_changes} total changes)")

def log_error(source: str, error: str):
    """Log errors in a standard format"""
    logger.error(f"❌ {source}: {error}")