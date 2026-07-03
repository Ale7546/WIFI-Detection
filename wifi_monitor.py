import subprocess
import re
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WiFiMonitor:
    def __init__(self, scan_interval: float = 1.5):
        self.scan_interval = scan_interval
        # Store latest scan: list of dicts with {ssid, bssid, rssi, signal_pct}
        self.latest_scan: List[dict] = []
        # Store connected hotspot details to exclude
        self.hotspot_ssid: Optional[str] = None
        self.hotspot_bssid: Optional[str] = None
        
    def update_hotspot_info(self):
        """Query netsh to find current connected SSID and BSSID."""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'], 
                capture_output=True, text=True, check=True, 
                startupinfo=startupinfo
            )
            output = result.stdout
            
            ssid = None
            bssid = None
            state = None
            
            for line in output.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if line.startswith('State'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        state = parts[1].strip()
                elif line.startswith('SSID'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        ssid = parts[1].strip()
                elif line.startswith('AP BSSID') or line.startswith('BSSID'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        bssid = parts[1].strip().lower()
                        
            if state == 'connected':
                self.hotspot_ssid = ssid
                self.hotspot_bssid = bssid
            else:
                self.hotspot_ssid = None
                self.hotspot_bssid = None
        except Exception as e:
            logging.error(f"Error checking connected WiFi interface: {e}")
            self.hotspot_ssid = None
            self.hotspot_bssid = None

    def scan_once(self) -> List[dict]:
        """Perform a single Wi-Fi scan and parse results."""
        self.update_hotspot_info()
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], 
                capture_output=True, text=True, check=True, 
                startupinfo=startupinfo
            )
            output = result.stdout
            
            networks = []
            current_ssid = None
            current_bssid = None
            
            for line in output.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # SSID matching
                ssid_match = re.match(r'^SSID\s+\d+\s*:\s*(.*)', line)
                if ssid_match:
                    current_ssid = ssid_match.group(1).strip()
                    if not current_ssid:
                        current_ssid = "<Hidden SSID>"
                    continue
                    
                # BSSID matching
                bssid_match = re.match(r'^BSSID\s+\d+\s*:\s*(.*)', line)
                if bssid_match:
                    current_bssid = bssid_match.group(1).strip().lower()
                    continue
                    
                # Signal matching
                signal_match = re.search(r'Signal\s*:\s*(\d+)%', line)
                if signal_match and current_bssid:
                    signal_pct = int(signal_match.group(1))
                    rssi = (signal_pct / 2.0) - 100.0
                    
                    # Exclude the hotspot BSSID
                    if self.hotspot_bssid and current_bssid == self.hotspot_bssid:
                        continue
                    
                    networks.append({
                        'ssid': current_ssid,
                        'bssid': current_bssid,
                        'rssi': rssi,
                        'signal_pct': signal_pct
                    })
            
            # Sort by signal strength (strongest first)
            networks.sort(key=lambda x: x['rssi'], reverse=True)
            self.latest_scan = networks
            return networks
        except Exception as e:
            logging.error(f"Error during WiFi scan: {e}")
            return []

    def get_top_ambient_aps(self, limit: int = 3) -> List[dict]:
        """Returns the top limit ambient APs (excluding the hotspot)."""
        return self.latest_scan[:limit]
