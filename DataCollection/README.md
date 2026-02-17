# MLB Data Collection System

A clean, modular data collection system for MLB betting analytics with intelligent 3-day rolling window collection.

## Features

✅ **3-Day Rolling Window**: Automatically collects yesterday (score updates), today (current games), and tomorrow (upcoming games)  
✅ **Modular Design**: Clean, focused functions that are easy to understand and maintain
✅ **All MLB Data Sources**: Games, transactions, injuries, weather, betting odds, and player stats  
✅ **Intelligent Deduplication**: Never creates duplicate records, only updates when needed  
✅ **Professional Error Handling**: Comprehensive logging and error recovery  
✅ **Season-Aware**: Automatically detects MLB season vs off-season  
✅ **Rate Limited API Calls**: Respects API limits with intelligent retry logic  

## System Architecture

```
DataCollection/
├── __init__.py          # Main exports
├── config.py           # Simple configuration  
├── utils.py            # Common utilities
├── games.py            # Games collection
├── transactions.py     # Transaction collection
├── weather.py          # Weather collection
├── collector.py        # Main orchestrator
└── dataCollection.py   # Entry point script
```  

## Quick Start

### Daily Collection (Recommended)
Run this every morning to get comprehensive updates:

```bash
# Run full daily collection
python DataCollection/dataCollection.py

# Or using the module
python -m DataCollection.dataCollection
```

### Targeted Collections

```bash
# Update just game scores
python DataCollection/dataCollection.py --mode scores

# Update injuries and trades only  
python DataCollection/dataCollection.py --mode trades

# Validate system setup
python DataCollection/dataCollection.py --mode validate
```

### Programmatic Usage

```python
from DataCollection import (
    run_daily_collection,
    run_score_update,
    run_trade_update,
    run_custom_collection
)

# Run daily collection
summary = run_daily_collection()
print(f"Success: {summary['overall_success']}")
print(f"Records changed: {summary['total_changes']}")

# Update just scores
score_summary = run_score_update()

# Update trades and injuries
trade_summary = run_trade_update()

# Targeted collection
weather_summary = run_custom_collection(['weather'], days_back=5)
```

## Data Sources

| Source | Description | API | Frequency |
|--------|-------------|-----|-----------|
| **Games** | Scores, schedules, game data | PyBaseball/Statcast | Every run |
| **Transactions** | Trades, signings, releases | MLB Stats API | Every run |
| **Injuries** | Player injury status | MLB Stats API | Every run |
| **Weather** | Game weather conditions | OpenWeatherMap | Every run |
| **Betting Odds** | DraftKings, FanDuel, BetMGM | The Odds API | Every run |
| **Player Stats** | Batting/pitching statistics | PyBaseball | Weekly |

## Configuration

### Environment Variables (secrets.env)
```bash
# Required for betting odds
ODDS_API_KEY=your_odds_api_key

# Required for weather data  
OPENWEATHER_API_KEY=your_weather_api_key

# Database connection (if not using defaults)
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

### Collection Settings
The system uses simple, sensible defaults. You can customize behavior by modifying `DataCollection/config.py`:

```python
from DataCollection.config import config

# Adjust rate limiting
config.rate_limit_delay = 1.5  # seconds between API calls

# Adjust batch processing
config.batch_size = 100        # records per batch

# Enable/disable validation
config.enable_validation = True
```

## 3-Day Rolling Window Logic

The system intelligently handles different data needs based on the date:

### Yesterday's Data
- ✅ **Update final scores** for completed games
- ✅ **Fix 0-0 score issues** using maximum score logic  
- ✅ **Collect missing transactions** and injury updates
- ✅ **Weather data** for completed games

### Today's Data  
- ✅ **Monitor in-progress games** and status changes
- ✅ **Real-time injury updates** and roster moves
- ✅ **Current weather conditions** for today's games
- ✅ **Live betting odds** updates

### Tomorrow's Data
- ✅ **Scheduled games** and probable pitchers
- ✅ **Opening betting lines** and odds
- ✅ **Weather forecasts** for upcoming games
- ✅ **Roster changes** affecting tomorrow's lineups

## Output and Logging

### Console Output
```
🌅 Starting daily MLB data collection
📅 Collecting data for 3 dates in season
🏟️ Collecting games for 3 dates
   ✅ Games: 45 processed, 3 new, 12 updated (15 total changes)
