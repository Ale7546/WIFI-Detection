import math

class KalmanFilter1D:
    def __init__(self, process_variance: float = 0.05, measurement_variance: float = 4.0):
        self.q = process_variance
        self.r = measurement_variance
        self.x = None  # Estimated value (state)
        self.p = 1.0   # Estimate error covariance
        
    def update(self, measurement: float) -> float:
        if self.x is None:
            self.x = measurement
            return self.x
            
        # Prediction update
        self.p = self.p + self.q
        
        # Measurement update
        k = self.p / (self.p + self.r)
        self.x = self.x + k * (measurement - self.x)
        self.p = (1.0 - k) * self.p
        
        return self.x

def calculate_distance(rssi: float, a: float = -59.0, n: float = 2.5) -> float:
    """
    Calculates distance in meters using Log-Distance Path Loss model.
    d = 10^((a - rssi) / (10 * n))
    """
    if rssi >= 0:
        return 0.0
    try:
        dist = 10.0 ** ((a - rssi) / (10.0 * n))
        return min(max(dist, 0.0), 15.0) # Clamp distance to [0, 15] meters
    except Exception:
        return 15.0
