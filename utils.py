"""
Utility functions for logging, retries, decorators, and common helpers.
"""

import os
import time
import logging
import functools
import requests
from typing import Callable, Any, Optional, List, Dict
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def retry(max_attempts: int = 3, delay: int = 5, backoff: int = 2, allowed_exceptions: tuple = (Exception,)):
    """
    Decorator to retry a function on failure.
    
    :param max_attempts: Maximum number of retry attempts.
    :param delay: Initial delay in seconds.
    :param backoff: Multiplier for delay after each attempt.
    :param allowed_exceptions: Tuple of exceptions that trigger a retry.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {str(e)}")
                    if attempt < max_attempts:
                        logger.info(f"Retrying in {current_delay} seconds...")
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception
        return wrapper
    return decorator

def read_file_contents(file_path: str, encoding: str = 'utf-8') -> str:
    """
    Safely reads the entire contents of a file.
    
    :param file_path: Path to the file.
    :param encoding: File encoding.
    :return: File contents as string.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"Required file missing: {file_path}")
    
    with open(file_path, 'r', encoding=encoding) as f:
        return f.read().strip()

def parse_facebook_api_file(file_path: str) -> Dict[str, Dict[str, str]]:
    """
    Parses the Facebook API text file into a structured dictionary.
    Expected format per block:
    Page Name
    Page Access Token
    Page ID
    
    :param file_path: Path to the facebook page api.txt file.
    :return: Dictionary mapping Page Name to {'token': str, 'id': str}
    """
    content = read_file_contents(file_path)
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    
    fb_creds = {}
    if len(lines) % 3 != 0:
        logger.error("Facebook API file format is invalid. Expected multiples of 3 lines.")
        raise ValueError("Invalid Facebook API file format.")
    
    for i in range(0, len(lines), 3):
        page_name = lines[i].lower()
        token = lines[i+1]
        page_id = lines[i+2]
        fb_creds[page_name] = {
            "token": token,
            "id": page_id
        }
        logger.info(f"Parsed Facebook credentials for: {page_name}")
        
    return fb_creds

def extract_sheet_id_from_url(sheet_url: str) -> str:
    """
    Extracts the Google Sheet ID from its URL.
    
    :param sheet_url: Full Google Sheets URL.
    :return: The Sheet ID string.
    """
    try:
        start_idx = sheet_url.find("/d/") + 3
        end_idx = sheet_url.find("/", start_idx)
        if start_idx == -1 or end_idx == -1:
            raise ValueError("Invalid Google Sheet URL format.")
        return sheet_url[start_idx:end_idx]
    except Exception as e:
        logger.error(f"Failed to parse Sheet URL: {sheet_url} - {str(e)}")
        raise

def get_current_utc_time() -> str:
    """Returns the current UTC time in ISO 8601 format."""
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

def sanitize_filename(filename: str) -> str:
    """
    Removes invalid characters from a string to make it a valid filename/title.
    Removes file extensions like .mp4, .jpg, .png.
    
    :param filename: The original filename.
    :return: Sanitized string.
    """
    name = os.path.splitext(filename)[0]
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    return name.strip()

def get_public_ip() -> Optional[str]:
    """
    Fetches the current public IP address of the machine.
    
    :return: IP address as string, or None if failed.
    """
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=10)
        response.raise_for_status()
        return response.json().get('ip')
    except Exception as e:
        logger.error(f"Failed to fetch public IP: {str(e)}")
        return None