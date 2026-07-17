"""
Copyright Compliance & Auto-Deletion System (Strict Dual-Platform Rule).
1. YT Copyright -> Delete from YT only.
2. FB Copyright -> Delete from FB only.
3. YT + FB Copyright -> Delete from YT, FB, AND Google Drive.
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class ComplianceChecker:
    def __init__(self, drive_manager, notification_service):
        self.drive_manager = drive_manager
        self.notifier = notification_service

    def _extract_id_from_link(self, link: str, platform: str) -> Optional[str]:
        """Helper to extract Video ID from URL."""
        if not link: return None
        if platform == 'youtube':
            if 'watch?v=' in link: return link.split('watch?v=')[-1].split('&')[0]
            elif 'youtu.be/' in link: return link.split('youtu.be/')[-1].split('?')[0]
        elif platform == 'facebook':
            parts = link.split('/')
            for p in reversed(parts):
                if p.isdigit() and len(p) > 5: return p
        return None

    def check_youtube_copyright(self, yt_service, video_id: str) -> bool:
        """Returns True if a severe issue/copyright is found on YouTube."""
        try:
            response = yt_service.videos().list(part='status', id=video_id).execute()
            items = response.get('items', [])
            if not items: return True # Video completely removed by YT
            
            status = items[0].get('status', {})
            upload_status = status.get('uploadStatus')
            rejection_reason = status.get('rejectionReason', '')
            
            if upload_status != 'processed': # rejected, deleted, failed
                logger.error(f"YT Violation: ID {video_id} | Status: {upload_status} | Reason: {rejection_reason}")
                return True
            return False
        except HttpError as e:
            logger.error(f"Error checking YT video {video_id}: {str(e)}")
            return False

    def check_facebook_copyright(self, page_token: str, video_id: str, api_version: str = "v19.0") -> bool:
        """Returns True if a severe issue/copyright is found on Facebook."""
        try:
            url = f"https://graph.facebook.com/{api_version}/{video_id}?fields=status_code&access_token={page_token}"
            response = requests.get(url, timeout=10).json()
            
            if 'error' in response: return True # Deleted or invalid
            
            status_code = response.get('status_code', '')
            if status_code in ['unpublished', 'deleted', 'failed']: return True
            return False
        except Exception as e:
            logger.error(f"Error checking FB video {video_id}: {str(e)}")
            return False

    def execute_daily_compliance_check(self, history_data: List[Dict[str, Any]], yt_creds_map: Dict, fb_creds_map: Dict):
        """
        Main runner. Groups records by video title to check BOTH platforms before deleting from Drive.
        """
        logger.info("Starting daily copyright compliance check (Strict Dual-Platform Rule)...")
        
        # We use a tracker to group YouTube and Facebook records of the SAME video.
        # Key: Video Title, Value: Dict tracking violations and Drive ID.
        violation_tracker = {}

        for record in history_data:
            platform = record.get('platform', '').lower()
            link = record.get('link', '')
            channel = record.get('channel', '')
            status = record.get('status', '')
            video_title = record.get('title', 'Unknown Video')
            drive_file_id = record.get('drive_id', '') # Assumption: We save Drive ID in history

            if status.lower() != 'success': continue

            # Initialize tracker for this video if not exists
            if video_title not in violation_tracker:
                violation_tracker[video_title] = {
                    "yt_violation": False,
                    "fb_violation": False,
                    "drive_id": drive_file_id,
                    "channel": channel
                }

            video_id = self._extract_id_from_link(link, platform)
            if not video_id: continue

            # --- CHECK YOUTUBE ---
            if platform == 'youtube' and channel in yt_creds_map:
                yt_service = build('youtube', 'v3', credentials=yt_creds_map[channel])
                is_violation = self.check_youtube_copyright(yt_service, video_id)
                
                if is_violation:
                    logger.critical(f"Copyright on YouTube for: {video_title}. Deleting from YT...")
                    try:
                        yt_service.videos().delete(id=video_id).execute()
                        logger.info(f"Successfully deleted {video_title} from YouTube.")
                    except Exception as e:
                        logger.error(f"Failed to delete from YT: {str(e)}")
                    
                    violation_tracker[video_title]["yt_violation"] = True

            # --- CHECK FACEBOOK ---
            elif platform == 'facebook' and channel in fb_creds_map:
                fb_token = fb_creds_map[channel]['token']
                is_violation = self.check_facebook_copyright(fb_token, video_id)
                
                if is_violation:
                    logger.critical(f"Copyright on Facebook for: {video_title}. Deleting from FB...")
                    try:
                        requests.delete(f"https://graph.facebook.com/v19.0/{video_id}?access_token={fb_token}")
                        logger.info(f"Successfully deleted {video_title} from Facebook.")
                    except Exception as e:
                        logger.error(f"Failed to delete from FB: {str(e)}")
                    
                    violation_tracker[video_title]["fb_violation"] = True

            # --- CRITICAL CHECK: DELETE FROM DRIVE IF BOTH VIOLATE ---
            tracker_state = violation_tracker[video_title]
            if tracker_state["yt_violation"] and tracker_state["fb_violation"]:
                logger.critical(f"DUAL VIOLATION DETECTED for {video_title}! Deleting from Google Drive...")
                
                if tracker_state["drive_id"] and self.drive_manager:
                    self.drive_manager.delete_file_by_id(tracker_state["drive_id"])
                
                self.notifier.alert_copyright_violation(
                    channel_name=tracker_state["channel"],
                    video_title=video_title,
                    platform="YouTube & Facebook (Both)",
                    reason="Dual Platform Violation - Removed from Drive"
                )
                
                # Reset flags to prevent multiple delete attempts in future runs
                tracker_state["yt_violation"] = False
                tracker_state["fb_violation"] = False