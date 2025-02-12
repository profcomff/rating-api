import os


__version__ = os.getenv('APP_VERSION', 'dev')

LOGGING_MARKETING_URLS = {
    "dev": f"http://localhost:{os.getenv('MARKETING_PORT', 8000)}/v1/action" if os.getenv('MARKETING_PORT', None) else "https://api.test.profcomff.com/marketing/v1/action", 
    "prod": "https://api.profcomff.com/marketing/v1/action",
}

LOGGING_MARKETING_URL = LOGGING_MARKETING_URLS.get(__version__, LOGGING_MARKETING_URLS["prod"])