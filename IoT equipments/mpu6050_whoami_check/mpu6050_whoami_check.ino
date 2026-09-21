/*
  MPU6050 Raw WHO_AM_I Diagnostic
  ---------------------------------
  Purpose: bypass the Adafruit library entirely and read the chip's
  identity register directly. This tells us whether this is a genuine
  MPU6050 (should report 0x68) or a clone reporting something else,
  which would explain why the scanner finds it but mpu.begin() fails.

  Wiring: same as before - VCC->3V3, GND->GND, SCL->D22, SDA->D21
*/

#include <Wire.h>

#define MPU6050_ADDR 0x68
#define WHO_AM_I_REG 0x75

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(21, 22);
  Wire.setClock(100000);
  delay(100);

  Serial.println("Reading WHO_AM_I register directly...");

  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(WHO_AM_I_REG);
  byte error = Wire.endTransmission(false); // repeated start, keep bus held

  if (error != 0) {
    Serial.print("Error writing register address, code: ");
    Serial.println(error);
    return;
  }

  Wire.requestFrom(MPU6050_ADDR, 1, true);
  if (Wire.available()) {
    byte whoAmI = Wire.read();
    Serial.print("WHO_AM_I register value: 0x");
    Serial.println(whoAmI, HEX);
    Serial.println("(Genuine MPU6050 should report 0x68)");
  } else {
    Serial.println("No data returned from WHO_AM_I read.");
  }

  // --- Also try waking the device up, in case it's stuck in sleep mode ---
  Serial.println("\nAttempting to wake device (write 0x00 to PWR_MGMT_1)...");
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(0x6B); // PWR_MGMT_1 register
  Wire.write(0x00); // wake up, clear sleep bit
  byte wakeError = Wire.endTransmission(true);
  Serial.print("Wake write result (0 = success): ");
  Serial.println(wakeError);
}

void loop() {
  // nothing - single diagnostic run, check Serial output once
}
