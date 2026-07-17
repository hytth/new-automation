"""
Configuration Manager for the Automation System.
Loads environment variables and provides a centralized configuration object.
"""

import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Optional

# Load environment variables from .env file
load_dotenv()

@dataclass
class NotificationConfig:
    """Configuration for Email and Telegram notifications."""
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    sender_email: str = field(default_factory=lambda: os.getenv("SENDER_EMAIL", ""))
    sender_email_app_password: str = field(default_factory=lambda: os.getenv("SENDER_EMAIL_APP_PASSWORD", ""))
    receiver_email: str = field(default_factory=lambda: os.getenv("RECEIVER_EMAIL", ""))

@dataclass
class VpnConfig:
    """Configuration for NordVPN connection."""
    nordvpn_cmd_path: str = field(default_factory=lambda: os.getenv("NORDVPN_CMD_PATH", "C:/Program Files (x86)/NordVPN/NordVPN.exe"))
    nordvpn_server: str = field(default_factory=lambda: os.getenv("NORDVPN_SERVER", "United States"))
    nordvpn_city: str = field(default_factory=lambda: os.getenv("NORDVPN_CITY", "New York"))
    max_retries: int = 3
    retry_delay_seconds: int = 3

@dataclass
class PathsConfig:
    """Configuration for file and folder paths."""
    credentials_folder_path: str = field(default_factory=lambda: os.getenv("CREDENTIALS_FOLDER_PATH", "./"))
    sheet_link_file_path: str = field(default_factory=lambda: os.getenv("SHEET_LINK_FILE_PATH", "./Sheet Link"))
    facebook_api_file_path: str = field(default_factory=lambda: os.getenv("FACEBOOK_API_FILE_PATH", "./facebook page api.txt"))
    state_file_path: str = field(default_factory=lambda: os.getenv("STATE_FILE_PATH", "./state.json"))

@dataclass
class YoutubeConfig:
    """Configuration specific to YouTube uploads."""
    upload_category_id: str = field(default_factory=lambda: os.getenv("YOUTUBE_UPLOAD_CATEGORY_ID", "22"))
    upload_privacy_status: str = field(default_factory=lambda: os.getenv("YOUTUBE_UPLOAD_PRIVACY_STATUS", "private"))
    upload_self_declared_made_for_kids: bool = field(default_factory=lambda: os.getenv("YOUTUBE_UPLOAD_SELF_DECLARED_MADE_FOR_KIDS", "False").lower() == "true")
    scopes: list[str] = field(default_factory=lambda: [
        'https://www.googleapis.com/auth/youtube.upload',
        'https://www.googleapis.com/auth/youtube.readonly'
    ])

@dataclass
class FacebookConfig:
    """Configuration specific to Facebook uploads."""
    publish_status: str = field(default_factory=lambda: os.getenv("FACEBOOK_PUBLISH_STATUS", "SCHEDULED"))
    api_version: str = "v19.0"

@dataclass
class SystemConfig:
    """Main configuration class holding all sub-configurations."""
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    vpn: VpnConfig = field(default_factory=VpnConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    youtube: YoutubeConfig = field(default_factory=YoutubeConfig)
    facebook: FacebookConfig = field(default_factory=FacebookConfig)

def get_config() -> SystemConfig:
    """Returns the singleton configuration instance."""
    return SystemConfig()
