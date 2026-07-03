import asyncio
import logging
import time
import random
import math
from typing import Dict, Tuple, Optional
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from distance_estimator import KalmanFilter1D

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BLEProximityScanner:
    def __init__(self, proximity_threshold: float = -75.0, ema_alpha: float = 0.3):
        self.proximity_threshold = proximity_threshold
        self.ema_alpha = ema_alpha  # Exponential Moving Average smoothing factor
        
        # Structure: mac_address -> { 'name': str, 'rssi_history': list, 'ema_rssi': float, 'last_seen': float }
        self.devices: Dict[str, dict] = {}
        self.is_scanning = False
        self._scanner: Optional[BleakScanner] = None
        self._scan_task: Optional[asyncio.Task] = None
        
    def _detection_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        mac = device.address
        name = device.name or "Unknown Device"
        rssi = advertisement_data.rssi
        now = time.time()
        
        if mac not in self.devices:
            kf = KalmanFilter1D(process_variance=0.05, measurement_variance=4.0)
            kf.update(rssi)
            self.devices[mac] = {
                'name': name,
                'rssi_history': [rssi],
                'ema_rssi': float(rssi),
                'kalman_rssi': float(rssi),
                'kalman': kf,
                'last_seen': now,
                'angle': random.uniform(0, 2 * math.pi)
            }
        else:
            dev = self.devices[mac]
            dev['name'] = name or dev['name']  # Keep existing name if new is None
            dev['rssi_history'].append(rssi)
            # Limit history to last 20 samples to avoid memory growth
            if len(dev['rssi_history']) > 20:
                dev['rssi_history'].pop(0)
            
            # Update EMA: EMA_new = alpha * RSSI_new + (1 - alpha) * EMA_old
            dev['ema_rssi'] = self.ema_alpha * rssi + (1 - self.ema_alpha) * dev['ema_rssi']
            if 'kalman' not in dev:
                dev['kalman'] = KalmanFilter1D(process_variance=0.05, measurement_variance=4.0)
            dev['kalman_rssi'] = dev['kalman'].update(rssi)
            if 'angle' not in dev:
                dev['angle'] = random.uniform(0, 2 * math.pi)
            dev['last_seen'] = now

    async def start(self):
        if self.is_scanning:
            return
        
        logging.info("Starting BLE Scanner...")
        self.is_scanning = True
        try:
            self._scanner = BleakScanner(detection_callback=self._detection_callback)
            await self._scanner.start()
            # Start background task to clean up old devices (older than 10 seconds)
            self._scan_task = asyncio.create_task(self._cleanup_loop())
        except Exception as e:
            self.is_scanning = False
            logging.error(f"Failed to start BLE Scanner: {e}")
            raise e

    async def stop(self):
        if not self.is_scanning:
            return
        
        logging.info("Stopping BLE Scanner...")
        self.is_scanning = False
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        
        if self._scanner:
            try:
                await self._scanner.stop()
            except Exception as e:
                logging.error(f"Error stopping BLE scanner: {e}")
            self._scanner = None

    async def _cleanup_loop(self):
        while self.is_scanning:
            await asyncio.sleep(2.0)
            now = time.time()
            # Remove devices not seen for more than 10 seconds
            dead_macs = [mac for mac, dev in self.devices.items() if now - dev['last_seen'] > 10.0]
            for mac in dead_macs:
                del self.devices[mac]

    def get_devices(self) -> Dict[str, dict]:
        """Returns a snapshot of currently tracked devices."""
        # Age out old devices on retrieval just in case cleanup loop didn't run yet
        now = time.time()
        return {
            mac: dev for mac, dev in self.devices.items()
            if now - dev['last_seen'] <= 10.0
        }

    def get_max_rssi(self) -> Tuple[Optional[str], float]:
        """Returns the MAC address and highest Kalman or EMA RSSI among all active devices."""
        active_devices = self.get_devices()
        if not active_devices:
            return None, -100.0
        
        best_mac = None
        best_rssi = -100.0
        for mac, dev in active_devices.items():
            val = dev.get('kalman_rssi', dev['ema_rssi'])
            if val > best_rssi:
                best_rssi = val
                best_mac = mac
        return best_mac, best_rssi

    def is_person_present(self) -> bool:
        """Returns True if any device's EMA RSSI is above the proximity threshold."""
        _, max_rssi = self.get_max_rssi()
        return max_rssi >= self.proximity_threshold
