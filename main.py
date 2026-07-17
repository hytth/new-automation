"""
Main Entry Point.
Initializes all services and starts the automation process.
Works seamlessly on both Local (Pickle) and GitHub Actions (JSON).
"""

import os
import logging
import pickle
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

from config import get_config
from utils import read_file_contents, parse_facebook_api_file
from sheet import GoogleSheetManager
from drive import DriveManager
from youtube import YouTubeManager
from facebook import FacebookManager
from state import StateManager
from notification import NotificationService
from vpn import VpnManager
from upload_manager import UploadManager
from compliance import ComplianceChecker

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('automation.log')
    ]
)
logger = logging.getLogger(__name__)

def get_google_creds(file_path: str, scopes: list):
    """Helper to load credentials from either Pickle or Service Account JSON."""
    if file_path.endswith('.pickle') and os.path.exists(file_path):
        with open(file_path, 'rb') as token:
            creds = pickle.load(token)
        # Auto-refresh if expired (Works locally)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds
    elif file_path.endswith('.json') and os.path.exists(file_path):
        return service_account.Credentials.from_service_account_file(file_path, scopes=scopes)
    return None

def find_credential_file(folder_path: str, base_name: str, file_type: str) -> str:
    """Finds a file dynamically based on channel name (e.g., client_secret_comedy blast.json)."""
    clean_name = base_name.lower().replace(" ", "")
    for f in os.listdir(folder_path):
        if f.endswith(f'.{file_type}'):
            f_clean = f.lower().replace(" ", "").replace(f'.{file_type}', "")
            if clean_name in f_clean:
                return os.path.join(folder_path, f)
    return ""

def load_youtube_managers(folder_path: str, channel_names: list) -> dict:
    """Dynamically loads YouTube managers using Pickle or JSON."""
    managers = {}
    for name in channel_names:
        # Try to find matching file
        json_file = find_credential_file(folder_path, name, "json")
        pickle_file = find_credential_file(folder_path, name, "pickle")

        creds = None
        cred_file_used = ""

        if pickle_file:
            creds = get_google_creds(pickle_file, ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly'])
            cred_file_used = pickle_file
        elif json_file:
            creds = get_google_creds(json_file, ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly'])
            cred_file_used = json_file

        if creds:
            try:
                yt = YouTubeManager()
                yt.service = build('youtube', 'v3', credentials=creds)
                yt.channel_name = name
                managers[name.lower()] = yt
                logger.info(f"✅ Loaded YouTube Manager for: {name} (Using {cred_file_used})")
            except Exception as e:
                logger.error(f"❌ Failed to load YT Manager for {name}: {e}")
        else:
            logger.warning(f"⚠️ No JSON or Pickle found for: {name}")
            
    return managers

def main():
    logger.info("="*50)
    logger.info("🚀 STARTING AUTOMATION SYSTEM")
    logger.info("="*50)

    config = get_config()
    notifier = NotificationService()
    folder_path = config.paths.credentials_folder_path

    try:
        # 1. Connect VPN
        vpn = VpnManager()
        if not vpn.connect():
            notifier.alert_vpn_failure(config.vpn.max_retries, "Failed to establish connection")
            logger.critical("Stopping automation due to VPN failure.")
            return

        # 2. Initialize State
        state = StateManager(config.paths.state_file_path)

        # 3. Load Google Sheet (Tries Pickle first, then JSON)
        sheet = GoogleSheetManager()
        sheet_pickle = find_credential_file(folder_path, "sheet", "pickle")
        sheet_json = find_credential_file(folder_path, "sheet", "json")
        
        sheet_creds = None
        if sheet_pickle:
            sheet_creds = get_google_creds(sheet_pickle, ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        elif sheet_json:
            sheet_creds = get_google_creds(sheet_json, ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
            
        if not sheet_creds:
            logger.error("❌ Sheet credentials (JSON/Pickle) not found!")
            return

        sheet.service = build('sheets', 'v4', credentials=sheet_creds)
        sheet.load_sheet()
        channel_names = [row.get('channel name', '') for row in sheet.schedule_data if row.get('channel name')]

        # 4. Load Drive Manager
        drive = DriveManager(sheet_creds)

        # 5. Load YouTube Managers
        yt_managers = load_youtube_managers(folder_path, channel_names)

        # 6. Load Facebook Managers
        fb_creds_data = parse_facebook_api_file(config.paths.facebook_api_file_path)
        fb_managers = {}
        for name in channel_names:
            name_lower = name.lower()
            if name_lower in fb_creds_data:
                fb = FacebookManager()
                fb.set_credentials(name, fb_creds_data[name_lower]['token'], fb_creds_data[name_lower]['id'])
                fb_managers[name_lower] = fb
                logger.info(f"✅ Loaded Facebook Manager for: {name}")
            else:
                logger.warning(f"⚠️ Facebook credentials missing for: {name}")
                notifier.alert_missing_credentials(name, "Facebook Token/ID")

        # 7. Initialize Compliance Checker
        compliance = ComplianceChecker(drive, notifier)

        # 8. Initialize Upload Manager & Run Scheduler
        upload_mgr = UploadManager(sheet, drive, yt_managers, fb_managers, state, notifier)
        upload_mgr.run_daily_schedule()

        logger.info("✅ Automation cycle completed successfully.")

    except Exception as e:
        logger.critical(f"🚨 FATAL ERROR IN MAIN: {str(e)}", exc_info=True)
        notifier.send_telegram_message(f"🚨 *FATAL ERROR*\n\n{str(e)}")
        notifier.send_email("Automation Fatal Error", str(e))

if __name__ == "__main__":
    main()