import time
import numpy as np
from collections import deque
from typing import Dict, List, Tuple, Optional

class DetectionEngine:
    def __init__(self, 
                 wifi_std_threshold: float = 1.5, 
                 ble_rssi_threshold: float = -75.0, 
                 window_size: float = 5.0):
        self.wifi_std_threshold = wifi_std_threshold
        self.ble_rssi_threshold = ble_rssi_threshold
        self.window_size = window_size
        
        # Structure: bssid -> deque of (timestamp, rssi)
        self.wifi_history: Dict[str, deque] = {}
        # Keep track of standard deviations for each BSSID
        self.wifi_stds: Dict[str, float] = {}
        
    def add_wifi_data(self, scan_results: List[dict]):
        """Adds a new Wi-Fi scan result and cleans up old data outside the window."""
        now = time.time()
        
        # Add new scans
        for net in scan_results:
            bssid = net['bssid']
            rssi = net['rssi']
            if bssid not in self.wifi_history:
                self.wifi_history[bssid] = deque(maxlen=20)
            self.wifi_history[bssid].append((now, rssi))
            
        # Clean up old samples and calculate standard deviations
        self.wifi_stds.clear()
        inactive_bssids = []
        
        for bssid, q in self.wifi_history.items():
            # Remove samples older than window_size
            while q and now - q[0][0] > self.window_size:
                q.popleft()
                
            if not q:
                inactive_bssids.append(bssid)
                continue
                
            # If we have at least 3 samples, we can compute standard deviation
            if len(q) >= 3:
                rssis = [val for _, val in q]
                std = float(np.std(rssis))
                self.wifi_stds[bssid] = std
            else:
                self.wifi_stds[bssid] = 0.0
                
        # Clean up entirely dead BSSIDs to prevent memory leaks
        for bssid in inactive_bssids:
            if bssid in self.wifi_history and not self.wifi_history[bssid]:
                del self.wifi_history[bssid]

    def get_max_wifi_std(self) -> Tuple[Optional[str], float]:
        """Returns the BSSID and max standard deviation value."""
        if not self.wifi_stds:
            return None, 0.0
        
        max_bssid = max(self.wifi_stds, key=self.wifi_stds.get)
        return max_bssid, self.wifi_stds[max_bssid]

    def get_wifi_score(self) -> float:
        """Returns a 0-100 Wi-Fi motion score based on standard deviation."""
        _, max_std = self.get_max_wifi_std()
        
        if self.wifi_std_threshold <= 0:
            return 0.0
            
        if max_std >= self.wifi_std_threshold:
            # Scale from 80% to 100% (maxes out at 2x threshold)
            extra = (max_std - self.wifi_std_threshold) / self.wifi_std_threshold
            score = 80.0 + 20.0 * min(1.0, extra)
        else:
            # Scale from 0% to 80%
            score = 80.0 * (max_std / self.wifi_std_threshold)
            
        return max(0.0, min(100.0, score))

    def get_ble_score(self, max_ble_rssi: float) -> float:
        """Returns a 0-100 BLE proximity score based on maximum RSSI."""
        if max_ble_rssi <= -100.0:
            return 0.0
            
        if max_ble_rssi >= self.ble_rssi_threshold:
            # Scale from 80% to 100% (maxes out at -50 dBm)
            range_upper = max(-50.0, self.ble_rssi_threshold + 15.0)
            interval = range_upper - self.ble_rssi_threshold
            if interval <= 0:
                score = 100.0
            else:
                extra = (max_ble_rssi - self.ble_rssi_threshold) / interval
                score = 80.0 + 20.0 * min(1.0, extra)
        else:
            # Scale from 0% to 80% (zero out at threshold - 15 dBm)
            range_lower = self.ble_rssi_threshold - 15.0
            interval = self.ble_rssi_threshold - range_lower
            if max_ble_rssi <= range_lower:
                score = 0.0
            else:
                score = 80.0 * ((max_ble_rssi - range_lower) / interval)
                
        return max(0.0, min(100.0, score))

    def compute_fusion_confidence(self, 
                                  wifi_active: bool, 
                                  ble_active: bool, 
                                  max_ble_rssi: float) -> Tuple[float, bool, bool]:
        """
        Computes fused presence confidence (0-100%) and individual alarm flags.
        Returns: (confidence_pct, motion_detected, person_present_ble)
        """
        motion_detected = False
        person_present_ble = False
        
        # Calculate individual scores
        wifi_score = 0.0
        if wifi_active:
            _, max_std = self.get_max_wifi_std()
            motion_detected = max_std >= self.wifi_std_threshold
            wifi_score = self.get_wifi_score()
            
        ble_score = 0.0
        if ble_active:
            person_present_ble = max_ble_rssi >= self.ble_rssi_threshold
            ble_score = self.get_ble_score(max_ble_rssi)
            
        if not wifi_active and not ble_active:
            return 0.0, False, False
            
        p_w = wifi_score / 100.0
        p_b = ble_score / 100.0
        
        if wifi_active and ble_active:
            p_f = 1.0 - (1.0 - p_w) * (1.0 - p_b)
        elif wifi_active:
            p_f = p_w
        else:
            p_f = p_b
            
        confidence = float(p_f * 100.0)
        return confidence, motion_detected, person_present_ble
