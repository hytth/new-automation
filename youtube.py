"""
YouTube API Integration.
Handles video uploading, and scheduling.
"""

import os
import logging
from typing import Optional, Dict
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from config import get_config

logger = logging.getLogger(__name__)

class YouTubeManager:
    def __init__(self):
        self.config = get_config().youtube
        self.service = None
        self.channel_name = ""

    def upload_and_schedule(self, file_path: str, title: str, description: str, tags: list, schedule_time: str) -> Optional[str]:
        """
        Uploads a video, sets it to private, and schedules it.
        Returns the Video ID if successful, None otherwise.
        """
        if not self.service: 
            logger.error("YouTube Service not initialized.")
            return None

        try:
            request_body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'categoryId': self.config.upload_category_id
                },
                'status': {
                    'privacyStatus': self.config.upload_privacy_status,
                    'publishAt': schedule_time,
                    'selfDeclaredMadeForKids': self.config.upload_self_declared_made_for_kids
                }
            }

            media_file = MediaFileUpload(
                file_path, 
                resumable=True, 
                chunksize=10*1024*1024 
            )

            request = self.service.videos().insert(
                part='snippet,status',
                body=request_body,
                media_body=media_file
            )

            response = request.execute()
            video_id = response.get('id')
            logger.info(f"✅ Successfully uploaded & scheduled to YouTube. ID: {video_id}")
            return video_id

        except Exception as e:
            error_str = str(e)
            if 'quotaExceeded' in error_str:
                logger.error("🛑 YouTube Daily Quota Exceeded!")
            else:
                logger.error(f"❌ YouTube Upload Error: {error_str}")
            return None