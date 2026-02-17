-- ================================================================================
-- MLB BETTING ANALYTICS PLATFORM - DATABASE SCHEMA
-- ================================================================================
--
-- Description: Comprehensive database schema for MLB betting analytics platform
--              supporting advanced sabermetrics, player analytics, and real-time
--              betting data integration
--
-- Version:     2.0
-- Created:     September 23, 2025
-- Updated:     October 9, 2025
-- Author:      MLB Analytics Team
--
-- Database:    PostgreSQL 14+
-- Extensions:  uuid-ossp, pg_stat_statements (recommended)
--
-- Schema Overview:
-- ├── Core Infrastructure Tables
-- │   ├── teams                    - MLB team master data
-- │   ├── games                    - Game schedules and results
-- │   └── audit_log               - Change tracking and compliance
-- │
-- ├── Player Analytics Tables
-- │   ├── players                 - Player master data
-- │   ├── player_batting_stats    - Individual batting performance
-- │   ├── player_pitching_stats   - Individual pitching performance
-- │   ├── player_matchups         - Pitcher vs batter history
-- │   └── player_matchup_summaries - Aggregated matchup data
-- │
-- ├── Team Analytics Tables
-- │   ├── team_stats              - Basic team performance
-- │   ├── advanced_team_pitching_metrics - Advanced pitching analytics
-- │   ├── advanced_team_batting_metrics  - Advanced batting analytics
-- │   ├── composite_team_metrics  - Combined team ratings
-- │   ├── team_statcast_aggregates - Statcast data aggregation
-- │   └── team_performance_trends - Momentum indicators
-- │
-- ├── Game Data Tables
-- │   ├── pitches                 - High-volume pitch-by-pitch data
-- │   ├── weather_conditions      - Game weather data
-- │   └── betting_odds           - Sportsbook odds and lines
-- │
-- └── Performance Optimization
--     ├── Indexes                 - Query optimization
--     ├── Constraints            - Data integrity
--     └── Statistics             - Query planner optimization
--
-- ================================================================================

-- ================================================================================
-- SECTION 1: DATABASE EXTENSIONS AND CONFIGURATION
-- ================================================================================

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set timezone for consistent timestamp handling
SET timezone = 'UTC';

-- ================================================================================
-- SECTION 2: CORE INFRASTRUCTURE TABLES
-- ================================================================================

-- Teams lookup table
-- Purpose: Master reference for all MLB teams with location data
CREATE TABLE IF NOT EXISTS teams (
    team_id             VARCHAR(3) PRIMARY KEY,
    team_name           VARCHAR(50) NOT NULL,
    city                VARCHAR(50) NOT NULL,
    stadium_name        VARCHAR(100) NOT NULL,
    latitude            DECIMAL(10,8) NOT NULL,
    longitude           DECIMAL(11,8) NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_teams_coordinates CHECK (
        latitude BETWEEN -90 AND 90 AND 
        longitude BETWEEN -180 AND 180
    )
);

-- Games table
-- Purpose: Core game schedule and results from MLB Statcast data
CREATE TABLE IF NOT EXISTS games (
    game_pk             BIGINT PRIMARY KEY,
    game_date           DATE NOT NULL,
    home_team_id        VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    away_team_id        VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    home_score          INTEGER,
    away_score          INTEGER,
    winner_team_id      VARCHAR(3) REFERENCES teams(team_id),
    game_status         VARCHAR(20) DEFAULT 'scheduled' NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_games_different_teams CHECK (home_team_id != away_team_id),
    CONSTRAINT chk_games_scores CHECK (
        (home_score IS NULL AND away_score IS NULL) OR 
        (home_score >= 0 AND away_score >= 0)
    ),
    CONSTRAINT chk_games_status CHECK (
        game_status IN ('scheduled', 'in_progress', 'completed', 'postponed', 'cancelled')
    )
);

-- Audit log table
-- Purpose: Security and compliance tracking for all data changes
CREATE TABLE IF NOT EXISTS audit_log (
    log_id              BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    table_name          VARCHAR(50) NOT NULL,
    operation           VARCHAR(10) NOT NULL,
    record_id           VARCHAR(100),
    old_values          JSONB,
    new_values          JSONB,
    changed_by          VARCHAR(100) DEFAULT 'system',
    changed_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_audit_operation CHECK (
        operation IN ('INSERT', 'UPDATE', 'DELETE')
    )
);

-- ================================================================================
-- SECTION 3: PLAYER ANALYTICS TABLES
-- ================================================================================
-- Players master table
-- Purpose: Comprehensive player biographical and career data
CREATE TABLE IF NOT EXISTS players (
    player_id               BIGINT PRIMARY KEY,
    fangraphs_id           VARCHAR(10) UNIQUE,
    baseball_reference_id   VARCHAR(10) UNIQUE,
    name_first             VARCHAR(50) NOT NULL,
    name_last              VARCHAR(50) NOT NULL,
    name_display           VARCHAR(100) NOT NULL,
    name_suffix            VARCHAR(10),
    birth_date             DATE,
    birth_country          VARCHAR(50),
    birth_state            VARCHAR(50),
    birth_city             VARCHAR(50),
    height_inches          INTEGER,
    weight_lbs             INTEGER,
    bats                   CHAR(1) CHECK (bats IN ('L', 'R', 'S')),
    throws                 CHAR(1) CHECK (throws IN ('L', 'R')),
    mlb_debut_date         DATE,
    final_game_date        DATE,
    is_active              BOOLEAN DEFAULT TRUE NOT NULL,
    primary_position       VARCHAR(5),
    jersey_number          INTEGER,
    current_team_id        VARCHAR(3) REFERENCES teams(team_id),
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_players_height CHECK (height_inches BETWEEN 60 AND 84),
    CONSTRAINT chk_players_weight CHECK (weight_lbs BETWEEN 140 AND 350),
    CONSTRAINT chk_players_jersey CHECK (jersey_number BETWEEN 0 AND 99),
    CONSTRAINT chk_players_debut_order CHECK (
        final_game_date IS NULL OR final_game_date >= mlb_debut_date
    ),
    UNIQUE(name_display, birth_date)
);

-- Player batting statistics by season
-- Purpose: Comprehensive batting performance metrics including Statcast data
CREATE TABLE IF NOT EXISTS player_batting_stats (
    id                      BIGSERIAL PRIMARY KEY,
    player_id               BIGINT NOT NULL REFERENCES players(player_id),
    team_id                 VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    season                  INTEGER NOT NULL,
    
    -- Basic counting statistics
    games                   INTEGER DEFAULT 0,
    plate_appearances       INTEGER DEFAULT 0,
    at_bats                 INTEGER DEFAULT 0,
    hits                    INTEGER DEFAULT 0,
    singles                 INTEGER DEFAULT 0,
    doubles                 INTEGER DEFAULT 0,
    triples                 INTEGER DEFAULT 0,
    home_runs               INTEGER DEFAULT 0,
    runs                    INTEGER DEFAULT 0,
    rbis                    INTEGER DEFAULT 0,
    walks                   INTEGER DEFAULT 0,
    intentional_walks       INTEGER DEFAULT 0,
    strikeouts              INTEGER DEFAULT 0,
    hit_by_pitch            INTEGER DEFAULT 0,
    sacrifice_flies         INTEGER DEFAULT 0,
    sacrifice_hits          INTEGER DEFAULT 0,
    grounded_into_dp        INTEGER DEFAULT 0,
    stolen_bases            INTEGER DEFAULT 0,
    caught_stealing         INTEGER DEFAULT 0,
    
    -- Traditional rate statistics
    batting_average         DECIMAL(4,3),
    on_base_percentage      DECIMAL(4,3),
    slugging_percentage     DECIMAL(4,3),
    ops                     DECIMAL(4,3),
    
    -- Advanced sabermetrics
    woba                    DECIMAL(4,3),       -- Weighted On-Base Average
    wraa                    DECIMAL(6,1),       -- Weighted Runs Above Average
    wrc                     INTEGER,            -- Weighted Runs Created
    wrc_plus                INTEGER,            -- Weighted Runs Created Plus (100 = league avg)
    war                     DECIMAL(4,1),       -- Wins Above Replacement
    iso                     DECIMAL(4,3),       -- Isolated Power
    babip                   DECIMAL(4,3),       -- Batting Average on Balls in Play
    
    -- Plate discipline metrics
    bb_percent              DECIMAL(5,2),       -- Walk percentage
    k_percent               DECIMAL(5,2),       -- Strikeout percentage
    bb_k_ratio              DECIMAL(4,2),       -- Walk to strikeout ratio
    
    -- Batted ball metrics
    gb_percent              DECIMAL(5,2),       -- Ground ball percentage
    fb_percent              DECIMAL(5,2),       -- Fly ball percentage
    ld_percent              DECIMAL(5,2),       -- Line drive percentage
    iffb_percent            DECIMAL(5,2),       -- Infield fly ball percentage
    hr_fb_ratio             DECIMAL(5,2),       -- Home run to fly ball ratio
    gb_fb_ratio             DECIMAL(4,2),       -- Ground ball to fly ball ratio
    
    -- Statcast metrics
    avg_exit_velocity       DECIMAL(4,1),       -- Average exit velocity (mph)
    max_exit_velocity       DECIMAL(4,1),       -- Maximum exit velocity (mph)
    hard_hit_percent        DECIMAL(5,2),       -- Hard hit percentage (95+ mph)
    barrel_percent          DECIMAL(5,2),       -- Barrel percentage
    avg_launch_angle        DECIMAL(4,1),       -- Average launch angle (degrees)
    sweet_spot_percent      DECIMAL(5,2),       -- Sweet spot percentage (8-32 degrees)
    
    -- Situational performance
    risp_avg                DECIMAL(4,3),       -- Runners in scoring position average
    bases_loaded_avg        DECIMAL(4,3),       -- Bases loaded average
    two_outs_avg            DECIMAL(4,3),       -- Two outs average
    clutch                  DECIMAL(5,2),       -- Clutch performance metric
    
    -- Positional information
    primary_position        VARCHAR(5),
    games_by_position       TEXT,               -- JSON format for position flexibility
    
    -- Metadata
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_batting_season CHECK (season BETWEEN 1871 AND 2050),
    CONSTRAINT chk_batting_games CHECK (games >= 0 AND games <= 200),
    CONSTRAINT chk_batting_pa_ab CHECK (plate_appearances >= at_bats),
    CONSTRAINT chk_batting_percentages CHECK (
        bb_percent BETWEEN 0 AND 100 AND
        k_percent BETWEEN 0 AND 100 AND
        hard_hit_percent BETWEEN 0 AND 100
    ),
    UNIQUE(player_id, season, team_id)
);

