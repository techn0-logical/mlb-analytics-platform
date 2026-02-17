"""
Production Logging Configuration for MLB Prediction System
=========================================================

Comprehensive logging setup for production deployment with different
log levels, file rotation, and monitoring capabilities.

Features:
- Structured logging with JSON format for analysis
- Automatic log rotation and archiving
- Performance metrics logging
- Error tracking and alerting
- Real-time monitoring capabilities
"""

import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import sys

class JSONFormatter(logging.Formatter):
    """Custom formatter to output logs in JSON format for easier analysis"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }
        
        # Add extra fields if they exist
        if hasattr(record, 'game_pk'):
            log_obj['game_pk'] = record.game_pk
        if hasattr(record, 'prediction_id'):
            log_obj['prediction_id'] = record.prediction_id
        if hasattr(record, 'accuracy'):
            log_obj['accuracy'] = record.accuracy
        if hasattr(record, 'confidence_level'):
            log_obj['confidence_level'] = record.confidence_level
            
        return json.dumps(log_obj)


class PredictionSystemLogger:
    """Centralized logging system for the MLB prediction workflow"""
    
    def __init__(self, log_dir: str = "logs", enable_json: bool = True):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.enable_json = enable_json
        
        # Create subdirectories for different log types
        (self.log_dir / "predictions").mkdir(exist_ok=True)
        (self.log_dir / "performance").mkdir(exist_ok=True)
        (self.log_dir / "errors").mkdir(exist_ok=True)
        (self.log_dir / "system").mkdir(exist_ok=True)
        
        self._setup_loggers()
    
    def _setup_loggers(self):
        """Setup all required loggers with appropriate handlers"""
        
        # 1. Main Application Logger
        self.app_logger = self._create_logger(
            name='mlb_predictor',
            log_file='system/application.log',
            level=logging.INFO
        )
        
        # 2. Prediction Logger - All predictions made
        self.prediction_logger = self._create_logger(
            name='predictions',
            log_file='predictions/predictions.log',
            level=logging.INFO,
            max_bytes=50*1024*1024,  # 50MB files
            backup_count=10
        )
        
        # 3. Performance Logger - Model accuracy and metrics
        self.performance_logger = self._create_logger(
            name='performance',
            log_file='performance/performance.log',
            level=logging.INFO,
            max_bytes=20*1024*1024,  # 20MB files
            backup_count=20  # Keep more performance history
        )
        
        # 4. Error Logger - Errors and exceptions
        self.error_logger = self._create_logger(
            name='errors',
            log_file='errors/errors.log',
            level=logging.ERROR,
            max_bytes=10*1024*1024,  # 10MB files
            backup_count=5
        )
        
        # 5. Database Logger - Database operations
        self.db_logger = self._create_logger(
            name='database',
            log_file='system/database.log',
            level=logging.WARNING  # Only warnings and errors
        )
        
        # 6. Model Logger - Model loading and operations
        self.model_logger = self._create_logger(
            name='model',
            log_file='system/model.log',
            level=logging.INFO
        )
    
    def _create_logger(self, name: str, log_file: str, level: int = logging.INFO,
                      max_bytes: int = 10*1024*1024, backup_count: int = 5) -> logging.Logger:
        """Create a logger with rotating file handler and optional console output"""
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
        # File handler with rotation
        file_path = self.log_dir / log_file
        file_handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Set formatter
        if self.enable_json:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s'
            )
        
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler for important messages
        if name in ['mlb_predictor', 'errors']:
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        return logger
    
    def log_prediction(self, game_pk: int, home_team: str, away_team: str,
                      predicted_winner: str, probability: float, confidence: str,
                      factors: list = None):
        """Log a prediction with all relevant details"""
        
        extra_fields = {
            'game_pk': game_pk,
            'confidence_level': confidence
        }
        
        message = (
            f"PREDICTION | Game {game_pk} | {away_team} @ {home_team} | "
            f"Winner: {predicted_winner} | Prob: {probability:.3f} | "
            f"Confidence: {confidence.upper()}"
        )
        
        if factors:
            message += f" | Factors: {', '.join(factors[:3])}"
        
        self.prediction_logger.info(message, extra=extra_fields)
    
    def log_performance(self, date: str, accuracy: float, total_predictions: int,
                       correct_predictions: int, confidence_breakdown: Dict[str, Dict]):
        """Log daily performance metrics"""
        
        extra_fields = {
            'accuracy': accuracy,
            'date': date
        }
        
        message = (
            f"DAILY_PERFORMANCE | {date} | "
            f"Accuracy: {accuracy:.3f} ({correct_predictions}/{total_predictions}) | "
            f"High: {confidence_breakdown.get('high', {}).get('accuracy', 0):.3f} | "
            f"Medium: {confidence_breakdown.get('medium', {}).get('accuracy', 0):.3f} | "
            f"Low: {confidence_breakdown.get('low', {}).get('accuracy', 0):.3f}"
        )
        
        self.performance_logger.info(message, extra=extra_fields)
    
    def log_validation(self, game_pk: int, predicted_winner: str, actual_winner: str,
                      is_correct: bool, confidence: str):
        """Log prediction validation results"""
        
        extra_fields = {
            'game_pk': game_pk,
            'confidence_level': confidence
        }
        
        result = "CORRECT" if is_correct else "INCORRECT"
        message = (
            f"VALIDATION | Game {game_pk} | "
            f"Predicted: {predicted_winner} | Actual: {actual_winner} | "
            f"Result: {result} | Confidence: {confidence.upper()}"
        )
        
        self.performance_logger.info(message, extra=extra_fields)
    
    def log_error(self, operation: str, error: Exception, context: Dict[str, Any] = None):
        """Log errors with context information"""
        
        error_message = f"ERROR in {operation}: {str(error)}"
        
        if context:
            context_str = " | ".join([f"{k}: {v}" for k, v in context.items()])
            error_message += f" | Context: {context_str}"
        
        self.error_logger.error(error_message, exc_info=True)
    
    def log_model_operation(self, operation: str, status: str, details: str = ""):
        """Log model loading, saving, and other operations"""
        
        message = f"MODEL_{operation.upper()} | Status: {status}"
        if details:
            message += f" | {details}"
        
        self.model_logger.info(message)
    
    def log_database_operation(self, operation: str, table: str, count: int = None,
                              status: str = "SUCCESS"):
        """Log database operations"""
        
        message = f"DB_{operation.upper()} | Table: {table} | Status: {status}"
        if count is not None:
            message += f" | Records: {count}"
        
        self.db_logger.info(message)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a specific logger by name"""
        loggers = {
            'app': self.app_logger,
            'predictions': self.prediction_logger,
            'performance': self.performance_logger,
            'errors': self.error_logger,
            'database': self.db_logger,
            'model': self.model_logger
        }
        return loggers.get(name, self.app_logger)


