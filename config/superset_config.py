# ============================================
# Apache Superset Configuration
# ============================================

import os
from cachelib.redis import RedisCache

# ==========================================
# Superset Metadata Database
# ==========================================
SQLALCHEMY_DATABASE_URI = (
    f"postgresql://{os.getenv('DATABASE_USER', 'airflow')}:"
    f"{os.getenv('DATABASE_PASSWORD', 'airflow')}@"
    f"{os.getenv('DATABASE_HOST', 'postgres')}:"
    f"{os.getenv('DATABASE_PORT', '5432')}/"
    f"{os.getenv('DATABASE_DB', 'superset')}"
)

# ==========================================
# Redis Cache
# ==========================================
CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_HOST': os.getenv('REDIS_HOST', 'redis'),
    'CACHE_REDIS_PORT': int(os.getenv('REDIS_PORT', 6379)),
    'CACHE_REDIS_DB': 1,
}

DATA_CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 86400,  # 1 day
    'CACHE_KEY_PREFIX': 'superset_data_',
    'CACHE_REDIS_HOST': os.getenv('REDIS_HOST', 'redis'),
    'CACHE_REDIS_PORT': int(os.getenv('REDIS_PORT', 6379)),
    'CACHE_REDIS_DB': 2,
}

# ==========================================
# Secret Key
# ==========================================
SECRET_KEY = os.getenv('SUPERSET_SECRET_KEY', 'thisISaSECRET_1234567890')

# ==========================================
# Security
# ==========================================
# CSRF Configuration
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = None

# ==========================================
# Feature Flags
# ==========================================
FEATURE_FLAGS = {
    'ENABLE_TEMPLATE_PROCESSING': True,
    'DASHBOARD_NATIVE_FILTERS': True,
    'DASHBOARD_CROSS_FILTERS': True,
    'DASHBOARD_RBAC': True,
    'EMBEDDED_SUPERSET': True,
    'ENABLE_EXPLORE_JSON_CSRF_PROTECTION': True,
}

# ==========================================
# Row Limit
# ==========================================
ROW_LIMIT = 10000
SUPERSET_WEBSERVER_TIMEOUT = 300

# ==========================================
# BigQuery Configuration
# ==========================================
# Pour se connecter à BigQuery, utilisez cette syntaxe dans l'UI:
# bigquery://{project_id}/?credentials_path=/path/to/service_account.json

# ==========================================
# PostgreSQL Configuration (pour données locales)
# ==========================================
# PostgreSQL est déjà configuré via SQLALCHEMY_DATABASE_URI

# ==========================================
# Async Queries
# ==========================================
GLOBAL_ASYNC_QUERIES_TRANSPORT = "polling"
GLOBAL_ASYNC_QUERIES_POLLING_DELAY = 500

# ==========================================
# Upload Settings
# ==========================================
UPLOAD_FOLDER = '/app/superset_home/uploads/'
IMG_UPLOAD_FOLDER = '/app/superset_home/uploads/'
IMG_UPLOAD_URL = '/static/uploads/'

# ==========================================
# Languages
# ==========================================
LANGUAGES = {
    'en': {'flag': 'us', 'name': 'English'},
    'fr': {'flag': 'fr', 'name': 'French'},
}

# ==========================================
# Email Configuration (optionnel)
# ==========================================
SMTP_HOST = os.getenv('SMTP_HOST', 'localhost')
SMTP_STARTTLS = True
SMTP_SSL = False
SMTP_USER = os.getenv('SMTP_USER', 'superset@example.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 25))
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_MAIL_FROM = os.getenv('SMTP_MAIL_FROM', 'superset@example.com')

# ==========================================
# Logging
# ==========================================
ENABLE_TIME_ROTATE = True
TIME_ROTATE_LOG_LEVEL = 'INFO'
FILENAME = os.path.join('/app/superset_home', 'superset.log')

# ==========================================
# Webserver Configuration
# ==========================================
SUPERSET_WEBSERVER_PORT = 8088
SUPERSET_WEBSERVER_ADDRESS = '0.0.0.0'
SUPERSET_WEBSERVER_TIMEOUT = 300

# ==========================================
# SQL Lab Configuration
# ==========================================
SQLLAB_TIMEOUT = 300
SQLLAB_ASYNC_TIME_LIMIT_SEC = 3600
SQLLAB_VALIDATION_TIMEOUT = 10

# ==========================================
# Custom Settings for Job Matching Platform
# ==========================================
APP_NAME = 'Job Matching BI Platform'
APP_ICON = '/static/assets/images/superset-logo-horiz.png'

