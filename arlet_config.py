"""
ARLET Configuration Manager
Centralized configuration with environment variables, type validation, and Firebase setup.
Architecture Choice: Singleton pattern ensures consistent config access across all modules.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TradingMode(Enum):
    """Trading operation modes for different market conditions"""
    DISCRETE = "discrete"      # Fixed action space
    CONTINUOUS = "continuous"  # Continuous action space
    HYBRID = "hybrid"          # Mixed strategy approach

class DataSource(Enum):
    """Supported data sources for market data"""
    CCXT = "ccxt"              # Crypto exchanges
    ALPACA = "alpaca"          # Stock markets
    YFINANCE = "yfinance"      # Historical data
    CUSTOM_API = "custom_api"  # Custom REST APIs

@dataclass
class ARLETConfig:
    """Main configuration class with validation"""
    
    # Trading parameters
    trading_mode: TradingMode = TradingMode.HYBRID
    initial_balance: float = 10000.0
    max_position_size: float = 0.1  # 10% of portfolio per trade
    transaction_cost: float = 0.001  # 0.1% per transaction
    
    # RL parameters
    learning_rate: float = 0.0003
    discount_factor: float = 0.99
    batch_size: int = 64
    memory_size: int = 100000
    
    # Data parameters
    data_source: DataSource = DataSource.CCXT
    symbols: list[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    timeframe: str = "1h"
    lookback_window: int = 50
    
    # Training parameters
    total_episodes: int = 1000
    steps_per_episode: int = 1000
    eval_frequency: int = 50
    
    # Risk management
    stop_loss: float = 0.05    # 5% max loss per trade
    max_drawdown: float = 0.20 # 20% max portfolio drawdown
    risk_free_rate: float = 0.02  # 2% annual
    
    # Firebase configuration
    firebase_project_id: Optional[str] = None
    firestore_collection: str = "arlet_trading"
    
    # Path configurations
    model_checkpoint_path: str = "./checkpoints/"
    log_path: str = "./logs/"
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_parameters()
        self._setup_logging()
        self._init_firebase()
    
    def _validate_parameters(self):
        """Validate all configuration parameters"""
        if self.initial_balance <= 0:
            raise ValueError("Initial balance must be positive")
        if not 0 < self.max_position_size <= 1:
            raise ValueError("Max position size must be between 0 and 1")
        if self.learning_rate <= 0:
            raise ValueError("Learning rate must be positive")
        if not 0 <= self.discount_factor <= 1:
            raise ValueError("Discount factor must be between 0 and 1")
        
        # Load from environment variables if present
        env_balance = os.getenv("ARLET_INITIAL_BALANCE")
        if env_balance:
            self.initial_balance = float(env_balance)
        
        self.firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")
    
    def _setup_logging(self):
        """Configure structured logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f"{self.log_path}arlet_{os.getpid()}.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("ARLET")
    
    def _init_firebase(self):
        """Initialize Firebase connection"""
        if self.firebase_project_id:
            try:
                # Try to get credentials from environment
                cred_dict = {
                    "type": os.getenv("FIREBASE_TYPE"),
                    "project_id": self.firebase_project_id,
                    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                    "private_key": os.getenv("FIREBASE_PRIVATE_KEY"),
                    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
                }
                
                # Filter out None values
                cred_dict = {k: v for k, v in cred_dict.items() if v is not None}
                
                if cred_dict:
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                    self.db: Client = firestore.client()
                    self.logger.info("Firebase initialized successfully")
                else:
                    self.logger.warning("Firebase credentials not found, using local mode")
                    self.db = None
            except Exception as e:
                self.logger.error(f"Firebase initialization failed: {e}")
                self.db =