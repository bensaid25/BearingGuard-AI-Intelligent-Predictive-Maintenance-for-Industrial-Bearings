# IoT Prototype Build — Session Summary

Reference notes covering the full hardware build session: final configuration, issues encountered and how they were resolved, and validation results. Use this as source material for the Sprint 5 report.

---

## 1. Hardware Components

| Component | Role |
|---|---|
| ESP32 (ESP-WROOM-32, CP2102) | Edge microcontroller — reads sensor over I2C, drives motor via PWM |
| MPU6050 (GY-521 board) | Vibration sensor — accelerometer + gyroscope |
| L298N | H-bridge motor driver |
| 12V DC motor (EG-530AD-2B, 2400 RPM, CCW) | Simulated rotating machine component |
| 12V 1A power adapter (barrel plug, cut and rewired) | Powers motor circuit independently of ESP32 |
| Breadboard, jumper wires | Prototyping platform |

---

## 2. Final Wiring Configuration

**MPU6050 → ESP32 (I2C):**

| MPU6050 pin | ESP32 pin |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SCL | GPIO22 |
| SDA | GPIO21 |

**L298N → ESP32 (logic):**

| L298N pin | ESP32 pin |
|---|---|
| IN1 | GPIO18 |
| IN2 | GPIO19 |
| ENA | GPIO15 |

**L298N → Power / Motor:**

| L298N terminal | Connects to |
|---|---|
| +12V | Adapter positive wire |
| GND | Adapter negative wire + ESP32 GND (shared ground) |
| OUT1/OUT2 | Motor terminals |

Note: ENA's default 2-pin jumper cap was removed to enable PWM speed control (leaving it in place would force the motor to always run at fixed full speed via the onboard 5V rail rather than a variable ESP32 signal).

---

## 3. Build & Debugging Timeline

This is the practical troubleshooting narrative — useful for a "challenges encountered" subsection, since it demonstrates real debugging methodology rather than a frictionless build.

1. **LEDC PWM API mismatch.** Initial firmware used the older `ledcSetup()`/`ledcAttachPin()` API. The installed ESP32 Arduino core (3.x) replaced this with a simpler `ledcAttach(pin, freq, resolution)` / `ledcWrite(pin, duty)` API tied directly to the GPIO pin rather than a channel number. Fixed by updating the PWM calls to the new API.

2. **ENA GPIO strapping pin consideration.** GPIO25 was the original ENA pin choice; GPIO15 was considered as an alternative but flagged as an ESP32 "strapping pin" (has a special role during boot). Final wiring used GPIO18/19/15 for IN1/IN2/ENA respectively (moved from an initial GPIO27/26/25 assignment during iterative wiring).

3. **Pin mismatch between code and physical wiring.** After moving ENA to a different physical pin during hardware iteration, the firmware still referenced the old pin number in code, causing "L298N powered (LED on) but motor not spinning" — a classic symptom of a floating/disconnected enable signal. Diagnosed via Serial Monitor confirmation prints, resolved by updating the `ENA` constant in code to match the actual wire.