-- Player pitching statistics by season  
CREATE TABLE IF NOT EXISTS player_pitching_stats (
    id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL REFERENCES players(player_id),
    team_id VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    season INTEGER NOT NULL,
    
    -- Basic counting stats
    games INTEGER DEFAULT 0,
    games_started INTEGER DEFAULT 0,
    complete_games INTEGER DEFAULT 0,
    shutouts INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    blown_saves INTEGER DEFAULT 0,
    holds INTEGER DEFAULT 0,
    innings_pitched DECIMAL(5,1),
    batters_faced INTEGER DEFAULT 0,
    hits_allowed INTEGER DEFAULT 0,
    runs_allowed INTEGER DEFAULT 0,
    earned_runs_allowed INTEGER DEFAULT 0,
    home_runs_allowed INTEGER DEFAULT 0,
    walks_allowed INTEGER DEFAULT 0,
    intentional_walks_allowed INTEGER DEFAULT 0,
    strikeouts INTEGER DEFAULT 0,
    hit_batsmen INTEGER DEFAULT 0,
    wild_pitches INTEGER DEFAULT 0,
    balks INTEGER DEFAULT 0,
    
    -- Traditional rate stats
    era DECIMAL(4,2),
    whip DECIMAL(4,2),
    
    -- Advanced sabermetrics
    fip DECIMAL(4,2),
    xfip DECIMAL(4,2),
    siera DECIMAL(4,2),
    war DECIMAL(4,1),
    
    -- Rate metrics
    k_per_9 DECIMAL(4,2),
    bb_per_9 DECIMAL(4,2),
    hr_per_9 DECIMAL(4,2),
    k_bb_ratio DECIMAL(4,2),
    h_per_9 DECIMAL(4,2),
    
    -- Percentage metrics
    bb_percent DECIMAL(5,2),
    k_percent DECIMAL(5,2),
    k_minus_bb_percent DECIMAL(5,2),
    
    -- Batted ball metrics
    gb_percent DECIMAL(5,2),
    fb_percent DECIMAL(5,2),
    ld_percent DECIMAL(5,2),
    iffb_percent DECIMAL(5,2),
    hr_fb_ratio DECIMAL(5,2),
    babip_against DECIMAL(4,3),
    lob_percent DECIMAL(5,2),
    
    -- Stuff+ metrics
    stuff_plus INTEGER,
    location_plus INTEGER,
    pitching_plus INTEGER,
    
    -- Pitch mix percentages
    fastball_percent DECIMAL(5,2),
    sinker_percent DECIMAL(5,2),
    cutter_percent DECIMAL(5,2),
    slider_percent DECIMAL(5,2),
    curveball_percent DECIMAL(5,2),
    changeup_percent DECIMAL(5,2),
    splitter_percent DECIMAL(5,2),
    knuckleball_percent DECIMAL(5,2),
    
    -- Velocity metrics
    avg_fastball_velocity DECIMAL(4,1),
    max_velocity DECIMAL(4,1),
    
    -- Role information
    starter_reliever VARCHAR(10) CHECK (starter_reliever IN ('SP', 'RP', 'CL')),
    leverage_index DECIMAL(4,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player_id, season, team_id)
);

-- Historical pitcher vs batter matchups
CREATE TABLE IF NOT EXISTS player_matchups (
    id BIGSERIAL PRIMARY KEY,
    pitcher_id BIGINT NOT NULL REFERENCES players(player_id),
    batter_id BIGINT NOT NULL REFERENCES players(player_id),
    
    -- Overall matchup stats (all-time)
    total_plate_appearances INTEGER DEFAULT 0,
    total_at_bats INTEGER DEFAULT 0,
    total_hits INTEGER DEFAULT 0,
    total_singles INTEGER DEFAULT 0,
    total_doubles INTEGER DEFAULT 0,
    total_triples INTEGER DEFAULT 0,
    total_home_runs INTEGER DEFAULT 0,
    total_walks INTEGER DEFAULT 0,
    total_strikeouts INTEGER DEFAULT 0,
    total_hit_by_pitch INTEGER DEFAULT 0,
    
    -- Calculated rates (all-time)
    batting_average DECIMAL(4,3),
    on_base_percentage DECIMAL(4,3),
    slugging_percentage DECIMAL(4,3),
    ops DECIMAL(4,3),
    
    -- Recent performance (last 2 seasons)
    recent_plate_appearances INTEGER DEFAULT 0,
    recent_at_bats INTEGER DEFAULT 0,
    recent_hits INTEGER DEFAULT 0,
    recent_home_runs INTEGER DEFAULT 0,
    recent_walks INTEGER DEFAULT 0,
    recent_strikeouts INTEGER DEFAULT 0,
    recent_batting_average DECIMAL(4,3),
    recent_ops DECIMAL(4,3),
    
    -- Situational splits
    risp_plate_appearances INTEGER DEFAULT 0,
    risp_hits INTEGER DEFAULT 0,
    risp_batting_average DECIMAL(4,3),
    
    two_strikes_plate_appearances INTEGER DEFAULT 0,
    two_strikes_strikeouts INTEGER DEFAULT 0,
    two_strikes_contact_rate DECIMAL(5,2),
    
    -- Platoon context
    same_handedness BOOLEAN,
    platoon_advantage VARCHAR(10) CHECK (platoon_advantage IN ('pitcher', 'batter', 'neutral')),
    
    -- Performance indicators
    dominance_score DECIMAL(5,2),
    contact_quality_score DECIMAL(5,2),
    
    -- Data quality and recency
    last_matchup_date DATE,
    total_seasons_faced INTEGER DEFAULT 0,
    confidence_level VARCHAR(10) CHECK (confidence_level IN ('high', 'medium', 'low', 'very_low')),
    
    -- Metadata
    last_updated DATE DEFAULT CURRENT_DATE,
    data_source VARCHAR(20) DEFAULT 'statcast',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(pitcher_id, batter_id)
);

