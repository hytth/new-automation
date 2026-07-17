"""
Google Sheets Integration.
Reads Schedule & History tabs, updates indexes and records.
"""

import pickle
import logging
from typing import Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import get_config
from utils import read_file_contents, extract_sheet_id_from_url, get_current_utc_time

logger = logging.getLogger(__name__)

class GoogleSheetManager:
    def __init__(self):
        self.config = get_config()
        self.service = None
        self.sheet_id = None
        self.schedule_data = []
        self.history_tab_name = "History"

    def connect(self, pickle_path: str):
        """Authenticates using the provided token pickle file."""
        try:
            with open(pickle_path, 'rb') as token:
                creds = pickle.load(token)
            self.service = build('sheets', 'v4', credentials=creds)
            logger.info("Google Sheets API authenticated successfully.")
        except Exception as e:
            logger.error(f"Failed to authenticate Google Sheets: {str(e)}")
            raise

    def load_sheet(self):
        """Reads the Sheet Link file and loads the Schedule tab data."""
        try:
            sheet_url = read_file_contents(self.config.paths.sheet_link_file_path)
            self.sheet_id = extract_sheet_id_from_url(sheet_url)
            
            # Read Schedule Tab (Assuming it's the first tab, or named 'Schedule')
            range_name = "Schedule!A1:Z100"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id, range=range_name).execute()
            
            rows = result.get('values', [])
            if not rows:
                logger.error("No data found in Schedule tab.")
                return

            headers = [str(h).strip().lower() for h in rows[0]]
            self.schedule_data = []
            
            for row in rows[1:]:
                if not row: continue
                row_data = dict(zip(headers, row))
                self.schedule_data.append(row_data)
                
            logger.info(f"Loaded {len(self.schedule_data)} channels from Google Sheet.")
        except Exception as e:
            logger.error(f"Failed to load Google Sheet: {str(e)}")
            raise

    def get_channel_schedule(self, channel_name: str) -> Optional[dict[str, Any]]:
        """Finds the specific row data for a channel by name."""
        name_lower = channel_name.lower()
        for row in self.schedule_data:
            if row.get('channel name', '').lower() == name_lower:
                return row
        return None

    def _find_column_index(self, headers: list[str], target: str) -> int:
        """Finds the index of a column header, case-insensitive."""
        for i, h in enumerate(headers):
            if target.lower() in h.lower():
                return i
        return -1

    def update_history(self, channel_name: str, content_type: str, platform: str, link: str, status: str, error_reason: str = ""):
        """Appends a new row to the History tab."""
        try:
            # Read History tab headers to append at the end
            hist_range = f"{self.history_tab_name}!A1:H1"
            headers_res = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id, range=hist_range).execute()
            
            # Calculate next empty row
            next_row = 2 
            if headers_res.get('values'):
                # In a real scenario, you'd find the last row, but appending to 1000 is safe for this scale
                pass 

            append_range = f"{self.history_tab_name}!A{next_row}"
            values = [[
                get_current_utc_time().split('T')[0], # Date
                channel_name,
                content_type,
                link,
                platform,
                get_current_utc_time(), # Time
                status,
                error_reason
            ]]
            
            body = {'values': values}
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id, range=append_range,
                valueInputOption="USER_ENTERED", body=body).execute()
            logger.info(f"History updated for {channel_name} -> {status}")
        except HttpError as e:
            logger.error(f"API Error updating history: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to update history: {str(e)}")

    def update_cell(self, tab_name: str, row_idx: int, col_letter: str, value: Any):
        """Updates a specific cell in the sheet."""
        try:
            cell_range = f"{tab_name}!{col_letter}{row_idx}"
            body = {'values': [[value]]}
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id, range=cell_range,
                valueInputOption="USER_ENTERED", body=body).execute()
        except Exception as e:
            logger.error(f"Failed to update cell {cell_range}: {str(e)}")
