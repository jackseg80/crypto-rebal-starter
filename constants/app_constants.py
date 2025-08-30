"""
Application-wide constants
"""

# API Configuration
DEFAULT_API_TIMEOUT = 30  # seconds
DEFAULT_CACHE_TTL = 300   # 5 minutes
MAX_RETRY_ATTEMPTS = 3

# Portfolio Configuration
MIN_TRADE_USD = 25.0      # Minimum trade amount in USD
DEFAULT_DRIFT_THRESHOLD = 5.0  # Default drift threshold percentage
MAX_ALLOCATION_DRIFT = 20.0    # Maximum allowed drift before critical alert

# Data Processing
MIN_ASSET_VALUE_USD = 0.50  # Minimum asset value to include in calculations
CSV_ENCODING = 'utf-8-sig'  # Encoding for CSV files (handles BOM)

# Risk Management
RISK_LEVELS = {
    'low': {'max_single_trade': 1000, 'max_daily_volume': 5000},
    'medium': {'max_single_trade': 5000, 'max_daily_volume': 25000},
    'high': {'max_single_trade': 25000, 'max_daily_volume': 100000}
}

# Alert Thresholds
ALERT_THRESHOLDS = {
    'drift_warning': 5.0,    # Warning at 5% drift
    'drift_critical': 10.0,  # Critical at 10% drift
    'price_deviation': 2.0   # Price deviation threshold
}

# File Paths
DEFAULT_DATA_DIR = "data"
DEFAULT_RAW_DATA_DIR = "data/raw"
DEFAULT_BACKUP_DIR = "data/backups"

# Debug Configuration (for development)
DEBUG_ENABLED = True
DEBUG_LOG_LEVEL = "INFO"

# Rate Limiting
API_RATE_LIMIT = {
    'coingecko': 30,    # requests per minute
    'cointracking': 60, # requests per minute
    'binance': 1200,    # requests per minute
    'kraken': 60        # requests per minute
}