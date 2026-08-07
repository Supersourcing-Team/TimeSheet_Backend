from google.oauth2 import id_token
from google.auth.transport import requests
from typing import Optional, Dict, Any
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

def verify_google_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies a Google ID token and returns the payload if valid.
    """
    try:
        client_id = settings.GOOGLE_CLIENT_ID
        if not client_id:
            logger.warning("GOOGLE_CLIENT_ID is not set. Google token verification might fail or be bypassed for testing.")
            
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
        return idinfo
    except ValueError as e:
        logger.error(f"Invalid Google token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error verifying Google token: {e}")
        return None
