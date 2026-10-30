"""FW-012 reference estimator (stdlib only). STATUS: design reference, synthetic-validated only.

1D-along-path speed + 2D position/heading complementary filter:
 - predict from longitudinal accel and yaw rate at the IMU rate
 - correct with GPS fixes (position, speed, course) when available
 - ZUPT when stationary
"""
import math


class DeadReckon:
    def __init__(self, k_pos=0.5, k_spd=0.5, k_hdg=0.2):
        self.x = self.y = 0.0   # east, north (m)
        self.v = 0.0            # m/s
        self.psi = 0.0          # rad, 0 = east, CCW positive
        self.last_fix_t = None
        self.t = 0.0
        self.k_pos, self.k_spd, self.k_hdg = k_pos, k_spd, k_hdg
        self._still = 0.0

    def predict(self, dt, a_long, yaw_rate, gyro_mag=None, acc_mag=None):
        self.t += dt
        self.psi += yaw_rate * dt
        self.v += a_long * dt
        if gyro_mag is not None and acc_mag is not None and gyro_mag < 0.02 and acc_mag < 0.1:
            self._still += dt
            if self._still >= 0.3:
                self.v = 0.0   # ZUPT
        else:
            self._still = 0.0
        self.x += self.v * math.cos(self.psi) * dt
        self.y += self.v * math.sin(self.psi) * dt

    def fix(self, x, y, speed, course=None):
        self.x += self.k_pos * (x - self.x)
        self.y += self.k_pos * (y - self.y)
        self.v += self.k_spd * (speed - self.v)
        if course is not None and speed > 2.0:
            d = (course - self.psi + math.pi) % (2 * math.pi) - math.pi
            self.psi += self.k_hdg * d
        self.last_fix_t = self.t

    def quality(self):
        if self.last_fix_t is None:
            return "Degraded"
        age = self.t - self.last_fix_t
        return "Fixed" if age < 0.15 else ("Interpolated" if age <= 3.0 else "Degraded")
