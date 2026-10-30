# FW-012: Sensor fusion and dead-reckoning design (kart consumer of BNO055)

Status: DESIGN NOTE, not implemented. Stacked on FW-014 (PR #43, BNO055 driver, "implemented, unvalidated").
Author: ButterBolt (DIR-0019). Numbers marked [verify] come from memory and need a datasheet check.

## 1. Goal and honest limits

Give a kart logger a usable orientation and short-horizon motion estimate from one BNO055,
so lap analysis (Nimbus lane) can use IMU data when GPS is poor or sampled slowly.

Dead-reckoning from a MEMS accelerometer alone drifts quadratically. Position error from a
constant accel bias b after t seconds is 0.5*b*t^2:

| bias (m/s^2) | 1 s | 5 s | 10 s | 30 s | 60 s |
|---|---|---|---|---|---|
| 0.01 | 0.0 m | 0.1 | 0.5 | 4.5 | 18 |
| 0.05 | 0.0 | 0.6 | 2.5 | 22.5 | 90 |
| 0.2  | 0.1 | 2.5 | 10 | 90 | 360 |
| 0.8  | 0.4 | 10 | 40 | 360 | 1440 |

The BNO055 zero-g offset is on the order of tens of mg (0.8 m/s^2 is ~80 mg) [verify]. So:
IMU-only position is good for about 1-3 s (a corner exit, a GPS dropout) and useless for a lap.
Design therefore treats the IMU as an interpolator between absolute fixes (GPS or lap markers),
never as a standalone position source.

## 2. What the chip already does

In IMUPLUS / NDOF mode the BNO055 fuses accel + gyro (+ mag) on-chip at 100 Hz and reports
quaternion, linear acceleration (gravity removed) and gravity vector (see `Bno055Reading`).
We do NOT re-implement orientation fusion on the host. FW-012 adds only:

1. Frame alignment: sensor frame to kart frame (x forward, y left, z up) via the driver axis
   remap plus a one-time static + straight-line calibration (section 4).
2. Longitudinal/lateral accel and yaw rate in the kart frame (what lap analysis needs).
3. A short-horizon dead-reckoning filter that is reset by absolute fixes (section 3).
4. Stationary detection (ZUPT) to kill velocity drift at stops.

Use IMUPLUS (no magnetometer) for karts: motors and steel frames corrupt the magnet field;
heading is then relative (yaw drifts slowly) and is anchored by GPS course when moving.

## 3. Estimator

State (2D, ground vehicle): position p (east, north), speed v, heading psi, accel bias b_a (long.), gyro-z bias b_g.
Prediction at 100 Hz from BNO055 linear accel (kart frame, long.) and gyro z.
Update when available:

- GPS fix (typ. 10 Hz GoPro/GNSS): position, speed, course (course only above ~2 m/s).
- ZUPT: when |gyro| < threshold and |lin. accel| < threshold for >= 0.3 s: v = 0, estimate b_a, b_g.
- Optional: lap-line crossing (known track point) as a position fix.

Filter: a plain error-state EKF in f32, ~6 states. No heap. Fits Cortex-M4F / ESP32. A host
reference in Python (replay of logged CSV) comes first; port to `no_std` Rust after it matches.
Complementary filter (speed = GPS speed blended with integrated accel) is the fallback if the
EKF proves too heavy; it already gives most of the value for lap analysis.

## 4. Calibration procedure (operator steps)

1. Power on, wait for BNO055 calibration status sys/gyro/accel = 3 (mag ignored in IMUPLUS).
   `Bno055Calibration::is_fully_calibrated` currently requires mag = 3 too: add an
   `is_ready_imuplus()` that ignores mag (small FW-014 follow-up).
2. Static 10 s on level ground: gyro bias, accel bias.
3. Drive a straight 20-50 m: fixes the forward axis from GPS course vs. accel direction.
4. Save the BNO055 calibration profile (driver already supports save/restore) to flash.

## 5. Interfaces

- Input: `Bno055Reading` at 100 Hz; optional `GpsFix { t, lat, lon, speed, course, hdop }`.
- Output: `KartState { t, p_en, v, psi, a_long, a_lat, yaw_rate, quality }`, with
  `quality` = {Fixed, Interpolated(age_s), Degraded}. Interpolated beyond 3 s becomes Degraded.
- Log: raw `Bno055Reading` plus fixes, so any estimate can be recomputed offline.

## 6. Validation plan (no hardware needed first)

1. Replay: GoPro GPMF IMU/GPS from the planned HERO clip (PR #7 `gpmf_extract`) through the
   Python reference filter; compare interpolated position against held-out GPS fixes
   (drop 2 s windows and measure error). Success metric to be set with Nimbus.
2. Synthetic: simulated kart paths with injected bias/noise to confirm the drift table above.
3. Hardware-in-loop only after FW-015 (needs Mike's bench board); status tag stays
   "implemented, unvalidated" until then.

## 7. Dependencies and open questions

- Real data: no GPMF source file yet (waiting on the 60 s original MP4 with 3 taps).
- Rust toolchain: none in this container, so Rust code cannot be compiled; the Python reference is the first deliverable.
- BNO055 scale factors and zero-g offset need a datasheet check (see PR #43 review note).
- Ask Nimbus: required output rate and accuracy for lap comparison; GPS rate of the real logger.

## 8. Next steps

1. (done) Python reference estimator + synthetic drift test: `simulation/fusion_ref/` (`python3 test_drift.py`, stdlib only; synthetic-validated only).
2. Replay on real clip when it arrives.
3. `no_std` port, host tests, once cargo exists.
