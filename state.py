"""
State Management Module.
Handles persistent storage of automation state using a JSON file.
Ensures automation can resume exactly where it left off after a restart.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class StateManager:
    """
    Manages the persistent state of the automation process.
    Uses a JSON file to keep track of indexes, repeat modes, and upload history.
    """
    
    def __init__(self, state_file_path: str):
        self.state_file_path = state_file_path
        self.state_data: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Loads state from the JSON file, or returns a fresh state if it doesn't exist."""
        if os.path.exists(self.state_file_path):
            try:
                with open(self.state_file_path, 'r', encoding='utf-8') as f:
                    logger.info(f"Loading existing state from {self.state_file_path}")
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("State file is corrupted. Initializing new state.")
            except Exception as e:
                logger.error(f"Error reading state file: {str(e)}")
        
        logger.info("Initializing new state.")
        return {
            "channels": {},
            "global_image_state": {
                "current_index": 0,
                "repeat_position": 0,
                "is_repeating": False
            }
        }

    def _save_state(self) -> bool:
        """Saves the current state dictionary back to the JSON file."""
        try:
            with open(self.state_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.state_data, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Failed to save state: {str(e)}")
            return False

    def get_channel_state(self, channel_name: str) -> Dict[str, Any]:
        """
        Retrieves the state for a specific channel.
        Initializes default values if the channel doesn't exist in state yet.
        """
        name_key = channel_name.lower()
        if name_key not in self.state_data["channels"]:
            self.state_data["channels"][name_key] = {
                "current_video_index": 0,
                "video_repeat_position": 0,
                "is_video_repeating": False,
                "last_uploaded_file": "",
                "last_upload_time": ""
            }
            self._save_state()
        return self.state_data["channels"][name_key]

    def update_video_index(self, channel_name: str, new_index: int, filename: str):
        """Updates the current video index and last uploaded file for a channel."""
        state = self.get_channel_state(channel_name)
        state["current_video_index"] = new_index
        state["last_uploaded_file"] = filename
        state["last_upload_time"] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        self._save_state()
        logger.info(f"State updated for {channel_name}: Video Index -> {new_index}")

    def set_video_repeat_mode(self, channel_name: str, is_repeating: bool, repeat_position: int):
        """Toggles video repeat mode and sets the position to repeat from."""
        state = self.get_channel_state(channel_name)
        state["is_video_repeating"] = is_repeating
        state["video_repeat_position"] = repeat_position
        self._save_state()
        mode_str = "REPEAT" if is_repeating else "NEW CONTENT"
        logger.info(f"{channel_name} switched to {mode_str} mode. Repeat Pos: {repeat_position}")

    def update_image_index(self, new_index: int):
        """Updates the global current image index."""
        self.state_data["global_image_state"]["current_index"] = new_index
        self._save_state()
        logger.info(f"Global Image Index updated -> {new_index}")

    def set_image_repeat_mode(self, is_repeating: bool, repeat_position: int):
        """Toggles global image repeat mode."""
        img_state = self.state_data["global_image_state"]
        img_state["is_repeating"] = is_repeating
        img_state["repeat_position"] = repeat_position
        self._save_state()
        mode_str = "REPEAT" if is_repeating else "NEW CONTENT"
        logger.info(f"Global Image state switched to {mode_str} mode. Repeat Pos: {repeat_position}")

    def get_image_state(self) -> Dict[str, Any]:
        """Returns the global image distribution state."""
        return self.state_data["global_image_state"]

    def is_video_repeating(self, channel_name: str) -> bool:
        """Checks if a specific channel is currently in video repeat mode."""
        return self.get_channel_state(channel_name).get("is_video_repeating", False)

    def is_image_repeating(self) -> bool:
        """Checks if the global image distribution is in repeat mode."""
        return self.state_data["global_image_state"].get("is_repeating", False)

    def stop_repeat_on_new_content(self, channel_name: str = None, is_image: bool = False):
        """
        Stops repeat mode if new content is added.
        When new content is uploaded, repeat stops and normal sequential upload resumes.
        """
        if is_image:
            if self.is_image_repeating():
                self.set_image_repeat_mode(False, 0)
                logger.info("New image content detected. Stopping global image repeat.")
        else:
            if channel_name and self.is_video_repeating(channel_name):
                self.set_video_repeat_mode(channel_name, False, 0)
                logger.info(f"New video content detected for {channel_name}. Stopping video repeat.")