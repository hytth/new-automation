"""
NordVPN Connection Manager.
Handles connecting to USA (New York), verifying public IP, and retry logic.
Works on both Linux (GitHub Actions) and Windows (Local).
"""

import subprocess
import time
import logging
import os
import requests
from typing import Optional
from config import get_config
from utils import get_public_ip

logger = logging.getLogger(__name__)

class VpnManager:
    def __init__(self):
        self.config = get_config().vpn
        # Read credentials safely from environment variables
        self.username = os.getenv("NORDVPN_USERNAME", "")
        self.password = os.getenv("NORDVPN_PASSWORD", "")
        
        if not self.username or not self.password:
            logger.warning("NordVPN credentials not found in environment variables. VPN connection may fail.")

    def _get_nordvpn_cmd(self) -> str:
        """Returns the correct command based on the operating system."""
        if os.name == 'nt':  # Windows
            cmd_path = self.config.nordvpn_cmd_path
            if not os.path.exists(cmd_path):
                logger.error(f"NordVPN executable not found at {cmd_path}")
                return None
            return cmd_path
        else:  # Linux (GitHub Actions / Ubuntu)
            return "nordvpn"

    def _is_ip_usa(self, ip_address: str) -> bool:
        """
        Verifies if the given IP address belongs to the United States.
        Uses a free IP lookup API.
        """
        if not ip_address:
            return False
            
        try:
            # Using ip-api.com for reliable country lookup
            response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'success' and data.get('countryCode') == 'US':
                logger.info(f"IP Verification Success: {ip_address} is located in {data.get('city', 'Unknown')}, {data.get('countryCode')}")
                return True
            else:
                logger.warning(f"IP Verification Failed: {ip_address} is in {data.get('countryCode', 'Unknown')}, not US.")
                return False
        except Exception as e:
            logger.error(f"Failed to verify IP location: {str(e)}")
            return False

    def connect(self) -> bool:
        """
        Attempts to connect to NordVPN (USA - New York) with retry logic.
        Returns True if connected and US IP is verified, False otherwise.
        """
        logger.info(f"Attempting to connect to NordVPN: {self.config.nordvpn_server} - {self.config.nordvpn_city}")
        
        nordvpn_cmd = self._get_nordvpn_cmd()
        if not nordvpn_cmd:
            return False

        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.info(f"VPN Connection Attempt {attempt}/{self.config.max_retries}...")
                
                # Step 1: Disconnect if already connected to clear state
                subprocess.run([nordvpn_cmd, "-d"], capture_output=True, timeout=30)
                time.sleep(3)
                
                # Step 2: Login (Crucial for Linux/GitHub Actions to pass credentials)
                if self.username and self.password:
                    login_cmd = [nordvpn_cmd, "login", "-u", self.username, "-p", self.password]
                    subprocess.run(login_cmd, capture_output=True, timeout=30)
                    time.sleep(2)

                # Step 3: Connect to specific city (New York)
                connect_cmd = [nordvpn_cmd, "-c", "-g", self.config.nordvpn_server, "-n", self.config.nordvpn_city]
                result = subprocess.run(connect_cmd, capture_output=True, text=True, timeout=60)
                
                # Check for success keywords in output (Works for both Win/Mac/Linux CLI)
                if "You are connected" in result.stdout or result.returncode == 0:
                    logger.info("NordVPN command executed successfully. Verifying IP address...")
                    time.sleep(5) # Wait for network adapter to fully apply the new IP
                    
                    current_ip = get_public_ip()
                    if current_ip:
                        if self._is_ip_usa(current_ip):
                            return True
                        else:
                            logger.warning(f"Connected to VPN, but IP ({current_ip}) is not in the USA.")
                    else:
                        logger.warning("Connected to VPN, but failed to fetch public IP.")
                else:
                    logger.warning(f"VPN Connection command failed. Output: {result.stdout} - Error: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"VPN Command timed out on attempt {attempt}.")
            except FileNotFoundError:
                logger.error("NordVPN CLI not installed on this system.")
                break # No point retrying if the command doesn't exist
            except Exception as e:
                logger.error(f"Unexpected error during VPN connection: {str(e)}")

            if attempt < self.config.max_retries:
                wait_time = self.config.retry_delay_seconds
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

        return False