# Global logger instance
prediction_system_logger = None

def get_logger() -> PredictionSystemLogger:
    """Get the global logger instance"""
    global prediction_system_logger
    if prediction_system_logger is None:
        prediction_system_logger = PredictionSystemLogger()
    return prediction_system_logger


def init_logging(log_dir: str = "logs", json_format: bool = True) -> PredictionSystemLogger:
    """Initialize the logging system"""
    global prediction_system_logger
    prediction_system_logger = PredictionSystemLogger(log_dir, json_format)
    
    # Log system initialization
    prediction_system_logger.app_logger.info(
        f"🚀 MLB Prediction System Logging Initialized | "
        f"Log Directory: {log_dir} | JSON Format: {json_format}"
    )
    
    return prediction_system_logger


if __name__ == "__main__":
    # Test the logging system
    print("🧪 Testing MLB Prediction Logging System")
    
    logger_system = init_logging()
    
    # Test different log types
    logger_system.log_prediction(
        game_pk=12345,
        home_team="LAD",
        away_team="SF",
        predicted_winner="LAD",
        probability=0.652,
        confidence="medium",
        factors=["Home field advantage", "Better recent form", "Trade acquisition boost"]
    )
    
    logger_system.log_performance(
        date="2026-02-05",
        accuracy=0.732,
        total_predictions=15,
        correct_predictions=11,
        confidence_breakdown={
            'high': {'accuracy': 1.0, 'count': 2},
            'medium': {'accuracy': 0.8, 'count': 5},
            'low': {'accuracy': 0.625, 'count': 8}
        }
    )
    
    logger_system.log_validation(
        game_pk=12345,
        predicted_winner="LAD",
        actual_winner="LAD",
        is_correct=True,
        confidence="medium"
    )
    
    logger_system.log_model_operation(
        operation="load",
        status="SUCCESS",
        details="Model loaded with 73.2% validation accuracy"
    )
    
    print("✅ Logging system test completed. Check the logs/ directory for output files.")