"""
Google Drive Integration.
Handles downloading files, listing folders, and deleting source files.
"""

import os
import logging
import requests
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
import io

logger = logging.getLogger(__name__)

class DriveManager:
    def __init__(self, creds: Credentials):
        self.service = build('drive', 'v3', credentials=creds)
        self.downloaded_file_path = ""

    def list_files_in_folder(self, folder_id: str, file_extension: str = "mp4") -> list[dict]:
        """Lists all files of a specific extension in a Google Drive folder."""
        query = f"'{folder_id}' in parents and mimeType contains '{file_extension}' and trashed=false"
        fields = "nextPageToken, files(id, name)"
        items = []
        
        page_token = None
        while True:
            results = self.service.files().list(
                q=query, fields=fields, pageToken=page_token, orderBy="name").execute()
            items.extend(results.get('files', []))
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        return items

    def download_file(self, file_id: str, file_name: str, save_path: str) -> bool:
        """Downloads a file from Google Drive to local storage."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            full_path = os.path.join(save_path, file_name)
            
            fh = io.FileIO(full_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            self.downloaded_file_path = full_path
            logger.info(f"Downloaded {file_name} to {full_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {str(e)}")
            return False

    def delete_file_by_id(self, file_id: str):
        """
        Permanently deletes a file from Google Drive.
        Used by the Compliance system to remove copyrighted content.
        """
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.warning(f"Successfully deleted file from Google Drive. ID: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Drive file {file_id}: {str(e)}")
            return False
