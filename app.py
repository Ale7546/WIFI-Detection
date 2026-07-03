import sys
import os
import time
import threading
import asyncio
import logging
from collections import deque
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# Matplotlib imports
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Local imports
from ble_scanner import BLEProximityScanner
from wifi_monitor import WiFiMonitor
from detector import DetectionEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set customtkinter appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DetectorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("WiFi & BLE Proximity and Motion Detector")
        self.geometry("1280x800")
        self.minsize(1024, 768)
        
        # Application flags and variables
        self.is_running = True
        self.wifi_enabled = True
        self.ble_enabled = True
        
        # Instances
        self.wifi_monitor = WiFiMonitor(scan_interval=1.5)
        self.ble_scanner = BLEProximityScanner(proximity_threshold=-75.0)
        self.detector = DetectionEngine(wifi_std_threshold=1.5, ble_rssi_threshold=-75.0)
        
        # Async Loop Thread
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.loop_thread.start()
        
        # Historical data for charts (last 30 samples)
        self.max_history_len = 30
        self.time_history = deque(maxlen=self.max_history_len)
        self.wifi_rssi_history = deque(maxlen=self.max_history_len)  # stores list of up to 3 RSSIs
        self.wifi_std_history = deque(maxlen=self.max_history_len)
        self.ble_rssi_history = deque(maxlen=self.max_history_len)
        
        # Start timestamp
        self.start_time = time.time()
        
        # Initialize UI Components
        self._build_ui()
        
        # Start background scan tasks on the async loop
        asyncio.run_coroutine_threadsafe(self._wifi_scan_loop(), self.loop)
        asyncio.run_coroutine_threadsafe(self._start_ble_scanner(), self.loop)
        
        # Start local UI update loop (100ms)
        self.update_ui()
        
        # Handle close window
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        
    def _build_ui(self):
        # Configure layout grid
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Main View
        self.grid_rowconfigure(0, weight=1)
        
        # ==========================================
        # SIDEBAR
        # ==========================================
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_rowconfigure(8, weight=1) # Spacer row
        
        # Logo / Title
        self.logo_label = ctk.CTkLabel(self.sidebar, text="SENSORS CONTROL", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 20))
        
        # Sensor toggles
        self.wifi_toggle = ctk.CTkSwitch(self.sidebar, text="Wi-Fi Monitoring", command=self.on_wifi_toggle, font=ctk.CTkFont(size=14))
        self.wifi_toggle.select()
        self.wifi_toggle.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        
        self.ble_toggle = ctk.CTkSwitch(self.sidebar, text="BLE Scanner", command=self.on_ble_toggle, font=ctk.CTkFont(size=14))
        self.ble_toggle.select()
        self.ble_toggle.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        
        # Thresholds headers
        self.threshold_label = ctk.CTkLabel(self.sidebar, text="CALIBRATION / SETTINGS", font=ctk.CTkFont(size=16, weight="bold"))
        self.threshold_label.grid(row=3, column=0, padx=20, pady=(25, 10), sticky="w")
        
        # Wi-Fi Std Dev Threshold Slider
        self.wifi_thresh_label = ctk.CTkLabel(self.sidebar, text="Wi-Fi Sensitivity Threshold: 1.50 dB", font=ctk.CTkFont(size=12))
        self.wifi_thresh_label.grid(row=4, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.wifi_thresh_slider = ctk.CTkSlider(self.sidebar, from_=0.1, to=5.0, number_of_steps=49, command=self.on_wifi_thresh_change)
        self.wifi_thresh_slider.set(1.5)
        self.wifi_thresh_slider.grid(row=5, column=0, padx=20, pady=(0, 15), sticky="ew")
        
        # BLE Proximity Threshold Slider
        self.ble_thresh_label = ctk.CTkLabel(self.sidebar, text="BLE Proximity Threshold: -75 dBm", font=ctk.CTkFont(size=12))
        self.ble_thresh_label.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.ble_thresh_slider = ctk.CTkSlider(self.sidebar, from_=-100, to=-40, number_of_steps=60, command=self.on_ble_thresh_change)
        self.ble_thresh_slider.set(-75)
        self.ble_thresh_slider.grid(row=7, column=0, padx=20, pady=(0, 15), sticky="ew")
        
        # BLE Device List Section
        self.devices_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.devices_frame.grid(row=9, column=0, padx=10, pady=10, sticky="nsew")
        self.devices_frame.grid_columnconfigure(0, weight=1)
        self.devices_frame.grid_rowconfigure(1, weight=1)
        
        self.dev_list_title = ctk.CTkLabel(self.devices_frame, text="Active BLE Devices", font=ctk.CTkFont(size=14, weight="bold"))
        self.dev_list_title.grid(row=0, column=0, padx=10, pady=(0, 5), sticky="w")
        
        self.dev_list = ctk.CTkTextbox(self.devices_frame, font=ctk.CTkFont(family="Consolas", size=11), width=280, height=250)
        self.dev_list.grid(row=1, column=0, padx=10, pady=0, sticky="nsew")
        self.dev_list.configure(state="disabled")
        
        # ==========================================
        # MAIN CONTENT VIEW
        # ==========================================
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(0, weight=0) # Status Indicator Card
        self.main_content.grid_rowconfigure(1, weight=1) # Plots
        
        # Header / Status Card
        self.status_card = ctk.CTkFrame(self.main_content, height=120)
        self.status_card.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.status_card.grid_columnconfigure(0, weight=1)
        
        # Big Glow / Status Label
        self.status_indicator = ctk.CTkLabel(
            self.status_card, 
            text="INITIALIZING SYSTEM...", 
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        self.status_indicator.grid(row=0, column=0, padx=20, pady=(15, 5))
        
        # Sub-status (Confidence and details)
        self.sub_status = ctk.CTkLabel(
            self.status_card, 
            text="Waiting for sensors to collect baseline data...", 
            font=ctk.CTkFont(size=14)
        )
        self.sub_status.grid(row=1, column=0, padx=20, pady=(0, 15))
        
        # Map/Plot canvas frame
        self.plot_frame = ctk.CTkFrame(self.main_content)
        self.plot_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Initialize Matplotlib Figure
        self._init_matplotlib()
        
    def _init_matplotlib(self):
        # Match Dark Mode colors
        plt.style.use('dark_background')
        
        self.fig = plt.Figure(figsize=(8, 5), dpi=100, facecolor='#1e1e1e')
        gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1], figure=self.fig)
        
        # Subplot 1: Wi-Fi RSSI and Std Dev
        self.ax_wifi = self.fig.add_subplot(gs[0])
        self.ax_wifi.set_title("Ambient Wi-Fi Monitoring (Top 3 APs)", color='#e0e0e0', fontsize=11, fontweight="bold", pad=8)
        self.ax_wifi.set_ylabel("Signal Strength (dBm)", color='#e0e0e0', fontsize=9)
        self.ax_wifi.set_facecolor('#1e1e1e')
        self.ax_wifi.grid(True, color='#333333', linestyle='--', linewidth=0.5)
        self.ax_wifi.tick_params(colors='#888888', labelsize=8)
        
        # Create a twinx axis for Wi-Fi rolling standard deviation
        self.ax_wifi_std = self.ax_wifi.twinx()
        self.ax_wifi_std.set_ylabel("Max Std Dev (dB)", color='#ff9800', fontsize=9)
        self.ax_wifi_std.tick_params(colors='#ff9800', labelsize=8)
        
        # Subplot 2: BLE RSSI
        self.ax_ble = self.fig.add_subplot(gs[1])
        self.ax_ble.set_title("BLE Bluetooth Proximity Tracker", color='#e0e0e0', fontsize=11, fontweight="bold", pad=8)
        self.ax_ble.set_xlabel("Time (s)", color='#e0e0e0', fontsize=9)
        self.ax_ble.set_ylabel("Max BLE RSSI (dBm)", color='#e0e0e0', fontsize=9)
        self.ax_ble.set_facecolor('#1e1e1e')
        self.ax_ble.grid(True, color='#333333', linestyle='--', linewidth=0.5)
        self.ax_ble.tick_params(colors='#888888', labelsize=8)
        
        self.fig.tight_layout()
        
        # Embed canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    # ==========================================
    # BACKGROUND LOOPS
    # ==========================================
    async def _wifi_scan_loop(self):
        while self.is_running:
            if self.wifi_enabled:
                # Execute in executor to avoid blocking the async event loop
                results = await self.loop.run_in_executor(None, self.wifi_monitor.scan_once)
                self.detector.add_wifi_data(results)
                
                # Fetch Top 3 RSSIs to store in history
                top_aps = self.wifi_monitor.get_top_ambient_aps(limit=3)
                rssis = [ap['rssi'] for ap in top_aps]
                # Pad with -100 if we have less than 3 APs
                while len(rssis) < 3:
                    rssis.append(-100.0)
                
                _, max_std = self.detector.get_max_wifi_std()
                
                # Update history in a thread-safe way (via deques)
                now_rel = time.time() - self.start_time
                self.time_history.append(now_rel)
                self.wifi_rssi_history.append(rssis)
                self.wifi_std_history.append(max_std)
                
                # Pull BLE state to match timestamps (pad if empty)
                _, max_ble_rssi = self.ble_scanner.get_max_rssi()
                self.ble_rssi_history.append(max_ble_rssi)
                
                # Trigger chart redraw on main thread
                self.loop.call_soon_threadsafe(self.redraw_charts)
                
            await asyncio.sleep(self.wifi_monitor.scan_interval)
            
    async def _start_ble_scanner(self):
        try:
            await self.ble_scanner.start()
            self.ble_active_state = True
        except Exception as e:
            self.ble_active_state = False
            logging.error(f"Bluetooth interface error: {e}")
            self.loop.call_soon_threadsafe(
                lambda: messagebox.showwarning(
                    "Bluetooth Error", 
                    "Could not initialize BLE Scanner. Please ensure your Bluetooth adapter is enabled."
                )
            )

    # ==========================================
    # UI CONTROLS / CALLBACKS
    # ==========================================
    def on_wifi_toggle(self):
        self.wifi_enabled = self.wifi_toggle.get() == 1
        logging.info(f"Wi-Fi monitor enabled: {self.wifi_enabled}")
        
    def on_ble_toggle(self):
        self.ble_enabled = self.ble_toggle.get() == 1
        logging.info(f"BLE scanner enabled: {self.ble_enabled}")
        if self.ble_enabled:
            asyncio.run_coroutine_threadsafe(self.ble_scanner.start(), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self.ble_scanner.stop(), self.loop)
            
    def on_wifi_thresh_change(self, val):
        self.detector.wifi_std_threshold = float(val)
        self.wifi_thresh_label.configure(text=f"Wi-Fi Sensitivity Threshold: {float(val):.2f} dB")
        
    def on_ble_thresh_change(self, val):
        val_int = int(float(val))
        self.detector.ble_rssi_threshold = val_int
        self.ble_scanner.proximity_threshold = val_int
        self.ble_thresh_label.configure(text=f"BLE Proximity Threshold: {val_int} dBm")
        
    def redraw_charts(self):
        if not self.time_history:
            return
            
        times = list(self.time_history)
        
        # 1. Update WiFi Plot
        self.ax_wifi.clear()
        self.ax_wifi.set_title("Ambient Wi-Fi Monitoring (Top 3 APs)", color='#e0e0e0', fontsize=11, fontweight="bold", pad=8)
        self.ax_wifi.set_ylabel("Signal Strength (dBm)", color='#e0e0e0', fontsize=9)
        self.ax_wifi.set_facecolor('#1e1e1e')
        self.ax_wifi.grid(True, color='#333333', linestyle='--', linewidth=0.5)
        
        # WiFi RSSI signals (transposed for plotting)
        rssi_lists = list(self.wifi_rssi_history)
        ap1 = [r[0] for r in rssi_lists]
        ap2 = [r[1] for r in rssi_lists]
        ap3 = [r[2] for r in rssi_lists]
        
        self.ax_wifi.plot(times, ap1, color='#00f0ff', linewidth=1.8, label="AP 1 (Strongest)")
        self.ax_wifi.plot(times, ap2, color='#00a0ff', linewidth=1.2, label="AP 2", linestyle="--")
        self.ax_wifi.plot(times, ap3, color='#0060aa', linewidth=1.0, label="AP 3", linestyle=":")
        self.ax_wifi.set_ylim(-105, -30)
        self.ax_wifi.legend(loc="upper left", fontsize=7, facecolor='#1e1e1e', edgecolor='#333333')
        
        # Wi-Fi Std Dev (twinx)
        self.ax_wifi_std.clear()
        self.ax_wifi_std.set_ylabel("Max Std Dev (dB)", color='#ff9800', fontsize=9)
        self.ax_wifi_std.tick_params(colors='#ff9800', labelsize=8)
        stds = list(self.wifi_std_history)
        self.ax_wifi_std.plot(times, stds, color='#ff9800', linewidth=1.5, label="Rolling Std Dev")
        self.ax_wifi_std.axhline(self.detector.wifi_std_threshold, color='#ff5722', linestyle=':', linewidth=1.2, label="Threshold")
        self.ax_wifi_std.set_ylim(0, max(5.0, max(stds) if stds else 5.0))
        
        # 2. Update BLE Plot
        self.ax_ble.clear()
        self.ax_ble.set_title("BLE Bluetooth Proximity Tracker", color='#e0e0e0', fontsize=11, fontweight="bold", pad=8)
        self.ax_ble.set_xlabel("Time (s)", color='#e0e0e0', fontsize=9)
        self.ax_ble.set_ylabel("Max BLE RSSI (dBm)", color='#e0e0e0', fontsize=9)
        self.ax_ble.set_facecolor('#1e1e1e')
        self.ax_ble.grid(True, color='#333333', linestyle='--', linewidth=0.5)
        
        ble_rssis = list(self.ble_rssi_history)
        self.ax_ble.plot(times, ble_rssis, color='#ff00ff', linewidth=2.0, label="Max BLE RSSI")
        self.ax_ble.axhline(self.detector.ble_rssi_threshold, color='#ff5722', linestyle=':', linewidth=1.2, label="Threshold")
        self.ax_ble.set_ylim(-105, -30)
        self.ax_ble.legend(loc="upper left", fontsize=7, facecolor='#1e1e1e', edgecolor='#333333')
        
        # Render canvas
        self.canvas.draw()
        
    def update_ui(self):
        """Periodic UI updates every 100ms."""
        if not self.is_running:
            return
            
        try:
            # 1. Check BLE devices and list them in the textbox
            devices = self.ble_scanner.get_devices()
            dev_text = ""
            
            # Sort devices by highest RSSI
            sorted_devs = sorted(devices.items(), key=lambda x: x[1]['ema_rssi'], reverse=True)
            for mac, dev in sorted_devs:
                dev_text += f"{dev['name'][:18]:<18} | {int(dev['ema_rssi']):>3} dBm\n"
                
            self.dev_list.configure(state="normal")
            self.dev_list.delete("1.0", tk.END)
            if sorted_devs:
                self.dev_list.insert("1.0", f"{'Device Name':<18} | {'RSSI':>7}\n" + "-"*30 + "\n" + dev_text)
            else:
                self.dev_list.insert("1.0", "Scanning for nearby BLE devices...\n(Ensure Bluetooth is ON)")
            self.dev_list.configure(state="disabled")
            
            # 2. Get Max BLE RSSI
            _, max_ble_rssi = self.ble_scanner.get_max_rssi()
            
            # 3. Perform Sensor Fusion and Status Calculation
            confidence, motion_detected, person_present_ble = self.detector.compute_fusion_confidence(
                wifi_active=self.wifi_enabled,
                ble_active=self.ble_enabled and getattr(self, 'ble_active_state', False),
                max_ble_rssi=max_ble_rssi
            )
            
            # 4. Display alerts & change status color
            is_active_alert = motion_detected or person_present_ble
            
            # Check sensor connectivity
            ble_status_msg = "ACTIVE" if getattr(self, 'ble_active_state', False) else "ERROR/DISABLED"
            wifi_status_msg = "ACTIVE" if self.wifi_enabled else "DISABLED"
            
            if not self.wifi_enabled and not self.ble_enabled:
                self.status_card.configure(fg_color="#333333")
                self.status_indicator.configure(text="ALL SENSORS DISABLED")
                self.sub_status.configure(text="Enable Wi-Fi or BLE to start scanning.")
            elif is_active_alert:
                self.status_card.configure(fg_color="#801a1a") # Premium Dark Red glow
                
                reasons = []
                if motion_detected:
                    reasons.append("Wi-Fi Motion Detected")
                if person_present_ble:
                    reasons.append("BLE Proximity Alert")
                    
                alert_text = " + ".join(reasons)
                self.status_indicator.configure(text=f"🚨 ALERT: HUMAN DETECTED (Confidence: {confidence:.0f}%)", text_color="#ffcccc")
                self.sub_status.configure(
                    text=f"Reason: {alert_text} | Wi-Fi: {wifi_status_msg} | BLE: {ble_status_msg}",
                    text_color="#ffcccc"
                )
            else:
                self.status_card.configure(fg_color="#1b3a24") # Premium Dark Green glow
                self.status_indicator.configure(text=f"SECURE: NO PRESENCE DETECTED (Confidence: {confidence:.0f}%)", text_color="#ccffcc")
                self.sub_status.configure(
                    text=f"Environment Stable | Wi-Fi: {wifi_status_msg} | BLE: {ble_status_msg}",
                    text_color="#ccffcc"
                )
                
        except Exception as e:
            logging.error(f"Error in UI update loop: {e}")
            
        # Reschedule UI update (100ms)
        self.after(100, self.update_ui)
        
    def on_closing(self):
        """Clean shutdown of background tasks and threads."""
        self.is_running = False
        
        # Stop BLE scanner on loop
        asyncio.run_coroutine_threadsafe(self.ble_scanner.stop(), self.loop)
        
        # Stop loop and wait for loop thread to join
        self.loop.call_soon_threadsafe(self.loop.stop)
        
        # Wait up to 1 second for background tasks
        logging.info("Shutting down...")
        self.destroy()

if __name__ == "__main__":
    app = DetectorApp()
    app.mainloop()
