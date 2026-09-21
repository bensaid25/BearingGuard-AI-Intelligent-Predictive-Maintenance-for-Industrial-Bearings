/*
  Predictive Maintenance Rig — Bring-up Sketch (raw I2C version)
  ------------------------------------------------------------------
  Purpose: verify vibration sensing + L298N motor control on the ESP32.

  Uses RAW I2C register access instead of the Adafruit_MPU6050 library,
  because this specific sensor's WHO_AM_I register reports 0x70
  (MPU6500 chip variant, common on some GY-521 clone boards) rather
  than 0x68 (genuine MPU6050), which causes the Adafruit library's
  identity check to fail even though the sensor itself works fine.
  The MPU6500 shares the same register map as the MPU6050 for
  accelerometer/gyroscope/temperature, so raw register access works
  identically for both.

  Wiring:
    MPU6050/6500  VCC -> 3.3V   GND -> GND   SCL -> GPIO22   SDA -> GPIO21
    L298N         IN1 -> GPIO18  IN2 -> GPIO19  ENA -> GPIO15 (PWM)
                  12V/GND -> 12V 1A adapter
                  ESP32 GND -> L298N GND (common ground, required)
*/

#include <Wire.h>

#define MPU_ADDR 0x68
#define PWR_MGMT_1   0x6B
#define ACCEL_CONFIG 0x1C
#define GYRO_CONFIG  0x1B
#define ACCEL_XOUT_H 0x3B

// L298N pins
const int IN1 = 18;
const int IN2 = 19;
const int ENA = 15;

// PWM config (ESP32 core 3.x LEDC API)
const int PWM_FREQ = 5000;
const int PWM_RES = 8;
int motorSpeed = 150;

unsigned long lastSample = 0;
const unsigned long SAMPLE_INTERVAL_MS = 50;

// Default full-scale sensitivities (range registers left at power-on default)
const float ACCEL_SCALE = 16384.0; // LSB per g, at +/-2g range
const float GYRO_SCALE  = 131.0;   // LSB per deg/s, at +/-250 deg/s range

void mpuWriteReg(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission(true);
}

bool mpuReadBytes(uint8_t startReg, uint8_t count, uint8_t *dest) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(startReg);
  if (Wire.endTransmission(false) != 0) return false;
  Wire.requestFrom(MPU_ADDR, count, true);
  for (int i = 0; i < count; i++) {
    if (!Wire.available()) return false;
    dest[i] = Wire.read();
  }
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  // --- I2C / sensor setup ---
  Wire.begin(21, 22);
  Wire.setClock(100000);
  delay(100);

  mpuWriteReg(PWR_MGMT_1, 0x00);   // wake up (clear sleep bit)
  delay(50);
  mpuWriteReg(ACCEL_CONFIG, 0x00); // +/-2g range
  mpuWriteReg(GYRO_CONFIG, 0x00);  // +/-250 deg/s range

  Serial.println("Sensor initialized (raw register mode).");

  // --- Motor driver setup ---
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);

  ledcAttach(ENA, PWM_FREQ, PWM_RES);
  ledcWrite(ENA, motorSpeed);

  Serial.println("Motor driver initialized. CSV header below:");
  Serial.println("timestamp_ms,ax,ay,az,gx,gy,gz,temp_c");
}

void loop() {
  unsigned long now = millis();
  if (now - lastSample >= SAMPLE_INTERVAL_MS) {
    lastSample = now;

    uint8_t buf[14];
    if (mpuReadBytes(ACCEL_XOUT_H, 14, buf)) {
      int16_t rawAx = (buf[0] << 8) | buf[1];
      int16_t rawAy = (buf[2] << 8) | buf[3];
      int16_t rawAz = (buf[4] << 8) | buf[5];
      int16_t rawTemp = (buf[6] << 8) | buf[7];
      int16_t rawGx = (buf[8] << 8) | buf[9];
      int16_t rawGy = (buf[10] << 8) | buf[11];
      int16_t rawGz = (buf[12] << 8) | buf[13];

      float ax = rawAx / ACCEL_SCALE * 9.80665; // convert g to m/s^2
      float ay = rawAy / ACCEL_SCALE * 9.80665;
      float az = rawAz / ACCEL_SCALE * 9.80665;
      float gx = (rawGx / GYRO_SCALE) * (PI / 180.0); // deg/s to rad/s
      float gy = (rawGy / GYRO_SCALE) * (PI / 180.0);
      float gz = (rawGz / GYRO_SCALE) * (PI / 180.0);
      float tempC = (rawTemp / 340.0) + 36.53;

      Serial.print(now);   Serial.print(",");
      Serial.print(ax, 4); Serial.print(",");
      Serial.print(ay, 4); Serial.print(",");
      Serial.print(az, 4); Serial.print(",");
      Serial.print(gx, 4); Serial.print(",");
      Serial.print(gy, 4); Serial.print(",");
      Serial.print(gz, 4); Serial.print(",");
      Serial.println(tempC, 2);
    } else {
      Serial.println("Sensor read failed.");
    }
  }

  if (Serial.available()) {
    int val = Serial.parseInt();
    if (val >= 0 && val <= 255) {
      motorSpeed = val;
      ledcWrite(ENA, motorSpeed);
      Serial.print("Motor speed set to: ");
      Serial.println(motorSpeed);
    }
  }
}