-- Player matchup summaries for quick lookups
CREATE TABLE IF NOT EXISTS player_matchup_summaries (
    id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL REFERENCES players(player_id),
    season INTEGER NOT NULL,
    
    -- Performance vs different handedness
    vs_lhp_plate_appearances INTEGER DEFAULT 0,
    vs_lhp_batting_average DECIMAL(4,3),
    vs_lhp_ops DECIMAL(4,3),
    vs_lhp_woba DECIMAL(4,3),
    
    vs_rhp_plate_appearances INTEGER DEFAULT 0,
    vs_rhp_batting_average DECIMAL(4,3),
    vs_rhp_ops DECIMAL(4,3),
    vs_rhp_woba DECIMAL(4,3),
    
    -- Platoon differential
    platoon_split_ops DECIMAL(4,3),
    platoon_advantage_type VARCHAR(20) CHECK (platoon_advantage_type IN ('normal', 'reverse', 'extreme')),
    
    -- Performance vs quality of pitching
    vs_elite_pitchers_pa INTEGER DEFAULT 0,
    vs_elite_pitchers_ops DECIMAL(4,3),
    
    vs_poor_pitchers_pa INTEGER DEFAULT 0,
    vs_poor_pitchers_ops DECIMAL(4,3),
    
    -- Situational performance
    high_leverage_pa INTEGER DEFAULT 0,
    high_leverage_ops DECIMAL(4,3),
    
    clutch_performance_score DECIMAL(5,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player_id, season)
);

-- ================================================================================
-- SECTION 3.5: PLAYER TRANSACTIONS AND INJURY TRACKING TABLES
-- ================================================================================

-- MLB Transactions table
-- Purpose: Raw transaction data from MLB Stats API for complete audit trail
CREATE TABLE IF NOT EXISTS mlb_transactions (
    transaction_id          BIGSERIAL PRIMARY KEY,
    mlb_transaction_id      BIGINT UNIQUE NOT NULL,    -- MLB's official transaction ID
    player_id               BIGINT NOT NULL REFERENCES players(player_id),
    from_team_id            VARCHAR(3) REFERENCES teams(team_id),
    to_team_id              VARCHAR(3) REFERENCES teams(team_id),
    transaction_date        DATE NOT NULL,
    effective_date          DATE,
    resolution_date         DATE,
    type_code              VARCHAR(10) NOT NULL,       -- SC, AS, etc.
    type_description       VARCHAR(50) NOT NULL,       -- Status Change, Assigned, etc.
    description            TEXT NOT NULL,              -- Full human-readable description
    
    -- Transaction categorization
    is_trade               BOOLEAN DEFAULT FALSE,
    is_injury_related      BOOLEAN DEFAULT FALSE,
    is_roster_move         BOOLEAN DEFAULT FALSE,
    
    -- Processing metadata
    processed_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_source           VARCHAR(20) DEFAULT 'mlb_stats_api',
    
    -- Constraints
    CONSTRAINT chk_mlb_trans_dates CHECK (
        effective_date IS NULL OR effective_date >= transaction_date
    ),
    CONSTRAINT chk_mlb_trans_teams CHECK (
        from_team_id IS DISTINCT FROM to_team_id OR 
        (from_team_id IS NULL AND to_team_id IS NOT NULL) OR
        (from_team_id IS NOT NULL AND to_team_id IS NULL)
    )
);

-- Player Team History table
-- Purpose: Clean chronological record of player team affiliations
CREATE TABLE IF NOT EXISTS player_team_history (
    history_id              BIGSERIAL PRIMARY KEY,
    player_id               BIGINT NOT NULL REFERENCES players(player_id),
    team_id                 VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    start_date              DATE NOT NULL,
    end_date                DATE,                       -- NULL = current team
    
    -- Transaction context
    start_transaction_id    BIGINT REFERENCES mlb_transactions(transaction_id),
    end_transaction_id      BIGINT REFERENCES mlb_transactions(transaction_id),
    transaction_type        VARCHAR(30),                -- 'trade', 'free_agent', 'draft', 'waiver_claim'
    
    -- Status tracking
    is_active               BOOLEAN DEFAULT TRUE,
    primary_position        VARCHAR(5),
    jersey_number           INTEGER,
    
    -- Metadata
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_team_history_dates CHECK (
        end_date IS NULL OR end_date >= start_date
    ),
    CONSTRAINT chk_team_history_jersey CHECK (
        jersey_number IS NULL OR jersey_number BETWEEN 0 AND 99
    ),
    CONSTRAINT chk_team_history_transaction_type CHECK (
        transaction_type IN ('trade', 'free_agent', 'draft', 'waiver_claim', 
                            'purchase', 'rule_5', 'expansion_draft', 'other')
    )
);

-- Player Injuries table
-- Purpose: Track injury periods and IL designations
CREATE TABLE IF NOT EXISTS player_injuries (
    injury_id               BIGSERIAL PRIMARY KEY,
    player_id               BIGINT NOT NULL REFERENCES players(player_id),
    team_id                 VARCHAR(3) REFERENCES teams(team_id),
    
    -- Injury details
    injury_type             VARCHAR(100),               -- 'elbow tendinitis', 'hamstring strain'
    body_part               VARCHAR(50),                -- 'elbow', 'hamstring', 'shoulder'
    severity                VARCHAR(20),                -- 'minor', 'moderate', 'major'
    
    -- IL designation
    il_designation          VARCHAR(20),                -- '10-day IL', '15-day IL', '60-day IL'
    il_placement_date       DATE,
    il_eligibility_date     DATE,                       -- Earliest return date
    
    -- Timeline tracking
    injury_date             DATE,                       -- When injury occurred
    reported_date           DATE,                       -- When injury was reported
    expected_return_date    DATE,                       -- Initial projection
    actual_return_date      DATE,                       -- Actual return
    
    -- Status
    status                  VARCHAR(20) DEFAULT 'active', -- 'active', 'returned', 'extended', 'season_ending'
    
    -- Related transactions
    placement_transaction_id BIGINT REFERENCES mlb_transactions(transaction_id),
    return_transaction_id   BIGINT REFERENCES mlb_transactions(transaction_id),
    
    -- Performance impact tracking
    games_missed            INTEGER DEFAULT 0,
    at_bats_lost           INTEGER DEFAULT 0,
    innings_lost           DECIMAL(5,1) DEFAULT 0,
    
    -- Metadata
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_injury_status CHECK (
        status IN ('active', 'returned', 'extended', 'season_ending', 'retired')
    ),
    CONSTRAINT chk_injury_il_designation CHECK (
        il_designation IN ('10-day IL', '15-day IL', '60-day IL', 'restricted list', 'suspended list')
    ),
    CONSTRAINT chk_injury_dates CHECK (
        reported_date >= injury_date AND
        (actual_return_date IS NULL OR actual_return_date >= il_placement_date)
    )
);

-- Daily Player Status table
-- Purpose: Daily availability and roster status for prediction models
CREATE TABLE IF NOT EXISTS daily_player_status (
    status_id               BIGSERIAL PRIMARY KEY,
    player_id               BIGINT NOT NULL REFERENCES players(player_id),
    team_id                 VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    status_date             DATE NOT NULL,
    
    -- Roster status
    roster_status           VARCHAR(20) NOT NULL,       -- 'active', 'injured', 'suspended', 'optioned'
    roster_designation      VARCHAR(30),                -- '40-man', '26-man', 'taxi_squad'
    
    -- Availability assessment
    availability_status     VARCHAR(20) DEFAULT 'available', -- 'available', 'questionable', 'doubtful', 'out'
    availability_score      DECIMAL(3,2) DEFAULT 1.00,  -- 0.0-1.0 probability of playing
    
    -- Context factors
    is_probable_starter     BOOLEAN DEFAULT FALSE,      -- For pitchers
    rest_days               INTEGER DEFAULT 0,          -- Days since last appearance
    workload_status         VARCHAR(20),                -- 'normal', 'high', 'rest_needed'
    
    -- Injury context
    injury_designation      VARCHAR(30),                -- Current IL status if any
    return_probability      DECIMAL(3,2),               -- Probability of return if injured
    
    -- Game context
    is_home_game           BOOLEAN,
    opponent_team_id       VARCHAR(3) REFERENCES teams(team_id),
    game_importance        DECIMAL(3,2),                -- 0.0-1.0 importance factor
    
    -- Metadata
    last_updated           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_confidence        DECIMAL(3,2) DEFAULT 0.95,   -- Confidence in availability data
    
    -- Constraints
    CONSTRAINT chk_daily_status_availability_score CHECK (
        availability_score BETWEEN 0 AND 1
    ),
    CONSTRAINT chk_daily_status_return_prob CHECK (
        return_probability IS NULL OR return_probability BETWEEN 0 AND 1
    ),
    CONSTRAINT chk_daily_status_roster CHECK (
        roster_status IN ('active', 'injured', 'suspended', 'optioned', 'designated', 'restricted')
    ),
    CONSTRAINT chk_daily_status_availability CHECK (
        availability_status IN ('available', 'questionable', 'doubtful', 'out', 'unknown')
    ),
    
    UNIQUE(player_id, status_date)
);

