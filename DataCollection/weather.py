"""
Simple weather data collection
"""
from datetime import date, datetime, timezone
from sqlalchemy.orm import sessionmaker
from Database.config.database import DatabaseConfig
from Database.models.models import Game, Team, WeatherConditions
from .utils import make_api_request, log_result, log_error
from .config import config
import logging

logger = logging.getLogger(__name__)

def get_wind_direction(degrees: float) -> str:
    """Convert wind degrees to direction"""
    if degrees is None:
        return "Unknown"
    
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(degrees / 45) % 8
    return directions[index]

def collect_weather_for_date(target_date: date) -> tuple[int, int, int]:
    """
    Collect weather for games on a single date
    Returns: (processed, inserted, updated)
    """
    if not config.weather_api_key:
        log_error("Weather", "API key not configured")
        return 0, 0, 0
    
    db_config = DatabaseConfig()
    session = sessionmaker(bind=db_config.create_engine())()
    
    processed = inserted = updated = 0
    
    try:
        # Get games that need weather data
        games = session.query(Game).outerjoin(WeatherConditions).filter(
            Game.game_date == target_date,
            WeatherConditions.game_pk.is_(None)
        ).all()
        
        for game in games:
            try:
                # Get home team stadium location
                home_team = session.query(Team).filter(Team.team_id == game.home_team_id).first()
                if not home_team or not home_team.latitude or not home_team.longitude:
                    continue
                
                # Get weather data
                url = "http://api.openweathermap.org/data/2.5/weather"
                params = {
                    'lat': float(home_team.latitude),
                    'lon': float(home_team.longitude),
                    'appid': config.weather_api_key,
                    'units': 'imperial'
                }
                
                response = make_api_request(url, params)
                weather_data = response.json()
                
                # Parse weather data
                main = weather_data.get('main', {})
                wind = weather_data.get('wind', {})
                weather_list = weather_data.get('weather', [{}])
                
                # Create weather record
                weather = WeatherConditions(
                    game_pk=game.game_pk,
                    game_time=datetime.combine(game.game_date, datetime.min.time().replace(hour=19, minute=5)),
                    temperature=main.get('temp'),
                    humidity=main.get('humidity'),
                    wind_speed=wind.get('speed'),
                    wind_direction=get_wind_direction(wind.get('deg')),
                    conditions=weather_list[0].get('main', 'Unknown') if weather_list else 'Unknown',
                    pressure=main.get('pressure')
                )
                
                session.add(weather)
                processed += 1
                inserted += 1
                
            except Exception as e:
                log_error("Weather", f"Error collecting weather for game {game.game_pk}: {e}")
                continue
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        log_error("Weather", f"Failed to collect weather for {target_date}: {e}")
    
    finally:
        session.close()
    
    return processed, inserted, updated

def collect_weather(dates: list[date]) -> dict:
    """
    Collect weather for multiple dates
    Returns summary dictionary
    """
    total_processed = total_inserted = total_updated = 0
    
    logger.info(f"🌤️ Collecting weather for {len(dates)} dates")
    
    for target_date in dates:
        processed, inserted, updated = collect_weather_for_date(target_date)
        total_processed += processed
        total_inserted += inserted
        total_updated += updated
    
    log_result("Weather", total_processed, total_inserted, total_updated)
    
    return {
        'source': 'weather',
        'success': True,
        'processed': total_processed,
        'inserted': total_inserted,
        'updated': total_updated
    }