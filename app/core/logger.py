import logging
from logging.handlers import RotatingFileHandler
import os

# Create a logs directory at the root of the project if it doesn't exist
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Setup the logger
logger = logging.getLogger("timesheet_app")
logger.setLevel(logging.INFO)

# Create formatters
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Create handlers
if not logger.handlers:
    # Rotating file handler (5MB per file, keeps last 5 logs)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(log_format)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    
    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
