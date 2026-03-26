# MLB Player Stats Collection System

## Overview

The Player Stats Collection System is a comprehensive module for collecting, processing, and storing individual MLB player statistics using the MLB Stats API. This system handles both batting and pitching statistics, automatically creates missing player records, and integrates seamlessly with the existing MLB analytics platform.

## Features

### ✅ **Current Capabilities**
- **Automated Player Creation**: Automatically creates missing player records with full biographical data
- **Comprehensive Stats Collection**: Collects detailed batting and pitching statistics
- **Multi-Season Support**: Can collect historical data for multiple seasons (2023, 2024, 2025)
- **Daily Integration**: Integrates with daily collection workflow
- **Robust Error Handling**: Graceful handling of API failures and data inconsistencies
- **Database Integration**: Full SQLAlchemy ORM integration with existing database schema

### 📊 **Data Sources**
- **Primary**: MLB Stats API (statsapi.mlb.com)
- **Method**: Leaderboard-based collection for reliable data retrieval
- **Coverage**: All active MLB players with statistics

## Quick Start

### 1. Populate Players Table (One-time Setup)

Before collecting player stats, populate the players table to avoid foreign key constraints:

```bash
cd DataCollection
python populate_players.py
```

This script will:
- Identify players in stats tables missing from players table
- Fetch biographical data from MLB Stats API
- Create complete player records with names, birth info, physical attributes

### 2. Collect Current Season Stats

```bash
# Collect all current season player stats
python player_stats.py all

# Or collect specific categories
python player_stats.py batting
python player_stats.py pitching
```

### 3. Multi-Season Collection

```bash
# Use collector for multiple seasons
python collector.py multi-season 2023 2024 2025

# Or use default seasons (2023, 2024, 2025)
python collector.py multi-season
```

### 4. Daily Integration

Player stats are automatically included in daily collection:

```bash
python collector.py daily
```

## System Architecture

### Core Components

#### `player_stats.py` - Main Collection Module
- **PlayerStatsCollector Class**: Main orchestrator for all player stats operations
- **Auto-Player Creation**: `_ensure_player_exists()` method creates missing players
- **API Integration**: Direct MLB Stats API calls without external dependencies  
- **Database Mapping**: Converts API data to database schema format

#### `populate_players.py` - Initial Setup Script
- **Missing Player Detection**: Finds players in stats tables but not players table
- **Biographical Data Collection**: Fetches complete player information from MLB API
- **Batch Processing**: Handles large player populations efficiently

#### `collector.py` - Workflow Integration
- **Daily Collection**: Includes player stats in daily workflow
- **Multi-Season Support**: `run_multi_season_player_stats()` function
- **Command Line Interface**: Easy access to all collection modes

### Database Schema

The system populates these main tables:

#### `players` - Player Biographical Data
- Basic info (name, birth date, physical attributes)
- Career info (debut date, position, active status)
- Identifiers (MLB player ID, jersey number)

#### `player_batting_stats` - Batting Statistics
- Traditional stats (AVG, OBP, SLG, OPS)
- Advanced metrics (wOBA, wRC+, WAR, BABIP)
- Counting stats (hits, runs, RBIs, home runs)

#### `player_pitching_stats` - Pitching Statistics  
- Traditional stats (ERA, WHIP, wins, losses, saves)
- Rate stats (K/9, BB/9, HR/9, K/BB ratio)
- Advanced metrics (FIP, xFIP, WAR)

## API Integration

### MLB Stats API
- **Base URL**: `https://statsapi.mlb.com/api/v1/`
- **Authentication**: None required (public API)
- **Rate Limiting**: Built-in request delays to respect API limits
- **Data Format**: JSON responses with nested player/team/stat structures

### Key Endpoints Used
- `/stats` - Player statistics leaderboards
- `/people/{playerId}` - Individual player biographical data
- `/teams` - Team rosters and information

## Usage Examples

### Collect Current Season Stats
```python
from DataCollection.player_stats import collect_all_player_stats

# Collect current season
result = collect_all_player_stats()
print(f"Success: {result['overall_success']}")
print(f"Total changes: {result['total_inserted'] + result['total_updated']}")
```

### Multi-Season Collection
```python
from DataCollection.player_stats import PlayerStatsCollector

collector = PlayerStatsCollector()
result = collector.collect_multi_season_stats([2023, 2024])
print(f"Batting records: {result['batting_records']}")
print(f"Pitching records: {result['pitching_records']}")
```

