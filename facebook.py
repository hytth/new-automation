"""
Facebook Graph API Integration.
Handles video uploads, image uploads, and scheduling for Pages.
"""

import os
import logging
import requests
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class FacebookManager:
    def __init__(self):
        self.api_version = "v19.0"
        self.page_token = ""
        self.page_id = ""
        self.page_name = ""

    def set_credentials(self, page_name: str, token: str, page_id: str):
        self.page_name = page_name
        self.page_token = token
        self.page_id = page_id

    def _make_api_call(self, url: str, payload: dict = None, method: str = "POST", files: dict = None) -> Optional[dict]:
        """Generic wrapper for FB API calls."""
        if not self.page_token:
            logger.error("Facebook token not set.")
            return None
            
        if 'access_token' not in url:
            if not payload: payload = {}
            payload['access_token'] = self.page_token

        try:
            if method == "POST":
                response = requests.post(url, data=payload, files=files, timeout=300) # 5 min timeout for uploads
            elif method == "GET":
                response = requests.get(url, params=payload, timeout=30)
            else:
                return None

            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"FB API HTTP Error: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"FB Network Error: {e}")
            return None

    def upload_video(self, file_path: str, title: str, description: str, schedule_time: str) -> Optional[tuple[str, str]]:
        """
        Uploads video to page, optionally schedules it.
        Returns Tuple (Video_ID, Video_URL) or None.
        """
        url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/videos"
        
        payload = {
            "title": title,
            "description": description,
            "publish_status": "SCHEDULED" if schedule_time else "PUBLISHED"
        }
        
        if schedule_time:
            # FB expects UNIX timestamp or ISO8601
            payload["scheduled_publish_time"] = schedule_time 

        try:
            with open(file_path, 'rb') as f:
                files = {'source': f}
                response = requests.post(url, data=payload, files=files, timeout=600) # 10 min for large vids
                response.raise_for_status()
                data = response.json()
                
            video_id = data.get('id')
            # To get the actual URL, we might need to query the video ID, or construct it
            video_url = f"https://www.facebook.com/{self.page_id}/videos/{video_id}/"
            
            logger.info(f"Successfully uploaded/scheduled to Facebook. ID: {video_id}")
            return video_id, video_url
        except Exception as e:
            logger.error(f"Failed to upload to Facebook: {str(e)}")
            return None

    def upload_image(self, file_path: str, caption: str, schedule_time: str = None) -> Optional[tuple[str, str]]:
        """
        Uploads image to page. If scheduled, creates an unpublished post and schedules it.
        FB image scheduling requires a two-step process: upload unpublished, then schedule post.
        """
        # Step 1: Upload unpublished photo
        url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/photos"
        payload = {
            "published": "false",
            "caption": caption
        }
        
        photo_id = None
        try:
            with open(file_path, 'rb') as f:
                files = {'source': f}
                res = requests.post(url, data=payload, files=files, timeout=120).json()
                photo_id = res.get('id')
        except Exception as e:
            logger.error(f"Failed to upload image to FB: {e}")
            return None

        if not photo_id: return None

        if not schedule_time:
            # Publish immediately
            pub_url = f"https://graph.facebook.com/{self.api_version}/{photo_id}"
            self._make_api_call(pub_url, {"published": "true"}, method="POST")
            return photo_id, f"https://www.facebook.com/photo.php?fbid={photo_id}"
        else:
            # Step 2: Create scheduled post with the unpublished photo
            post_url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/feed"
            post_payload = {
                "message": caption,
                "attached_media": f'{{"media_fbid": "{photo_id}"}}',
                "published": "false",
                "scheduled_publish_time": schedule_time
            }
            post_res = self._make_api_call(post_url, post_payload, method="POST")
            post_id = post_res.get('id') if post_res else None
            return photo_id, f"https://www.facebook.com/{post_id}" if post_id else None
