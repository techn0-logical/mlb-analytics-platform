"""
Simple configuration for MLB data collection
"""
import os
import sys
from dataclasses import dataclass
from typing import Dict, List
from dotenv import load_dotenv

# Add project root to path for database imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Load environment variables
load_dotenv(os.path.join(project_root, 'secrets.env'))

# Import database config
from Database.config.database import DatabaseConfig

@dataclass
class CollectionConfig:
    """Simple configuration for data collection"""
    
    # Basic settings
    rate_limit_delay: float = 1.0
    max_retries: int = 3
    batch_size: int = 50
    
    # API settings
    api_timeout: int = 30
    
    # Data quality
    enable_validation: bool = True
    
    # API keys
    odds_api_key: str = os.getenv('ODDS_API_KEY', '')
    weather_api_key: str = os.getenv('OPENWEATHER_API_KEY', '')
    
    # Team mapping (simplified)
    team_mapping: Dict[str, str] = None
    
    def __post_init__(self):
        if self.team_mapping is None:
            self.team_mapping = {
                'AZ': 'AZ', 'ATL': 'ATL', 'BAL': 'BAL', 'BOS': 'BOS', 'CHC': 'CHC',
                'CHW': 'CHW', 'CIN': 'CIN', 'CLE': 'CLE', 'COL': 'COL', 'DET': 'DET',
                'HOU': 'HOU', 'KC': 'KC', 'LAA': 'LAA', 'LAD': 'LAD', 'MIA': 'MIA',
                'MIL': 'MIL', 'MIN': 'MIN', 'NYM': 'NYM', 'NYY': 'NYY', 'OAK': 'OAK',
                'PHI': 'PHI', 'PIT': 'PIT', 'SD': 'SD', 'SF': 'SF', 'SEA': 'SEA',
                'STL': 'STL', 'TB': 'TB', 'TEX': 'TEX', 'TOR': 'TOR', 'WSH': 'WSH'
            }

# Global config instance
config = CollectionConfig()

# Database session management
def get_session():
    """Get database session"""
    db_config = DatabaseConfig()
    return db_config.get_session()