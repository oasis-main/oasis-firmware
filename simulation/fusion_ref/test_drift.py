"""Synthetic check of the FW-012 drift table: 0.5*b*t^2, and that GPS fixes bound it."""
import math, random, unittest
from deadreckon import DeadReckon


def run(bias, gap, seed=1):
    rnd = random.Random(seed)
    d = DeadReckon(); dt = 0.01
    # truth: constant 10 m/s straight east
    tx, v = 0.0, 10.0
    d.v = v
    err_at_gap_end = None
    n = int((gap + 2.0) / dt)
    for i in range(n):
        t = i * dt
        tx += v * dt
        a = bias + rnd.gauss(0, 0.02)
        d.predict(dt, a, 0.0)
        if t < 1.0 and i % 10 == 0:
            d.fix(tx, 0.0, v)
        if abs(t - (1.0 + gap)) < dt / 2:
            err_at_gap_end = abs(d.x - tx)
    return err_at_gap_end


class T(unittest.TestCase):
    def test_drift_grows_with_gap(self):
        e1, e5 = run(0.2, 1.0), run(0.2, 5.0)
        self.assertLess(e1, e5)

    def test_matches_half_b_t2(self):
        # speed error also integrates: position err ~ 0.5*b*t^2 (+ small noise)
        e = run(0.2, 3.0)
        self.assertAlmostEqual(e, 0.5 * 0.2 * 9.0, delta=0.4)

    def test_zupt(self):
        d = DeadReckon(); d.v = 1.0
        for _ in range(100):
            d.predict(0.01, 0.0, 0.0, gyro_mag=0.0, acc_mag=0.0)
        self.assertEqual(d.v, 0.0)


if __name__ == "__main__":
    unittest.main()
