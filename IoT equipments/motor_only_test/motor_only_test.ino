/*
  Predictive Maintenance Rig — Motor-Only Bring-up Sketch
  ---------------------------------------------------------
  Purpose: verify the L298N + 12V motor circuit on the ESP32,
  independent of the MPU6050 (use this before the sensor is wired in).

  Wiring:
    L298N   IN1 -> GPIO27   IN2 -> GPIO26   ENA -> GPIO25 (PWM)
            12V/GND -> 12V 1A adapter
            ESP32 GND -> L298N GND (common ground, required)
            OUT1/OUT2 -> motor terminals
*/

// L298N pins
const int IN1 = 18;
const int IN2 = 19;
const int ENA = 15;

// PWM config (ESP32 core 3.x LEDC API - attach by pin directly)
const int PWM_FREQ = 5000;
const int PWM_RES = 8;      // 8-bit -> 0-255
int motorSpeed = 150;       // 0-255, starting speed

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  digitalWrite(IN1, HIGH);  // fixed direction (motor is CCW-only)
  digitalWrite(IN2, LOW);

  ledcAttach(ENA, PWM_FREQ, PWM_RES);
  ledcWrite(ENA, motorSpeed);

  Serial.println("Motor driver initialized.");
  Serial.print("Starting speed: ");
  Serial.println(motorSpeed);
  Serial.println("Type a number 0-255 and press Enter to change speed.");
  Serial.println("Type 0 to stop the motor.");
}

void loop() {
  if (Serial.available()) {
    int val = Serial.parseInt();
    if (val >= 0 && val <= 255) {
      motorSpeed = val;
      ledcWrite(ENA, motorSpeed);
      Serial.print("Motor speed set to: ");
      Serial.println(motorSpeed);
    } else {
      Serial.println("Invalid value, enter 0-255.");
    }
  }
}