-- Player Trade Impact table
-- Purpose: Track performance changes around trades for analysis
CREATE TABLE IF NOT EXISTS player_trade_impact (
    impact_id               BIGSERIAL PRIMARY KEY,
    player_id               BIGINT NOT NULL REFERENCES players(player_id),
    trade_transaction_id    BIGINT NOT NULL REFERENCES mlb_transactions(transaction_id),
    from_team_id            VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    to_team_id              VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    trade_date              DATE NOT NULL,
    season                  INTEGER NOT NULL,
    
    -- Performance periods (games before/after trade)
    pre_trade_games         INTEGER DEFAULT 0,
    post_trade_games        INTEGER DEFAULT 0,
    
    -- Batting impact (if position player)
    pre_trade_avg           DECIMAL(4,3),
    post_trade_avg          DECIMAL(4,3),
    pre_trade_ops           DECIMAL(4,3),
    post_trade_ops          DECIMAL(4,3),
    pre_trade_wrc_plus      INTEGER,
    post_trade_wrc_plus     INTEGER,
    
    -- Pitching impact (if pitcher)
    pre_trade_era           DECIMAL(4,2),
    post_trade_era          DECIMAL(4,2),
    pre_trade_whip          DECIMAL(4,2),
    post_trade_whip         DECIMAL(4,2),
    pre_trade_fip           DECIMAL(4,2),
    post_trade_fip          DECIMAL(4,2),
    
    -- Context factors
    ballpark_factor_change  DECIMAL(4,3),               -- Park effects difference
    league_change           BOOLEAN DEFAULT FALSE,      -- AL/NL change
    role_change             VARCHAR(50),                -- Position/role changes
    
    -- Statistical significance
    sample_size_adequate    BOOLEAN DEFAULT FALSE,      -- Enough games for analysis
    performance_change_pct  DECIMAL(6,2),               -- Overall performance change %
    
    -- Metadata
    calculated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_trade_impact_season CHECK (season BETWEEN 1871 AND 2050),
    CONSTRAINT chk_trade_impact_games CHECK (
        pre_trade_games >= 0 AND post_trade_games >= 0
    )
);

-- ================================================================================
-- 6.4 TABLE COMMENTS AND DOCUMENTATION
-- ================================================================================

-- Table documentation
COMMENT ON TABLE teams IS 
    'Master reference table for all MLB teams with geographic location data';
COMMENT ON TABLE games IS 
    'Core game schedule and results from MLB Statcast data integration';
COMMENT ON TABLE players IS 
    'Comprehensive player biographical and career information with external ID mappings';
COMMENT ON TABLE player_batting_stats IS 
    'Season-by-season batting statistics including traditional, advanced, and Statcast metrics';
COMMENT ON TABLE player_pitching_stats IS 
    'Season-by-season pitching statistics with advanced sabermetrics and pitch mix data';
COMMENT ON TABLE player_matchups IS 
    'Historical pitcher vs batter matchup performance with confidence scoring';
COMMENT ON TABLE player_matchup_summaries IS 
    'Aggregated matchup performance summaries by player and season for quick lookups';
COMMENT ON TABLE pitches IS 
    'High-volume pitch-by-pitch Statcast data (740k+ records per season)';
COMMENT ON TABLE weather_conditions IS 
    'Game weather data integration from OpenWeatherMap API';
COMMENT ON TABLE betting_odds IS 
    'Real-time sportsbook odds and line movement tracking from The Odds API';
COMMENT ON TABLE audit_log IS 
    'Security and compliance tracking for all data changes';

-- New table documentation for transactions and injuries
COMMENT ON TABLE mlb_transactions IS 
    'Raw transaction data from MLB Stats API with complete audit trail and categorization';
COMMENT ON TABLE player_team_history IS 
    'Clean chronological record of player team affiliations with transaction references';
COMMENT ON TABLE player_injuries IS 
    'Comprehensive injury tracking including IL designations and performance impact';
COMMENT ON TABLE daily_player_status IS 
    'Daily availability and roster status for prediction models and analytics';
COMMENT ON TABLE player_trade_impact IS 
    'Performance analysis before and after trades for impact assessment';

-- Key column documentation
COMMENT ON COLUMN players.player_id IS 
    'MLB Statcast player ID - primary identifier for data integration';
COMMENT ON COLUMN players.fangraphs_id IS 
    'FanGraphs player ID for advanced analytics integration';
COMMENT ON COLUMN players.baseball_reference_id IS 
    'Baseball Reference player ID for historical data integration';
COMMENT ON COLUMN players.bats IS 
    'Batting handedness: L=Left, R=Right, S=Switch hitter';
COMMENT ON COLUMN players.throws IS 
    'Throwing handedness: L=Left, R=Right';

COMMENT ON COLUMN player_batting_stats.wrc_plus IS 
    'Weighted Runs Created Plus - 100 represents league average performance';
COMMENT ON COLUMN player_batting_stats.war IS 
    'Wins Above Replacement - player value metric';
COMMENT ON COLUMN player_batting_stats.woba IS 
    'Weighted On-Base Average - comprehensive offensive metric';

COMMENT ON COLUMN player_pitching_stats.stuff_plus IS 
    'Stuff+ rating - 100 represents league average pitch quality';
COMMENT ON COLUMN player_pitching_stats.location_plus IS 
    'Location+ rating - 100 represents league average command';
COMMENT ON COLUMN player_pitching_stats.pitching_plus IS 
    'Combined Pitching+ rating - 100 represents league average overall pitching';

COMMENT ON COLUMN player_matchups.dominance_score IS 
    'Pitcher dominance metric: negative values favor batter performance';
COMMENT ON COLUMN player_matchups.confidence_level IS 
    'Sample size reliability: high (20+ PA), medium (10-19), low (5-9), very_low (<5)';

-- ================================================================================
-- 6.5 STATISTICS UPDATE FOR QUERY OPTIMIZATION
-- ================================================================================

-- Update table statistics for PostgreSQL query optimizer
ANALYZE teams;
ANALYZE games;
ANALYZE players;
ANALYZE player_batting_stats;
ANALYZE player_pitching_stats;
ANALYZE player_matchups;
ANALYZE player_matchup_summaries;
ANALYZE pitches;
ANALYZE team_stats;
ANALYZE weather_conditions;
ANALYZE betting_odds;
ANALYZE audit_log;

-- Update statistics for new transaction and injury tables
ANALYZE mlb_transactions;
ANALYZE player_team_history;
ANALYZE player_injuries;
ANALYZE daily_player_status;
ANALYZE player_trade_impact;

-- ================================================================================
-- SCHEMA DEPLOYMENT COMPLETE
-- ================================================================================

/*
DEPLOYMENT VERIFICATION CHECKLIST:
□ All tables created successfully
□ All constraints and indexes applied
□ Foreign key relationships established
□ Comments and documentation added
□ Statistics updated for query optimization
□ Connection test passed
□ Sample data insertion test (optional)

PERFORMANCE NOTES:
- Estimated total schema size: ~600MB per season with full data
- Pitches table will be largest component (~500MB per season)
- Indexes optimized for common query patterns
- Partial indexes used for conditional optimization
- Full-text search enabled for team and weather data

MAINTENANCE SCHEDULE:
- Weekly REINDEX during off-season
- ANALYZE after bulk data loads
- Monitor pg_stat_user_indexes for usage patterns
- Review slow query log quarterly

For support and documentation: See project README.md
*/

-- ================================================================================
-- SECTION 4: GAME DATA TABLES
-- ================================================================================

-- Pitches table
-- Purpose: High-volume pitch-by-pitch Statcast data (740k+ records per season)
CREATE TABLE IF NOT EXISTS pitches (
    pitch_id                BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    game_pk                 BIGINT NOT NULL REFERENCES games(game_pk),
    pitcher_id              BIGINT NOT NULL,
    batter_id               BIGINT NOT NULL,
    inning                  INTEGER NOT NULL,
    pitch_type              VARCHAR(5),
    release_speed           DECIMAL(4,1),
    events                  VARCHAR(50),
    description             VARCHAR(50),
    home_score              INTEGER NOT NULL DEFAULT 0,
    away_score              INTEGER NOT NULL DEFAULT 0,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_pitches_inning CHECK (inning BETWEEN 1 AND 20),
    CONSTRAINT chk_pitches_speed CHECK (release_speed BETWEEN 40 AND 110),
    CONSTRAINT chk_pitches_scores CHECK (home_score >= 0 AND away_score >= 0)
);