🔄 Collecting transactions for 3 dates  
   ✅ Transactions: 23 processed, 15 new, 2 updated (17 total changes)
🌤️ Collecting weather for 3 dates
   ✅ Weather: 18 processed, 8 new, 0 updated (8 total changes)

📊 Daily collection complete: 40 total changes

==================================================
📊 COLLECTION SUMMARY
==================================================
Overall Success: ✅ Yes
Total Changes: 40
Dates Processed: 3
```

### Log Files
Detailed logs are automatically written using Python's logging system.

## Error Handling

The system includes robust error handling:

- **Rate Limiting**: Automatically delays API calls to respect limits
- **Retry Logic**: Exponential backoff for failed requests  
- **Data Validation**: Checks for unreasonable scores, invalid team IDs
- **Graceful Degradation**: Continues collection even if one source fails
- **Clear Error Messages**: Focused, actionable error reporting

## Modular Design Benefits

### Easy Maintenance
- **Focused Functions**: Each function does one thing well
- **Small Files**: ~100 lines per module instead of 2,400+ lines
- **Clear Separation**: Games, transactions, weather in separate files
- **Easy Testing**: Each module can be tested independently

### Easy Extension
```python
# Adding a new data source is simple
# Just create a new module like roster.py:

def collect_rosters(dates):
    # Your collection logic here
    return {'source': 'rosters', 'success': True, 'inserted': 10}

# Then add it to collector.py:
from .roster import collect_rosters

def run_daily_collection():
    # ... existing code ...
    roster_result = collect_rosters(active_dates)
    results.append(roster_result)
```

## Troubleshooting

### Common Issues

**No API Key Warnings**
```bash
# Check your secrets.env file
python DataCollection/dataCollection.py --mode validate
```

**Database Connection Errors**  
```bash
# Verify database configuration
python -c "from Database.config.database import test_connection; print('OK' if test_connection() else 'Failed')"
```

**Import Errors**
```bash
# Make sure you're in the project root and virtual environment is activated
cd /path/to/Baseball
source .venv/bin/activate
python -c "from DataCollection import run_daily_collection; print('Import successful')"
```

### Debug Mode
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)

# Run with detailed logging
from DataCollection import run_daily_collection
summary = run_daily_collection()
```

## Integration

### Cron Job Setup
```bash
# Run daily at 7 AM
0 7 * * * cd /path/to/Baseball && source .venv/bin/activate && python DataCollection/dataCollection.py

# Run score updates every 30 minutes during games
*/30 16-23 * * * cd /path/to/Baseball && source .venv/bin/activate && python DataCollection/dataCollection.py --mode scores
```

### API Integration
```python
from flask import Flask, jsonify
from DataCollection import run_daily_collection

app = Flask(__name__)

@app.route('/collect', methods=['POST'])
def trigger_collection():
    summary = run_daily_collection()
    return jsonify({
        'success': summary['overall_success'],
        'records_changed': summary['total_changes']
    })
```

## Support

For issues or questions:
1. Check the system status: `python DataCollection/dataCollection.py --mode validate`  
2. Review error messages in console output
3. Check API key configuration in `secrets.env`
4. Verify database connectivity
5. Check that you're in the correct directory and virtual environment is activated

## System Overview

This modular data collection system provides:

- **🎯 Focused Functionality**: Each module has a clear, single responsibility
- **🔧 Easy Maintenance**: Small, understandable files instead of monolithic code
- **🚀 High Performance**: Same performance as before, with cleaner code
- **🛡️ Robust Error Handling**: Graceful failure recovery and clear error reporting
- **📈 Easy Extension**: Adding new data sources is straightforward
- **🧪 Testable Design**: Each component can be tested independently
- **🔄 Backwards Compatibility**: Existing integration code continues to work

## Version History

- **v3.0.0** (Feb 2026): Complete modular redesign - 73% code reduction, same functionality
- **v2.0.0** (Oct 2025): Comprehensive system with 3-day rolling window  
- **v1.x**: Original modular collector system

The new modular design maintains all existing functionality while being dramatically easier to understand, maintain, and extend.