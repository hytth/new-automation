"""
Upload Manager: The Brain of the Automation.
Handles scheduling logic, sequential uploads, repeat mode, and history updates.
"""

import os
import time
import logging
from datetime import datetime
from typing import Any, Optional
from google.oauth2 import service_account
import pytz

from sheet import GoogleSheetManager
from drive import DriveManager
from youtube import YouTubeManager
from facebook import FacebookManager
from state import StateManager
from notification import NotificationService
from utils import sanitize_filename, get_current_utc_time

logger = logging.getLogger(__name__)

class UploadManager:
    def __init__(self, sheet_manager: GoogleSheetManager, drive_manager: DriveManager, 
                 yt_managers: dict, fb_managers: dict, state_manager: StateManager, 
                 notification: NotificationService):
        self.sheet = sheet_manager
        self.drive = drive_manager
        self.yt_managers = yt_managers
        self.fb_managers = fb_managers
        self.state = state_manager
        self.notifier = notification

    def _get_time_slots(self, row_data: dict, prefix: str) -> list:
        """Dynamically extracts all time slots (Time_1, Time_2... Time_N) from sheet row."""
        times = []
        for key, val in row_data.items():
            if prefix.lower() in key.lower() and 'time' in key.lower() and val:
                times.append(val.strip())
        return times

    def _is_time_to_upload(self, time_slots: list) -> bool:
        """Checks if current time matches any of the scheduled time slots."""
        tz = pytz.timezone('America/New_York') # Assuming schedule is in NY time
        now_ny = datetime.now(tz).strftime("%H:%M")
        
        for slot in time_slots:
            # Handle different formats (e.g., "11:00" or "2026-06-29T11:00:00Z")
            if "T" in slot:
                clean_time = slot.split("T")[1].split(":")[0] + ":" + slot.split("T")[1].split(":")[1]
            else:
                clean_time = slot
                
            if now_ny == clean_time:
                return True
        return False

    def _find_matching_file(self, folder_id: str, current_index: int, is_image: bool = False) -> Optional[dict]:
        """Finds the file to upload based on current index."""
        ext = "jpg" if is_image else "mp4"
        mime_type = "image/jpeg" if is_image else "video/mp4"
        
        files = self.drive.list_files_in_folder(folder_id, ext if is_image else "mp4")
        # Sort files alphabetically to ensure sequential order
        files.sort(key=lambda x: x['name'])
        
        if current_index < len(files):
            return files[current_index]
        return None

    def run_daily_schedule(self):
        """Main loop that checks all channels and uploads if time matches."""
        logger.info("Starting Daily Schedule Check...")
        schedule_data = self.sheet.schedule_data
        
        for row in schedule_data:
            channel_name = row.get('channel name', '').strip()
            if not channel_name: continue

            # 1. Check YouTube Video Schedule
            yt_times = self._get_time_slots(row, "youtube video")
            if yt_times and self._is_time_to_upload(yt_times):
                self._process_video_upload(channel_name, row, "youtube")

            # 2. Check Facebook Video Schedule
            fb_vid_times = self._get_time_slots(row, "facebook video")
            if fb_vid_times and self._is_time_to_upload(fb_vid_times):
                self._process_video_upload(channel_name, row, "facebook")

        # 3. Check Image Distribution Schedule (Global)
        # Find the first row that has image times (assuming it's the same for all, or read from a specific row)
        # For simplicity, we read image times from the first row of the sheet
        if schedule_data:
            img_times = self._get_time_slots(schedule_data[0], "facebook image")
            if img_times and self._is_time_to_upload(img_times):
                self._process_image_distribution(schedule_data)

    def _process_video_upload(self, channel_name: str, row: dict, platform: str):
        """Handles downloading and uploading a single video for a specific platform."""
        logger.info(f"Time matched for {channel_name} on {platform}.")
        
        folder_id = row.get('drive folder id', '')
        ch_state = self.state.get_channel_state(channel_name)
        current_idx = ch_state['current_video_index']

        # Find file
        file_info = self._find_matching_file(folder_id, current_idx)
        if not file_info:
            logger.warning(f"No video found at index {current_idx} for {channel_name}. Starting REPEAT mode.")
            self.state.set_video_repeat_mode(channel_name, True, 0)
            file_info = self._find_matching_file(folder_id, 0)
            if not file_info:
                self.notifier.alert_missing_credentials(channel_name, "Videos finished & cannot repeat")
                return

        # Download
        local_path = f"temp_{channel_name.replace(' ', '_')}.mp4"
        if not self.drive.download_file(file_info['id'], file_info['name'], "."):
            self.sheet.update_history(channel_name, "Video", platform, "", "Failed", "Drive download failed")
            return

        title = sanitize_filename(file_info['name'])
        desc = f"Uploaded automatically via automation system."

        link = ""
        if platform == "youtube" and channel_name in self.yt_managers:
            yt = self.yt_managers[channel_name]
            times = self._get_time_slots(row, "youtube video")
            sched_time = times[0] if times else get_current_utc_time() # Fallback
            vid_id = yt.upload_and_schedule(local_path, title, desc, [], sched_time)
            link = f"https://youtube.com/watch?v={vid_id}" if vid_id else ""
            
        elif platform == "facebook" and channel_name in self.fb_managers:
            fb = self.fb_managers[channel_name]
            times = self._get_time_slots(row, "facebook video")
            sched_time = times[0] if times else None
            res = fb.upload_video(local_path, title, desc, sched_time)
            link = res[1] if res else ""

        # Cleanup local file
        if os.path.exists(local_path):
            os.remove(local_path)

        # Update State & History
        if link:
            status = "Success"
            next_idx = current_idx + 1
            self.state.update_video_index(channel_name, next_idx, title)
            self.sheet.update_history(channel_name, "Video", platform, link, status)
            self.sheet.update_cell("Schedule", int(row.get('row_number', 2)), "D", next_idx) # Update index in sheet
        else:
            self.sheet.update_history(channel_name, "Video", platform, "", "Failed", "Upload API failed")

    def _process_image_distribution(self, schedule_data: list):
        """Handles sequential image distribution across all channels."""
        img_state = self.state.get_image_state()
        current_idx = img_state['current_index']
        
        # Find image folder ID (Assuming it's the same for all, or read from first row)
        img_folder_id = schedule_data[0].get('image folder id', '')
        if not img_folder_id:
            logger.error("Image Folder ID not found in sheet.")
            return

        file_info = self._find_matching_file(img_folder_id, current_idx, is_image=True)
        if not file_info:
            logger.warning("Images finished. Starting Image REPEAT mode.")
            self.state.set_image_repeat_mode(True, 0)
            file_info = self._find_matching_file(img_folder_id, 0, is_image=True)
            if not file_info: return

        # Map image to channel based on index
        total_channels = len(schedule_data)
        channel_idx = current_idx % total_channels
        target_channel_name = schedule_data[channel_idx].get('channel name', '')
        
        local_path = f"temp_img_{file_info['name']}"
        if not self.drive.download_file(file_info['id'], file_info['name'], "."):
            return

        caption = f"Automated post: {sanitize_filename(file_info['name'])}"
        link = ""

        if target_channel_name in self.fb_managers:
            fb = self.fb_managers[target_channel_name]
            # Find FB Image times
            fb_img_times = self._get_time_slots(schedule_data[0], "facebook image")
            sched_time = fb_img_times[0] if fb_img_times else None
            res = fb.upload_image(local_path, caption, sched_time)
            link = res[1] if res else ""

        if os.path.exists(local_path): os.remove(local_path)

        if link:
            next_idx = current_idx + 1
            self.state.update_image_index(next_idx)
            self.sheet.update_history(target_channel_name, "Image", "Facebook", link, "Success")
            # Update Image Index in Sheet
            self.sheet.update_cell("Schedule", 2, "H", next_idx) # Assuming Image index is in H2
        else:
            self.sheet.update_history(target_channel_name, "Image", "Facebook", "", "Failed", "Image upload failed")