-- Weather conditions table
-- Purpose: Game weather data from OpenWeatherMap API
CREATE TABLE IF NOT EXISTS weather_conditions (
    weather_id              BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    game_pk                 BIGINT NOT NULL REFERENCES games(game_pk),
    game_time               TIMESTAMP NOT NULL,
    temperature             DECIMAL(4,1),          -- Fahrenheit
    humidity                INTEGER,               -- Percentage
    wind_speed              DECIMAL(4,1),          -- MPH
    wind_direction          VARCHAR(3),            -- Cardinal direction
    conditions              VARCHAR(50),           -- Weather description
    pressure                DECIMAL(5,2),          -- Inches of mercury
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_weather_temperature CHECK (temperature BETWEEN -20 AND 120),
    CONSTRAINT chk_weather_humidity CHECK (humidity BETWEEN 0 AND 100),
    CONSTRAINT chk_weather_wind_speed CHECK (wind_speed BETWEEN 0 AND 80),
    CONSTRAINT chk_weather_pressure CHECK (pressure BETWEEN 28 AND 32),
    UNIQUE(game_pk)
);

-- Betting odds table
-- Purpose: Real-time sportsbook odds and line movement tracking
CREATE TABLE IF NOT EXISTS betting_odds (
    odds_id                 BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    game_pk                 BIGINT NOT NULL REFERENCES games(game_pk),
    sportsbook              VARCHAR(50) NOT NULL,
    home_team_id            VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    away_team_id            VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    home_moneyline          INTEGER,               -- American odds format
    away_moneyline          INTEGER,               -- American odds format
    odds_timestamp          TIMESTAMP NOT NULL,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_betting_moneylines CHECK (
        (home_moneyline IS NULL AND away_moneyline IS NULL) OR
        (home_moneyline BETWEEN -10000 AND 10000 AND away_moneyline BETWEEN -10000 AND 10000)
    ),
    UNIQUE(game_pk, sportsbook, odds_timestamp)
);

-- ================================================================================
-- SECTION 5: TEAM ANALYTICS TABLES
-- ================================================================================

-- Team stats table
-- Purpose: Basic season performance metrics for teams
CREATE TABLE IF NOT EXISTS team_stats (
    stat_id                 BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    team_id                 VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    season                  INTEGER NOT NULL,
    games_played            INTEGER DEFAULT 0,
    runs_scored             INTEGER DEFAULT 0,
    runs_allowed            INTEGER DEFAULT 0,
    batting_avg             DECIMAL(4,3),
    era                     DECIMAL(4,2),
    ops                     DECIMAL(4,3),
    whip                    DECIMAL(4,2),
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_team_stats_season CHECK (season BETWEEN 1871 AND 2050),
    CONSTRAINT chk_team_stats_games CHECK (games_played BETWEEN 0 AND 200),
    CONSTRAINT chk_team_stats_runs CHECK (runs_scored >= 0 AND runs_allowed >= 0),
    UNIQUE(team_id, season)
);

-- ================================================================================
-- SECTION 6: PERFORMANCE OPTIMIZATION
-- ================================================================================

-- ================================================================================
-- 6.1 PRIMARY LOOKUP INDEXES (Critical for Performance)
-- ================================================================================

