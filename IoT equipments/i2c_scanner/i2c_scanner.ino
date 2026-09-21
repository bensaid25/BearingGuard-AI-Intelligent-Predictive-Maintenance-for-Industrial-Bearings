/*
  I2C Scanner — run this BEFORE the full sensor sketch
  ------------------------------------------------------
  Purpose: confirm the ESP32 can actually see the MPU6050
  on the I2C bus, and print its address, before trusting
  any real sensor readings.

  Wiring expected:
    MPU6050 VCC -> 3V3   GND -> GND   SCL -> D22   SDA -> D21

  A working MPU6050 will show up at address 0x68 (default)
  or 0x69 (if the ADO pin is pulled high).
*/

#include <Wire.h>

void setup() {
  Wire.begin(21, 22); // SDA, SCL
  Serial.begin(115200);
  delay(1000);
  Serial.println("\nI2C Scanner starting...");
}

void loop() {
  byte error, address;
  int devicesFound = 0;

  Serial.println("Scanning...");

  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("Device found at address 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
      devicesFound++;
    }
  }

  if (devicesFound == 0) {
    Serial.println("No I2C devices found. Check wiring:");
    Serial.println("  - VCC to 3V3 (not 5V)");
    Serial.println("  - GND to GND");
    Serial.println("  - SCL to D22");
    Serial.println("  - SDA to D21");
  } else {
    Serial.print(devicesFound);
    Serial.println(" device(s) found.");
  }

  delay(3000); // scan again every 3 seconds
}
