"""
Configuration settings for the Trading Platform Backend
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for Flask application"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # Frontend settings
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    # Allow multiple origins for local dev
    WS_CORS_ORIGINS = os.environ.get('WS_CORS_ORIGINS')
    if WS_CORS_ORIGINS:
        # Comma-separated list from env
        WS_CORS_ORIGINS = [o.strip() for o in WS_CORS_ORIGINS.split(',') if o.strip()]
    else:
        WS_CORS_ORIGINS = [
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:5173',
            'http://127.0.0.1:5173'
        ]
    
    # API settings
    API_VERSION = '1.0.0'
    API_TIMEOUT = int(os.environ.get('API_TIMEOUT', '30'))
    
    # Database settings (if needed in future)
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Kite Connect API settings
    KITE_API_KEY = os.environ.get('KITE_API_KEY')
    KITE_API_SECRET = os.environ.get('KITE_API_SECRET')
    KITE_ACCESS_TOKEN = os.environ.get('KITE_ACCESS_TOKEN')
    KITE_REQUEST_TOKEN = os.environ.get('KITE_REQUEST_TOKEN')
    
    # WebSocket settings
    # Note: WS_CORS_ORIGINS is defined above and can be configured via env
    
    # Cache settings
    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', '30'))  # seconds
    
    # Trading symbols
    INDEX_SYMBOLS = [
        'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX'
    ]
    
    # All 224 stock symbols (major NSE stocks)
    STOCK_SYMBOLS = [
        'TATAMOTORS', 'HDFCBANK', 'SBIN', 'AXISBANK', 'ICICIBANK', 
        'RELIANCE', 'INFY', 'TCS', 'HINDUNILVR', 'ASIANPAINT', 
        'ONGC', 'NTPC', 'JSWSTEEL', 'BHARTIARTL', 'HCLTECH', 
        'MARUTI', 'ADANIPORTS', 'SUNPHARMA', 'UPL', 'LT',
        'WIPRO', 'BAJFINANCE', 'POWERGRID', 'NESTLEIND', 'KOTAKBANK',
        'DRREDDY', 'TECHM', 'TITAN', 'COALINDIA', 'BAJAJFINSV',
        'HEROMOTOCO', 'BRITANNIA', 'CIPLA', 'DIVISLAB', 'EICHERMOT',
        'GRASIM', 'HINDALCO', 'INDUSINDBK', 'ITC', 'TATACONSUM',
        'BAJAJ-AUTO', 'SHREECEM', 'ULTRACEMCO', 'APOLLOHOSP', 'M&M',
        'ADANIENT', 'ADANIGREEN', 'ADANITRANS', 'ATGL', 'ADANIPOWER',
        'TATASTEEL', 'VEDL', 'SAIL', 'JINDALSTEL', 'NMDC',
        'HINDZINC', 'NATIONALUM', 'MOIL', 'WELCORP', 'RATNAMANI',
        'APLAPOLLO', 'KPIT', 'PERSISTENT', 'COFORGE', 'LTIM',
        'MPHASIS', 'MINDTREE', 'OFSS', 'HEXAWARE', 'CYIENT',
        'ZENSAR', 'ROLTA', 'SONATSOFTW', 'NIITTECH', 'INTELLECT',
        'RAMCOCEM', 'JKCEMENT', 'DALMIACEM', 'HEIDELBERG', 'PRISMCEM',
        'AMBUJCEM', 'ACC', 'JKLAKSHMI', 'INDIACEM', 'ORIENTCEM',
        'STARCEMENT', 'BURNPUR', 'WESTLIFE', 'JUBLFOOD', 'DEVYANI',
        'SAPPHIRE', 'SPECIALITY', 'RELAXO', 'BATA', 'KHADIM',
        'MIRZA', 'METRO', 'SHOPPER', 'TRENT', 'ABFRL',
        'VMART', 'ADITYA', 'RAYMOND', 'SIYARAM', 'GOKEX',
        'SPANDANA', 'INDHOTEL', 'LEMONTREE', 'MAHINDCIE', 'DELTACORP',
        'WONDERLA', 'TIPS', 'EIHOTEL', 'TAJGVK', 'CHALET',
        'MAHLOG', 'BLUEDART', 'GATI', 'AEGISCHEM', 'CONCOR',
        'TIINDIA', 'GARFIBRES', 'SYMPHONY', 'VOLTAS', 'BLUESTAR',
        'AMBER', 'CARRIER', 'JOHNSON', 'WHIRLPOOL', 'CROMPTON',
        'HAVELLS', 'ORIENT', 'KHAITAN', 'FINOLEX', 'POLYCAB',
        'KALYAN', 'PCJEWELLER', 'TITAN', 'RAJESHEXPO', 'THANGAMAYL',
        'GITANJALI', 'GOLDIAM', 'SURANASOL', 'DBREALTY', 'DLF',
        'GODREJPROP', 'BRIGADE', 'PRESTIGE', 'SOBHA', 'MAHLIFE',
        'SUNTECK', 'KOLTE', 'PURAVANKARA', 'ANANTRAJ', 'ASHIANA',
        'NITCO', 'DELTACORP', 'MAHSCOOTER', 'BAJAJHIND', 'EICHER',
        'APOLLOTYRE', 'CEAT', 'BALKRISIND', 'JK', 'MRF',
        'MOTHERSUMI', 'BOSCHLTD', 'SCHAEFFLER', 'SPARC', 'RANE',
        'WABCOINDIA', 'WHEELS', 'GABRIEL', 'RAMKRISHNA', 'EXIDEIND',
        'AMARA', 'ELGIEQUIP', 'KEC', 'THERMAX', 'BEL',
        'SIEMENS', 'ABB', 'CROMPTON', 'SCHNEIDER', 'LEGRAND',
        'GREAVES', 'CUMMINSIND', 'KIRLOSENG', 'KALYANI', 'GRINDWELL',
        'CARBORUNIV', 'FINEORG', 'SRF', 'AAVAS', 'KANSAINER',
        'KESORAMIND', 'HEIDELBERG', 'SHREECEM', 'DALMIACEM', 'JKCEMENT',
        'RAMCOCEM', 'PRISMCEM', 'INDIACEM', 'ORIENTCEM', 'BURNPUR',
        'ZUARI', 'GSFC', 'GNFC', 'RCF', 'NFL',
        'CHAMBLFERT', 'COROMANDEL', 'KRIBHCO', 'MADRAS', 'DEEPAKFERT',
        'SPIC', 'SFL', 'FACT', 'MANGALAM', 'TRAVANCORE',
        'IFFCO', 'KRISHANA', 'NAGARFERT', 'SMARTLINK', 'TANLA',
        'ROUTE', 'RCOM', 'GTL', 'GTLINFRA', 'ONMOBILE',
        'IDEA', 'BHARTIARTL', 'MARICO', 'GODREJCP', 'VBL',
        'DABUR', 'EMAMILTD', 'JYOTHY', 'MRPL', 'HPCL',
        'BPCL', 'IOC', 'GAIL', 'OIL', 'PETRONET'
    ]
    
    ALL_SYMBOLS = INDEX_SYMBOLS + STOCK_SYMBOLS
    
    # Option chain settings
    DEFAULT_STRIKE_RANGE = 20  # Number of strikes around ATM
    MAX_STRIKE_RANGE = 50     # Maximum strikes to return
    
    # Greeks calculation settings
    RISK_FREE_RATE = float(os.environ.get('RISK_FREE_RATE', '0.05'))  # 5%
    
    # Rate limiting (if needed)
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '100'))
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    @classmethod
    def validate_config(cls):
        """Validate required configuration"""
        required_vars = []
        
        if not cls.KITE_API_KEY:
            required_vars.append('KITE_API_KEY')
        if not cls.KITE_API_SECRET:
            required_vars.append('KITE_API_SECRET')
            
        if required_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(required_vars)}")
        
        return True
    
    @classmethod
    def get_kite_config(cls):
        """Get Kite Connect configuration"""
        return {
            'api_key': cls.KITE_API_KEY,
            'api_secret': cls.KITE_API_SECRET,
            'access_token': cls.KITE_ACCESS_TOKEN,
            'request_token': cls.KITE_REQUEST_TOKEN
        }
    
    @classmethod
    def is_development(cls):
        """Check if running in development mode"""
        return cls.DEBUG
    
    @classmethod
    def get_frontend_config(cls):
        """Get frontend-related configuration"""
        return {
            'frontend_url': cls.FRONTEND_URL,
            'cors_origins': cls.WS_CORS_ORIGINS,
            'api_version': cls.API_VERSION
        }
