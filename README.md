# Wi-Fi & BLE Presence Detection System

A real-time desktop dashboard application utilizing ambient Wi-Fi and Bluetooth Low Energy (BLE) signal analytics for device tracking and occupant presence detection. 

Using sensor fusion techniques on signal variability (Wi-Fi signal standard deviation) and proximity metrics (BLE RSSI with Kalman filtering), this system estimates movement and presence in the local environment and visualizes them on a dynamic radar map.

---

## 🚀 Key Features

*   **Wi-Fi Motion Detection**: Monitors ambient Wi-Fi BSSID signal strengths (RSSI) over a rolling time window. High variability (standard deviation) in ambient signals indicates physical movement/disturbances in the environment (due to multipath propagation variance).
*   **BLE Proximity & Distance Tracking**: Continuously scans for BLE advertisements and tracks nearby devices. Smooths RSSI fluctuations with a **1D Kalman Filter** and an **Exponential Moving Average (EMA)**, translating signal levels into distance estimates using the Log-Distance Path Loss model.
*   **Intelligent Sensor Fusion**: Fuses Wi-Fi motion scores and BLE proximity probability inputs to calculate an overall occupant presence confidence percentage ($0\text{--}100\%$).
*   **Dynamic Radar Dashboard**: A modern, dark-themed GUI built using `customtkinter` and `matplotlib` that visualizes:
    *   An interactive circular **Radar Map** with a sweep-line animation plotting nearby BLE devices relative to the host machine.
    *   Real-time graphs showing historical Wi-Fi standard deviations, BLE RSSI signals, and sensor fusion confidence levels.

---

## 📂 File Architecture

*   [app.py](file:///c:/Users/Allen/Documents/WIFI%20Detection/app.py): The primary entry point. Orchestrates threads for background scanning and builds the CustomTkinter GUI/Matplotlib widgets.
*   [ble_scanner.py](file:///c:/Users/Allen/Documents/WIFI%20Detection/ble_scanner.py): Asynchronous BLE scanner leveraging `bleak` to track BLE device advertisements and run RSSI filters.
*   [wifi_monitor.py](file:///c:/Users/Allen/Documents/WIFI%20Detection/wifi_monitor.py): Queries Windows CLI network interface information using `netsh wlan show networks mode=bssid` and parses SSID, BSSID, and RSSI statistics.
*   [detector.py](file:///c:/Users/Allen/Documents/WIFI%20Detection/detector.py): The core presence engine. Evaluates individual Wi-Fi and BLE occupancy scores and outputs the combined fusion confidence.
*   [distance_estimator.py](file:///c:/Users/Allen/Documents/WIFI%20Detection/distance_estimator.py): Implements the Log-Distance Path Loss Model for distance calculations and holds the mathematical implementation of the `KalmanFilter1D` state-estimator.
*   [setup_env.ps1](file:///c:/Users/Allen/Documents/WIFI%20Detection/setup_env.ps1): PowerShell script to initialize the virtual environment and install dependency libraries.
*   [run.ps1](file:///c:/Users/Allen/Documents/WIFI%20Detection/run.ps1): PowerShell wrapper script to run the application in the correct environment.
*   [requirements.txt](file:///c:/Users/Allen/Documents/WIFI%20Detection/requirements.txt): List of dependencies (`bleak`, `customtkinter`, `matplotlib`, `numpy`).

---

## 🛠️ Installation & Setup

> [!NOTE]
> This application scans Wi-Fi via Windows `netsh` utility, and utilizes Windows Bluetooth APIs via `bleak`. It is configured to run on Windows environments.

1. **Clone/Open the Workspace**: Open the project folder in your terminal or IDE.
2. **Setup the Virtual Environment**: Run the setup script in PowerShell to automatically create `.venv` and install the package dependencies:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
   .\setup_env.ps1
   ```
   *(Alternatively, you can manually create a venv and run `pip install -r requirements.txt`)*

---

## 🏃 Running the Application

Execute the application using the runner script:
```powershell
.\run.ps1
```
Or run the Python entrypoint directly from the virtual environment:
```powershell
.venv\Scripts\python.exe app.py
```

### Dashboard Guide
1. **Radar Display**: The center represents the host device. Concentric rings mark distances ($1\text{m}$, $3\text{m}$, $5\text{m}$, $10\text{m}$, $15\text{m}$). BLE devices detected will pop up on the radar sweep.
2. **Wi-Fi Motion Graph**: Plots standard deviations of ambient Wi-Fi APs to track signal fluctuations.
3. **Presence Fusion Confidence**: Displays the aggregated likelihood of occupancy/motion in your space.