-- Advanced Team Pitching Metrics
CREATE TABLE advanced_team_pitching_metrics (
    metric_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    team_id VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    season INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    
    -- Traditional stats
    era DECIMAL(4,2),
    whip DECIMAL(4,2),
    
    -- Advanced sabermetric stats
    fip DECIMAL(4,2),                    -- Fielding Independent Pitching
    xfip DECIMAL(4,2),                   -- Expected FIP
    siera DECIMAL(4,2),                  -- Skill-Interactive ERA
    k_percent DECIMAL(5,2),              -- Strikeout percentage
    bb_percent DECIMAL(5,2),             -- Walk percentage  
    k_bb_percent DECIMAL(5,2),           -- K-BB percentage
    hr_9 DECIMAL(4,2),                   -- Home runs per 9 innings
    
    -- Advanced metrics (100 = league average)
    stuff_plus INTEGER,                  -- Stuff+ rating
    location_plus INTEGER,               -- Location+ rating
    pitching_plus INTEGER,               -- Overall Pitching+ rating
    era_minus INTEGER,                   -- ERA- (lower is better)
    fip_minus INTEGER,                   -- FIP- (lower is better)
    
    -- Statcast aggregates (against this team's pitching)
    avg_exit_velocity_against DECIMAL(4,1),     -- Average exit velocity allowed
    hard_hit_percent_against DECIMAL(5,2),      -- Hard hit rate allowed
    barrel_percent_against DECIMAL(5,2),        -- Barrel rate allowed
    avg_launch_angle_against DECIMAL(4,1),      -- Average launch angle allowed
    
    -- Metadata
    games_analyzed INTEGER,
    data_quality_score DECIMAL(3,2),    -- 0.0 to 1.0 quality score
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(team_id, season, as_of_date)
);

-- Advanced Team Batting Metrics  
CREATE TABLE advanced_team_batting_metrics (
    metric_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    team_id VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    season INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    
    -- Traditional stats
    avg DECIMAL(4,3),                    -- Batting average
    obp DECIMAL(4,3),                    -- On-base percentage
    slg DECIMAL(4,3),                    -- Slugging percentage
    ops DECIMAL(4,3),                    -- OPS
    
    -- Advanced sabermetric stats
    woba DECIMAL(4,3),                   -- Weighted On-Base Average
    wrc_plus INTEGER,                    -- Weighted Runs Created Plus (100 = average)
    iso DECIMAL(4,3),                    -- Isolated Power (SLG - AVG)
    babip DECIMAL(4,3),                  -- Batting Average on Balls in Play
    bb_percent DECIMAL(5,2),             -- Walk percentage
    k_percent DECIMAL(5,2),              -- Strikeout percentage
    
    -- Statcast metrics
    avg_exit_velocity DECIMAL(4,1),      -- Average exit velocity
    hard_hit_percent DECIMAL(5,2),       -- Hard hit percentage (95+ mph)
    barrel_percent DECIMAL(5,2),         -- Barrel percentage
    avg_launch_angle DECIMAL(4,1),       -- Average launch angle
    max_exit_velocity DECIMAL(4,1),      -- Maximum exit velocity
    
    -- Expected stats (based on Statcast data)
    xba DECIMAL(4,3),                    -- Expected batting average
    xslg DECIMAL(4,3),                   -- Expected slugging
    xwoba DECIMAL(4,3),                  -- Expected wOBA
    
    -- Metadata
    games_analyzed INTEGER,
    batted_balls_analyzed INTEGER,       -- Number of batted balls in Statcast data
    data_quality_score DECIMAL(3,2),    -- 0.0 to 1.0 quality score
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(team_id, season, as_of_date)
);

-- Composite Team Metrics (derived from pitching + batting)
CREATE TABLE composite_team_metrics (
    composite_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    team_id VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    season INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    
    -- Reference to component metrics
    pitching_metric_id BIGINT REFERENCES advanced_team_pitching_metrics(metric_id),
    batting_metric_id BIGINT REFERENCES advanced_team_batting_metrics(metric_id),
    
    -- Derived composite scores (0-10 scale)
    run_prevention_score DECIMAL(4,2),   -- Pitching effectiveness score
    run_creation_score DECIMAL(4,2),     -- Offensive effectiveness score  
    overall_team_rating DECIMAL(4,2),    -- Combined team rating
    
    -- Specialized ratings (0-10 scale)
    power_rating DECIMAL(4,2),           -- Exit velocity + barrel rate
    contact_quality DECIMAL(4,2),        -- Hard hit % + contact skills
    pitching_quality DECIMAL(4,2),       -- Stuff + command + results
    
    -- Market performance indicators
    expectation_differential DECIMAL(5,2), -- Actual vs expected performance gap
    clutch_performance DECIMAL(4,2),       -- Performance in high-leverage situations
    
    -- Metadata
    calculation_method VARCHAR(50),       -- Method used for calculations
    confidence_score DECIMAL(3,2),       -- Confidence in these metrics (0-1)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(team_id, season, as_of_date)
);

-- Team Statcast Aggregates (rolling windows)
CREATE TABLE team_statcast_aggregates (
    aggregate_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    team_id VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    season INTEGER NOT NULL,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    
    -- Offensive Statcast metrics
    avg_exit_velocity DECIMAL(4,1),
    max_exit_velocity DECIMAL(4,1),
    avg_launch_angle DECIMAL(4,1),
    hard_hit_count INTEGER,
    total_batted_balls INTEGER,
    hard_hit_percentage DECIMAL(5,2),
    barrel_count INTEGER,
    barrel_percentage DECIMAL(5,2),
    
    -- Expected performance
    expected_ba DECIMAL(4,3),
    expected_slg DECIMAL(4,3),
    expected_woba DECIMAL(4,3),
    
    -- Pitching Statcast metrics (when this team is pitching)
    opp_avg_exit_velocity DECIMAL(4,1),
    opp_hard_hit_percentage DECIMAL(5,2),
    opp_barrel_percentage DECIMAL(5,2),
    
    -- Metadata
    games_included INTEGER,
    pitches_analyzed INTEGER,
    batted_balls_analyzed INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(team_id, season, date_range_start, date_range_end)
);

-- Team Performance Trends (for momentum analysis)
CREATE TABLE team_performance_trends (
    trend_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    team_id VARCHAR(3) NOT NULL REFERENCES teams(team_id),
    season INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    
    -- Recent performance windows
    last_5_games_wl_pct DECIMAL(4,3),    -- Last 5 games win %
    last_10_games_wl_pct DECIMAL(4,3),   -- Last 10 games win %
    last_20_games_wl_pct DECIMAL(4,3),   -- Last 20 games win %
    
    -- Trend indicators
    run_differential_trend DECIMAL(5,2), -- Runs/game trend (positive = improving)
    pitching_trend DECIMAL(5,2),         -- ERA trend 
    offensive_trend DECIMAL(5,2),        -- wOBA trend
    
    -- Situational performance
    home_wl_pct DECIMAL(4,3),
    away_wl_pct DECIMAL(4,3),
    vs_above_500_pct DECIMAL(4,3),       -- vs teams with winning record
    vs_division_pct DECIMAL(4,3),        -- vs division opponents
    
    -- Rest and fatigue indicators
    avg_rest_days DECIMAL(3,1),
    back_to_back_record VARCHAR(10),     -- "3-2" format
    travel_games_record VARCHAR(10),     -- Record in games after travel
    
    -- Momentum indicators
    current_streak INTEGER,              -- Current win/loss streak (+ = wins, - = losses)
    longest_win_streak INTEGER,
    longest_loss_streak INTEGER,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(team_id, season, as_of_date)
);

-- Indexes for performance
CREATE INDEX idx_advanced_pitching_team_season ON advanced_team_pitching_metrics(team_id, season);
CREATE INDEX idx_advanced_pitching_date ON advanced_team_pitching_metrics(as_of_date);

CREATE INDEX idx_advanced_batting_team_season ON advanced_team_batting_metrics(team_id, season);  
CREATE INDEX idx_advanced_batting_date ON advanced_team_batting_metrics(as_of_date);

CREATE INDEX idx_composite_team_season ON composite_team_metrics(team_id, season);
CREATE INDEX idx_composite_date ON composite_team_metrics(as_of_date);

CREATE INDEX idx_statcast_team_season ON team_statcast_aggregates(team_id, season);
CREATE INDEX idx_statcast_date_range ON team_statcast_aggregates(date_range_start, date_range_end);

CREATE INDEX idx_trends_team_season ON team_performance_trends(team_id, season);
CREATE INDEX idx_trends_date ON team_performance_trends(as_of_date);

-- Comments for documentation
COMMENT ON TABLE advanced_team_pitching_metrics IS 'Advanced pitching metrics from FanGraphs/PyBaseball including FIP, xFIP, SIERA, Stuff+';
COMMENT ON TABLE advanced_team_batting_metrics IS 'Advanced batting metrics including wOBA, wRC+, Statcast exit velocity, barrel rate';
COMMENT ON TABLE composite_team_metrics IS 'Derived team ratings combining pitching and batting metrics into composite scores';
COMMENT ON TABLE team_statcast_aggregates IS 'Aggregated Statcast data by team and date range for rolling window analysis';
COMMENT ON TABLE team_performance_trends IS 'Team performance trends and momentum indicators for situational analysis';


-- Games table - Core query patterns for game lookups
CREATE INDEX IF NOT EXISTS idx_games_date 
    ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_home_team 
    ON games(home_team_id);
CREATE INDEX IF NOT EXISTS idx_games_away_team 
    ON games(away_team_id);
CREATE INDEX IF NOT EXISTS idx_games_status 
    ON games(game_status);
CREATE INDEX IF NOT EXISTS idx_games_date_status 
    ON games(game_date, game_status);
CREATE INDEX IF NOT EXISTS idx_games_date_teams 
    ON games(game_date, home_team_id, away_team_id);

-- Teams table - Geographic and lookup queries
CREATE INDEX IF NOT EXISTS idx_teams_name 
    ON teams(team_name);
CREATE INDEX IF NOT EXISTS idx_teams_city 
    ON teams(city);
CREATE INDEX IF NOT EXISTS idx_teams_location 
    ON teams(latitude, longitude);

-- ================================================================================
-- 6.2 HIGH-VOLUME TABLE INDEXES (Pitches - 740k+ records per season)
-- ================================================================================

-- Pitches table - Critical for performance due to volume
CREATE INDEX IF NOT EXISTS idx_pitches_game 
    ON pitches(game_pk);
CREATE INDEX IF NOT EXISTS idx_pitches_pitcher 
    ON pitches(pitcher_id);
CREATE INDEX IF NOT EXISTS idx_pitches_batter 
    ON pitches(batter_id);
CREATE INDEX IF NOT EXISTS idx_pitches_inning 
    ON pitches(inning);
CREATE INDEX IF NOT EXISTS idx_pitches_type 
    ON pitches(pitch_type);
CREATE INDEX IF NOT EXISTS idx_pitches_events 
    ON pitches(events);

-- Composite indexes for common pitch analysis queries
CREATE INDEX IF NOT EXISTS idx_pitches_game_inning 
    ON pitches(game_pk, inning);
CREATE INDEX IF NOT EXISTS idx_pitches_pitcher_type 
    ON pitches(pitcher_id, pitch_type);
CREATE INDEX IF NOT EXISTS idx_pitches_batter_events 
    ON pitches(batter_id, events);
CREATE INDEX IF NOT EXISTS idx_pitches_game_pitcher 
    ON pitches(game_pk, pitcher_id);

-- ================================================================================
-- 6.3 PLAYER ANALYTICS INDEXES
-- ================================================================================

-- Players table indexes
CREATE INDEX IF NOT EXISTS idx_players_name_display 
    ON players(name_display);
CREATE INDEX IF NOT EXISTS idx_players_current_team 
    ON players(current_team_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_players_position 
    ON players(primary_position) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_players_bats_throws 
    ON players(bats, throws) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_players_active 
    ON players(is_active);
CREATE INDEX IF NOT EXISTS idx_players_debut_date 
    ON players(mlb_debut_date);

-- Player batting stats indexes
CREATE INDEX IF NOT EXISTS idx_batting_player_season 
    ON player_batting_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_batting_season 
    ON player_batting_stats(season);
CREATE INDEX IF NOT EXISTS idx_batting_team_season 
    ON player_batting_stats(team_id, season);
CREATE INDEX IF NOT EXISTS idx_batting_wrc_plus 
    ON player_batting_stats(wrc_plus) WHERE wrc_plus IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_batting_war 
    ON player_batting_stats(war) WHERE war IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_batting_qualified 
    ON player_batting_stats(plate_appearances) WHERE plate_appearances >= 502;

-- ================================================================================
-- 6.3.5 TRANSACTION AND INJURY TRACKING INDEXES
-- ================================================================================

-- MLB Transactions indexes
CREATE INDEX IF NOT EXISTS idx_mlb_transactions_player 
    ON mlb_transactions(player_id);
CREATE INDEX IF NOT EXISTS idx_mlb_transactions_date 
    ON mlb_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_mlb_transactions_from_team 
    ON mlb_transactions(from_team_id) WHERE from_team_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mlb_transactions_to_team 
    ON mlb_transactions(to_team_id) WHERE to_team_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mlb_transactions_type 
    ON mlb_transactions(type_code, type_description);
CREATE INDEX IF NOT EXISTS idx_mlb_transactions_trades 
    ON mlb_transactions(transaction_date, player_id) WHERE is_trade = TRUE;
CREATE INDEX IF NOT EXISTS idx_mlb_transactions_injuries 
    ON mlb_transactions(transaction_date, player_id) WHERE is_injury_related = TRUE;

-- Player Team History indexes
CREATE INDEX IF NOT EXISTS idx_team_history_player 
    ON player_team_history(player_id);
CREATE INDEX IF NOT EXISTS idx_team_history_team 
    ON player_team_history(team_id);
CREATE INDEX IF NOT EXISTS idx_team_history_dates 
    ON player_team_history(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_team_history_active 
    ON player_team_history(player_id, start_date) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_team_history_current 
    ON player_team_history(player_id, team_id) WHERE end_date IS NULL;

-- Player Injuries indexes
CREATE INDEX IF NOT EXISTS idx_player_injuries_player 
    ON player_injuries(player_id);
CREATE INDEX IF NOT EXISTS idx_player_injuries_team 
    ON player_injuries(team_id) WHERE team_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_player_injuries_dates 
    ON player_injuries(injury_date, actual_return_date);
CREATE INDEX IF NOT EXISTS idx_player_injuries_il_dates 
    ON player_injuries(il_placement_date, il_eligibility_date);
CREATE INDEX IF NOT EXISTS idx_player_injuries_status 
    ON player_injuries(status, il_designation);
CREATE INDEX IF NOT EXISTS idx_player_injuries_active 
    ON player_injuries(player_id, status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_player_injuries_body_part 
    ON player_injuries(body_part, injury_type);

-- Daily Player Status indexes
CREATE INDEX IF NOT EXISTS idx_daily_status_player_date 
    ON daily_player_status(player_id, status_date);
CREATE INDEX IF NOT EXISTS idx_daily_status_team_date 
    ON daily_player_status(team_id, status_date);
CREATE INDEX IF NOT EXISTS idx_daily_status_availability 
    ON daily_player_status(availability_status, availability_score);
CREATE INDEX IF NOT EXISTS idx_daily_status_injured 
    ON daily_player_status(player_id, status_date) WHERE roster_status = 'injured';
CREATE INDEX IF NOT EXISTS idx_daily_status_game_context 
    ON daily_player_status(status_date, opponent_team_id, is_home_game);

-- Player Trade Impact indexes
CREATE INDEX IF NOT EXISTS idx_trade_impact_player 
    ON player_trade_impact(player_id);
CREATE INDEX IF NOT EXISTS idx_trade_impact_trade 
    ON player_trade_impact(trade_transaction_id);
CREATE INDEX IF NOT EXISTS idx_trade_impact_season 
    ON player_trade_impact(season, trade_date);
CREATE INDEX IF NOT EXISTS idx_trade_impact_teams 
    ON player_trade_impact(from_team_id, to_team_id);
CREATE INDEX IF NOT EXISTS idx_trade_impact_performance 
    ON player_trade_impact(sample_size_adequate, performance_change_pct) 
    WHERE sample_size_adequate = TRUE;

-- ================================================================================
-- 6.4 TABLE COMMENTS AND DOCUMENTATION
-- ================================================================================

-- =============================================================================
-- TEAM STATS INDEXES (Analytics and Reporting)
-- =============================================================================

-- Team stats table - Season analysis
CREATE INDEX IF NOT EXISTS idx_team_stats_team ON team_stats(team_id);
CREATE INDEX IF NOT EXISTS idx_team_stats_season ON team_stats(season);
CREATE INDEX IF NOT EXISTS idx_team_stats_team_season ON team_stats(team_id, season);
CREATE INDEX IF NOT EXISTS idx_team_stats_games_played ON team_stats(games_played);

-- Performance metric indexes for ranking queries
CREATE INDEX IF NOT EXISTS idx_team_stats_batting_avg ON team_stats(batting_avg DESC);
CREATE INDEX IF NOT EXISTS idx_team_stats_era ON team_stats(era ASC);
CREATE INDEX IF NOT EXISTS idx_team_stats_ops ON team_stats(ops DESC);
CREATE INDEX IF NOT EXISTS idx_team_stats_runs_scored ON team_stats(runs_scored DESC);
CREATE INDEX IF NOT EXISTS idx_team_stats_runs_allowed ON team_stats(runs_allowed ASC);

-- =============================================================================
-- WEATHER CONDITIONS INDEXES (API Integration)
-- =============================================================================

-- Weather conditions table - Game correlation
CREATE INDEX IF NOT EXISTS idx_weather_game ON weather_conditions(game_pk);
CREATE INDEX IF NOT EXISTS idx_weather_game_time ON weather_conditions(game_time);
CREATE INDEX IF NOT EXISTS idx_weather_temperature ON weather_conditions(temperature);
CREATE INDEX IF NOT EXISTS idx_weather_conditions ON weather_conditions(conditions);
CREATE INDEX IF NOT EXISTS idx_weather_wind ON weather_conditions(wind_speed, wind_direction);

-- Weather analysis composite indexes
CREATE INDEX IF NOT EXISTS idx_weather_temp_humidity ON weather_conditions(temperature, humidity);
CREATE INDEX IF NOT EXISTS idx_weather_favorable ON weather_conditions(temperature, humidity, wind_speed);

-- =============================================================================
-- BETTING ODDS INDEXES (Trading and Analysis)
-- =============================================================================

-- Betting odds table - Real-time trading queries
CREATE INDEX IF NOT EXISTS idx_betting_odds_game ON betting_odds(game_pk);
CREATE INDEX IF NOT EXISTS idx_betting_odds_sportsbook ON betting_odds(sportsbook);
CREATE INDEX IF NOT EXISTS idx_betting_odds_timestamp ON betting_odds(odds_timestamp);
CREATE INDEX IF NOT EXISTS idx_betting_odds_home_team ON betting_odds(home_team_id);
CREATE INDEX IF NOT EXISTS idx_betting_odds_away_team ON betting_odds(away_team_id);

-- Moneyline analysis indexes
CREATE INDEX IF NOT EXISTS idx_betting_odds_home_moneyline ON betting_odds(home_moneyline);
CREATE INDEX IF NOT EXISTS idx_betting_odds_away_moneyline ON betting_odds(away_moneyline);

-- Composite indexes for odds comparison and line movement
CREATE INDEX IF NOT EXISTS idx_betting_odds_game_sportsbook ON betting_odds(game_pk, sportsbook);
CREATE INDEX IF NOT EXISTS idx_betting_odds_game_timestamp ON betting_odds(game_pk, odds_timestamp);
CREATE INDEX IF NOT EXISTS idx_betting_odds_sportsbook_timestamp ON betting_odds(sportsbook, odds_timestamp);

-- Line movement tracking
CREATE INDEX IF NOT EXISTS idx_betting_odds_game_sportsbook_time ON betting_odds(game_pk, sportsbook, odds_timestamp);

-- =============================================================================
-- AUDIT LOG INDEXES (Security and Monitoring)
-- =============================================================================

-- Audit log table - Security and compliance
CREATE INDEX IF NOT EXISTS idx_audit_log_table ON audit_log(table_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_operation ON audit_log(operation);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_at ON audit_log(changed_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_by ON audit_log(changed_by);
CREATE INDEX IF NOT EXISTS idx_audit_log_record_id ON audit_log(record_id);

-- Audit analysis composite indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_table_operation ON audit_log(table_name, operation);
CREATE INDEX IF NOT EXISTS idx_audit_log_table_time ON audit_log(table_name, changed_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_time ON audit_log(changed_by, changed_at);

-- =============================================================================
-- TIMESTAMP INDEXES (Data Management)
-- =============================================================================

-- Universal timestamp indexes for data cleanup and analysis
CREATE INDEX IF NOT EXISTS idx_games_created_at ON games(created_at);
CREATE INDEX IF NOT EXISTS idx_games_updated_at ON games(updated_at);
CREATE INDEX IF NOT EXISTS idx_pitches_created_at ON pitches(created_at);
CREATE INDEX IF NOT EXISTS idx_team_stats_created_at ON team_stats(created_at);
CREATE INDEX IF NOT EXISTS idx_team_stats_updated_at ON team_stats(updated_at);
CREATE INDEX IF NOT EXISTS idx_weather_created_at ON weather_conditions(created_at);
CREATE INDEX IF NOT EXISTS idx_betting_odds_created_at ON betting_odds(created_at);

-- =============================================================================
-- PARTIAL INDEXES (Conditional Optimization)
-- =============================================================================

-- Only index completed games for final analysis
CREATE INDEX IF NOT EXISTS idx_games_completed ON games(game_date, home_team_id, away_team_id) 
WHERE game_status = 'completed';

-- Only index recent betting odds (last 30 days) for active trading
CREATE INDEX IF NOT EXISTS idx_betting_odds_recent ON betting_odds(game_pk, sportsbook, odds_timestamp)
WHERE odds_timestamp >= CURRENT_DATE - INTERVAL '30 days';

-- Only index significant pitch events for outcome analysis
CREATE INDEX IF NOT EXISTS idx_pitches_significant_events ON pitches(game_pk, pitcher_id, batter_id)
WHERE events IN ('single', 'double', 'triple', 'home_run', 'walk', 'strikeout');

-- =============================================================================
-- FULL-TEXT SEARCH INDEXES (Advanced Queries)
-- =============================================================================

-- Enable full-text search on team names and cities
CREATE INDEX IF NOT EXISTS idx_teams_fulltext ON teams USING gin(to_tsvector('english', team_name || ' ' || city));

-- Enable full-text search on weather conditions
CREATE INDEX IF NOT EXISTS idx_weather_conditions_fulltext ON weather_conditions USING gin(to_tsvector('english', conditions));

-- =============================================================================
-- STATISTICS UPDATE (Performance Maintenance)
-- =============================================================================

-- Update table statistics for query optimizer
ANALYZE teams;
ANALYZE games;
ANALYZE pitches;
ANALYZE team_stats;
ANALYZE weather_conditions;
ANALYZE betting_odds;
ANALYZE audit_log;

-- =============================================================================
-- INDEX MAINTENANCE NOTES
-- =============================================================================

/*
PERFORMANCE GUIDELINES:

1. HIGH-FREQUENCY QUERIES:
   - Game lookups by date: idx_games_date, idx_games_date_status
   - Pitch analysis: idx_pitches_game, idx_pitches_pitcher_type
   - Team performance: idx_team_stats_team_season
   - Odds comparison: idx_betting_odds_game_sportsbook_time

2. MAINTENANCE SCHEDULE:
   - REINDEX weekly during off-season
   - ANALYZE after bulk data loads
   - Monitor index usage with pg_stat_user_indexes
   - Drop unused indexes if identified

3. SPACE CONSIDERATIONS:
   - Pitches table will be largest (740k+ rows/season)
   - Consider partitioning by season if data grows beyond 5+ years
   - Monitor index size vs table size ratio

4. QUERY OPTIMIZATION:
   - Use EXPLAIN ANALYZE to verify index usage
   - Consider covering indexes for frequently selected columns
   - Monitor slow query log for missing indexes

ESTIMATED INDEX SIZES (per season):
- Games: ~2MB
- Pitches: ~500MB (high volume)
- Team Stats: <1MB
- Weather: ~5MB
- Betting Odds: ~50MB
- Audit Log: ~10MB

Total estimated index overhead: ~600MB per season
*/

-- Player table indexes for optimal query performance
-- MLB Betting Analytics Platform - Player Data Enhancement
-- Created: September 23, 2025

-- Players table indexes
CREATE INDEX IF NOT EXISTS idx_players_name_display ON players(name_display);
CREATE INDEX IF NOT EXISTS idx_players_current_team ON players(current_team_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_players_position ON players(primary_position) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_players_bats_throws ON players(bats, throws) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_players_active ON players(is_active);
CREATE INDEX IF NOT EXISTS idx_players_debut_date ON players(mlb_debut_date);

-- Player batting stats indexes
CREATE INDEX IF NOT EXISTS idx_batting_player_season ON player_batting_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_batting_season ON player_batting_stats(season);
CREATE INDEX IF NOT EXISTS idx_batting_team_season ON player_batting_stats(team_id, season);
CREATE INDEX IF NOT EXISTS idx_batting_wrc_plus ON player_batting_stats(wrc_plus) WHERE wrc_plus IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_batting_war ON player_batting_stats(war) WHERE war IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_batting_qualified ON player_batting_stats(plate_appearances) WHERE plate_appearances >= 502; -- Qualified batters
CREATE INDEX IF NOT EXISTS idx_batting_stats_lookup ON player_batting_stats(season, wrc_plus, war) WHERE plate_appearances >= 100;

-- Player pitching stats indexes  
CREATE INDEX IF NOT EXISTS idx_pitching_player_season ON player_pitching_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_pitching_season ON player_pitching_stats(season);
CREATE INDEX IF NOT EXISTS idx_pitching_team_season ON player_pitching_stats(team_id, season);
CREATE INDEX IF NOT EXISTS idx_pitching_stuff_plus ON player_pitching_stats(stuff_plus) WHERE stuff_plus IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pitching_location_plus ON player_pitching_stats(location_plus) WHERE location_plus IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pitching_war ON player_pitching_stats(war) WHERE war IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pitching_qualified ON player_pitching_stats(innings_pitched) WHERE innings_pitched >= 162; -- Qualified starters
CREATE INDEX IF NOT EXISTS idx_pitching_role ON player_pitching_stats(starter_reliever, season);
CREATE INDEX IF NOT EXISTS idx_pitching_stats_lookup ON player_pitching_stats(season, stuff_plus, location_plus, war) WHERE innings_pitched >= 50;

-- Player matchups indexes (Critical for performance!)
CREATE INDEX IF NOT EXISTS idx_matchups_pitcher ON player_matchups(pitcher_id);
CREATE INDEX IF NOT EXISTS idx_matchups_batter ON player_matchups(batter_id);
CREATE INDEX IF NOT EXISTS idx_matchups_pitcher_batter ON player_matchups(pitcher_id, batter_id);
CREATE INDEX IF NOT EXISTS idx_matchups_sample_size ON player_matchups(total_plate_appearances) WHERE total_plate_appearances >= 5;
CREATE INDEX IF NOT EXISTS idx_matchups_recent ON player_matchups(last_matchup_date) WHERE last_matchup_date >= CURRENT_DATE - INTERVAL '2 years';
CREATE INDEX IF NOT EXISTS idx_matchups_confidence ON player_matchups(confidence_level, total_plate_appearances);
CREATE INDEX IF NOT EXISTS idx_matchups_platoon ON player_matchups(same_handedness, platoon_advantage);
CREATE INDEX IF NOT EXISTS idx_matchups_performance ON player_matchups(batting_average, ops) WHERE total_plate_appearances >= 10;

-- Player matchup summaries indexes
CREATE INDEX IF NOT EXISTS idx_matchup_summaries_player_season ON player_matchup_summaries(player_id, season);
CREATE INDEX IF NOT EXISTS idx_matchup_summaries_season ON player_matchup_summaries(season);
CREATE INDEX IF NOT EXISTS idx_matchup_summaries_platoon ON player_matchup_summaries(platoon_split_ops) WHERE platoon_split_ops IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_matchup_summaries_vs_elite ON player_matchup_summaries(vs_elite_pitchers_ops) WHERE vs_elite_pitchers_pa >= 20;

-- Composite indexes for common query patterns

-- Find active players by team and position
CREATE INDEX IF NOT EXISTS idx_players_team_position_active ON players(current_team_id, primary_position) 
    WHERE is_active = TRUE;

-- Batting stats for current season qualified players
CREATE INDEX IF NOT EXISTS idx_batting_current_qualified ON player_batting_stats(season, wrc_plus, war) 
    WHERE season = EXTRACT(YEAR FROM CURRENT_DATE) AND plate_appearances >= 100;

-- Pitching stats for current season qualified players  
CREATE INDEX IF NOT EXISTS idx_pitching_current_qualified ON player_pitching_stats(season, stuff_plus, war)
    WHERE season = EXTRACT(YEAR FROM CURRENT_DATE) AND innings_pitched >= 20;

-- Matchups with sufficient sample size and recent activity
CREATE INDEX IF NOT EXISTS idx_matchups_reliable ON player_matchups(pitcher_id, batter_id, batting_average, ops)
    WHERE total_plate_appearances >= 10 AND last_matchup_date >= CURRENT_DATE - INTERVAL '3 years';

-- High-leverage matchup lookups
CREATE INDEX IF NOT EXISTS idx_matchups_high_leverage ON player_matchups(pitcher_id, batter_id, dominance_score)
    WHERE total_plate_appearances >= 5 AND confidence_level IN ('high', 'medium');

-- Platoon split analysis
CREATE INDEX IF NOT EXISTS idx_matchups_platoon_analysis ON player_matchups(same_handedness, platoon_advantage, batting_average)
    WHERE total_plate_appearances >= 5;

-- Performance-based lookups for model training
CREATE INDEX IF NOT EXISTS idx_batting_model_features ON player_batting_stats(
    season, wrc_plus, iso, bb_percent, k_percent, hard_hit_percent
) WHERE plate_appearances >= 100;

CREATE INDEX IF NOT EXISTS idx_pitching_model_features ON player_pitching_stats(
    season, stuff_plus, location_plus, k_percent, bb_percent, gb_percent
) WHERE innings_pitched >= 20;

-- Add statistics for query optimization
ANALYZE players;
ANALYZE player_batting_stats;
ANALYZE player_pitching_stats;
ANALYZE player_matchups;
ANALYZE player_matchup_summaries;