### Ensure Player Exists
```python
from DataCollection.player_stats import PlayerStatsCollector

collector = PlayerStatsCollector()
# This will create the player if they don't exist
player_exists = collector._ensure_player_exists(660271)  # Example player ID
```

## Command Line Interface

### Available Commands

```bash
# Individual collection modes
python player_stats.py batting     # Batting stats only
python player_stats.py pitching    # Pitching stats only  
python player_stats.py all         # All player stats

# Multi-season collection
python collector.py multi-season 2023 2024 2025

# Daily collection (includes player stats)
python collector.py daily

# Initial setup
python populate_players.py
```

## Data Flow

### Collection Process
1. **API Request**: Query MLB Stats API leaderboards
2. **Player Verification**: Check if player exists in database
3. **Auto-Creation**: Create missing players with biographical data
4. **Data Mapping**: Convert API format to database schema
5. **Upsert Operation**: Insert new or update existing records
6. **Error Handling**: Log issues and continue processing

### Multi-Season Workflow
1. **Season Iteration**: Process each requested season
2. **Parallel Collection**: Collect batting and pitching stats
3. **Progress Tracking**: Log detailed progress and statistics
4. **Error Aggregation**: Collect and report all errors

## Configuration

### Default Settings
- **Seasons**: [2023, 2024, 2025] for multi-season collection
- **API Timeout**: 10 seconds per request
- **Batch Size**: 50 players per commit for population script
- **Retry Logic**: Automatic retries for API failures

### Customization Options
- Modify season list in `collect_multi_season_stats()`
- Adjust API timeout in `_make_api_request()`
- Configure logging levels in collection scripts

## Error Handling

### Robust Error Management
- **API Failures**: Graceful handling of network issues and API errors
- **Data Validation**: Safe conversion of API data types
- **Database Errors**: Transaction rollback on failures
- **Missing Data**: Intelligent defaults for incomplete API responses

### Logging and Monitoring
- **Structured Logging**: Detailed progress and error logs
- **Performance Metrics**: Collection timing and success rates
- **Error Classification**: Warning vs error level logging

## Performance

### Optimization Features
- **Leaderboard Approach**: More efficient than individual player queries
- **Batch Processing**: Commits in batches for better performance
- **Intelligent Caching**: Avoids unnecessary player creation checks
- **Minimal Dependencies**: Direct API calls without heavy libraries

### Expected Performance
- **Current Season**: ~200 player records in 30-60 seconds
- **Multi-Season**: ~600 records (3 seasons) in 2-3 minutes
- **Player Population**: ~3000+ players in 5-10 minutes

## Integration Points

### Daily Workflow Integration
- Player stats collection runs as part of `run_daily_collection()`
- Player status tracking included in daily updates
- Automatic season detection and collection

### Analytics Pipeline Integration  
- Direct database integration with existing analytics models
- Compatible with existing prediction and analysis systems
- Maintains referential integrity with games and team data

## Troubleshooting

### Common Issues

#### Foreign Key Constraints
```bash
# Solution: Run player population first
python populate_players.py
```

#### API Rate Limiting
- Built-in delays prevent most rate limiting
- Script automatically retries failed requests
- Consider running during off-peak hours for large collections

#### Missing Biographical Data
- Some players may have incomplete API data
- System creates records with available data only
- Check logs for specific missing data warnings

### Verification Commands

```bash
# Check missing players
python populate_players.py  # Shows missing count

# Verify collection results
python player_stats.py all  # Check success/error counts
```

## Future Enhancements

### Planned Features
- [ ] Advanced metrics integration (Statcast data)
- [ ] Minor league player support
- [ ] Historical season expansion (pre-2023)
- [ ] Real-time stat updates during games
- [ ] Player transaction history integration

### Enhancement Opportunities  
- [ ] Parallel processing for faster collection
- [ ] Data quality validation and cleanup
- [ ] Advanced error recovery mechanisms
- [ ] Performance monitoring dashboard

## Support

### Getting Help
1. Check logs for detailed error messages
2. Verify database connectivity and schema
3. Ensure MLB Stats API availability
4. Review the comprehensive logging output

### Contributing
When contributing to the player stats system:
1. Maintain the existing error handling patterns
2. Follow the logging conventions
3. Test with small data sets before full collection
4. Update this documentation for any new features

---

*This system is part of the comprehensive MLB Analytics Platform. For questions about integration with other system components, refer to the main project documentation.*