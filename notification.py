"""
Notification System.
Sends alerts via Telegram and Email for missing files, VPN failures, or copyright issues.
"""

import smtplib
import requests
import logging
from typing import Optional
from config import get_config

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.config = get_config().notification

    def send_telegram_message(self, message: str) -> bool:
        """Sends a message to the specified Telegram chat."""
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.warning("Telegram credentials not set. Skipping Telegram notification.")
            return False
            
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Telegram notification sent successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {str(e)}")
            return False

    def send_email(self, subject: str, body: str) -> bool:
        """Sends an email alert."""
        if not all([self.config.sender_email, self.config.sender_email_app_password, self.config.receiver_email]):
            logger.warning("Email credentials not set. Skipping Email notification.")
            return False

        try:
            msg = f"Subject: {subject}\n\n{body}"
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.config.sender_email, self.config.sender_email_app_password)
            server.sendmail(self.config.sender_email, self.config.receiver_email, msg)
            server.quit()
            logger.info("Email notification sent successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to send Email: {str(e)}")
            return False

    def alert_missing_credentials(self, channel_name: str, missing_item: str):
        """Alerts that a specific credential is missing for a channel."""
        msg = f"🚨 *MISSING CREDENTIALS*\n\nChannel: *{channel_name}*\nMissing: *{missing_item}*\nAutomation paused for this channel."
        self.send_telegram_message(msg)
        self.send_email(f"Automation Paused: {channel_name}", msg.replace('*', ''))

    def alert_vpn_failure(self, retries: int, error: str):
        """Alerts that NordVPN failed to connect."""
        msg = f"🛑 *VPN CONNECTION FAILED*\n\nRetries: {retries}\nError: {error}\nUpload process safely stopped."
        self.send_telegram_message(msg)
        self.send_email("Critical: VPN Connection Failed", msg.replace('*', ''))

    def alert_copyright_violation(self, channel_name: str, video_title: str, platform: str, reason: str):
        """Alerts that a video was deleted due to copyright."""
        msg = f"⚠️ *COPYRIGHT STRIKE DETECTED & DELETED*\n\nChannel: *{channel_name}*\nPlatform: *{platform}*\nVideo: {video_title}\nReason: {reason}\n\nVideo deleted from YT, FB, and Google Drive."
        self.send_telegram_message(msg)
        self.send_email(f"Copyright Alert: {channel_name}", msg.replace('*', ''))