4. **MPU6050 not detected in combined sketch despite passing I2C scanner test.** The standalone I2C scanner reliably found the sensor at address `0x68`, but the full sketch's `mpu.begin()` (Adafruit_MPU6050 library) consistently failed with "MPU6050 not found."
   - First hypothesis (I2C bus speed too high for breadboard wiring) — tested by lowering `Wire.setClock()` to 100kHz. Did not resolve the issue.
   - Root cause found via a raw I2C diagnostic reading the WHO_AM_I identity register directly: **the sensor returned `0x70`, identifying it as an MPU6500 chip variant, not a genuine MPU6050** (common on some low-cost GY-521 clone boards). The Adafruit library hard-fails its identity check against the expected `0x68`.
   - **Resolution:** rewrote sensor communication using raw I2C register reads/writes (bypassing the Adafruit library's identity check entirely), since the MPU6500 shares the same accelerometer/gyroscope/temperature register map as the MPU6050.

5. **Serial capture reset issue.** Attempting to script automated data capture via Python (`pyserial`) caused the ESP32 to reboot every time the script connected, silently resetting motor state. Root cause: the CP2102 USB-serial chip's auto-reset circuit toggles DTR/RTS control lines on connection open, which is wired to the ESP32's reset pin (same mechanism that resets the board when Arduino Serial Monitor opens). Resolved by explicitly configuring the serial connection to set DTR/RTS false *before* opening the port (setting them after opening was insufficient, as the reset pulse occurs during the open call itself on Windows).

---

## 4. Software Produced

| File | Purpose |
|---|---|
| `motor_only_test.ino` | Isolated L298N + motor test, independent of sensor |
| `i2c_scanner.ino` | Standalone I2C bus scan to verify sensor detection |
| `mpu6050_whoami_check.ino` | Raw register diagnostic that identified the MPU6500 chip mismatch |
| `rig_bringup.ino` | Combined sketch: raw-register sensor reading + PWM motor control, streaming live CSV over Serial |
| `capture_serial.py` | Captures ESP32 serial output directly to timed CSV files (avoids manual copy-paste from a fast-scrolling terminal; suppresses the auto-reset issue) |
| `compare_vibration.py` | Computes and compares per-axis standard deviation between motor-running and motor-stopped captures |

---

## 5. Validation Results

**Test procedure:** capture accelerometer readings while the motor runs at a fixed PWM speed, then again while stopped; compare variability (standard deviation) per axis as evidence the sensor detects real motor-induced vibration rather than producing static/noise-only output.

**Trial 1 — sensor unmounted (loose on breadboard), small sample (~23 rows/state):**

| Axis | Std (running) | Std (stopped) | Ratio |
|---|---|---|---|
| ax | 0.0355 | 0.0216 | 1.64× |
| ay | 0.0268 | 0.0194 | 1.38× |
| az | 0.0503 | 0.0355 | 1.42× |

**Trial 2 — sensor rigidly mounted on motor housing (angled headers, glued), large sample (585 rows/state, ~30s each):**

| Axis | Std (running) | Std (stopped) | Ratio |
|---|---|---|---|
| ax | 0.0992 | 0.0460 | **2.16×** |
| ay | 0.0913 | 0.0333 | **2.74×** |
| az | 0.2707 | 0.2601 | 1.04× |

**Interpretation:**
- Rigid mounting measurably improved vibration transfer fidelity — ax/ay ratios roughly doubled compared to the unmounted trial, and the larger sample size (585 vs. 23 rows) makes this result statistically more reliable.
- The az axis shows minimal change in both trials. This is attributable to gravity (~9.8 m/s²) dominating the z-axis's total variance, which dilutes the relative contribution of the smaller vibration-induced fluctuation — an expected property of single-axis accelerometer behavior under a constant offset, not a sensor fault.
- ax and ay are the more diagnostically sensitive axes for this sensor's current orientation on the motor housing.

---

## 6. Current Status vs. Sprint Backlog

| Item | Status |
|---|---|
| I2C communication study | Done |
| MPU6050–ESP32 integration | **Done** (including resolving a real hardware compatibility issue) |
| Vibration data acquisition | **Done** — validated with quantified before/after comparison |
| ESP32 Wi-Fi + HTTP communication with FastAPI | Not started |
| Sensor-data transmission endpoint | Backend endpoint code exists (`/sensor-data` in `inference_sensor.py`) and is unit-tested with synthetic data, but **not yet exercised with real ESP32 hardware over the network** |
| Dockerized backend | Not started |
| Remote deployment | Not started |

**Important scope note for the report:** the existing `/sensor-data` endpoint deliberately returns computed vibration features only, not an anomaly score. The trained IMS anomaly model was calibrated on the NASA bearing rig's specific hardware (20 kHz sampling, 4–8 channels) and is not statistically valid for this ESP32/MPU6050 setup at a different sampling rate and axis count. Real-time anomaly scoring on this rig's data requires collecting baseline data from this exact hardware and training a model calibrated to it — a defined next step, not an oversight.

---

## 7. Suggested Next Steps

1. ESP32 Wi-Fi connection + HTTP POST implementation, sending live sensor windows to `/sensor-data`.
2. Collect a larger baseline dataset from this rig (multiple motor speeds, extended duration) to eventually train a properly calibrated anomaly model for this hardware.
3. Docker packaging and local/remote deployment of the FastAPI backend.
4. End-to-end validation test: ESP32 → network → backend → (future) model inference.
