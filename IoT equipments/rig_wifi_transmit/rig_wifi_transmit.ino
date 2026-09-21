/*
  Predictive Maintenance Rig — WiFi + HTTP Transmission
  ---------------------------------------------------------
  Purpose: connect to WiFi, sample the MPU6050/6500 sensor, and POST
  a window of readings to the FastAPI backend's /sensor-data endpoint,
  matching the SensorVibrationRequest schema.

  BEFORE UPLOADING, FILL IN:
    - WIFI_SSID / WIFI_PASSWORD below
    - SERVER_IP: your laptop's LOCAL network IP (not "localhost" -
      find it on Windows with: ipconfig, look for "IPv4 Address"
      under your active WiFi adapter, e.g. 192.168.1.42)

  Requires the ArduinoJson library (Library Manager -> search
  "ArduinoJson" by Benoit Blanchon, install the latest 6.x or 7.x).

  Wiring: same as rig_bringup.ino
    MPU6050/6500  VCC->3.3V  GND->GND  SCL->GPIO22  SDA->GPIO21
    L298N         IN1->GPIO18  IN2->GPIO19  ENA->GPIO15 (PWM)
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <time.h>

// ---- FILL THESE IN ----
const char* WIFI_SSID = "ooredoo5B1DF2";
const char* WIFI_PASSWORD = "706CF4E1Tm=74";
const char* SERVER_IP = "192.168.0.6";
const int SERVER_PORT = 8000;
const char* ENDPOINT_PATH = "/sensor-data";
// ------------------------

#define MPU_ADDR 0x68
#define PWR_MGMT_1   0x6B
#define ACCEL_CONFIG 0x1C
#define GYRO_CONFIG  0x1B
#define ACCEL_XOUT_H 0x3B

const int IN1 = 18;
const int IN2 = 19;
const int ENA = 15;
const int PWM_FREQ = 5000;
const int PWM_RES = 8;
int motorSpeed = 150;

const float ACCEL_SCALE = 16384.0;
const float GYRO_SCALE  = 131.0;

const int SAMPLES_PER_WINDOW = 50;
const unsigned long SAMPLE_INTERVAL_MS = 20; // 50Hz sampling -> matches sampling_rate_hz below
const float SAMPLING_RATE_HZ = 1000.0 / SAMPLE_INTERVAL_MS;

float axBuf[SAMPLES_PER_WINDOW];
float ayBuf[SAMPLES_PER_WINDOW];
float azBuf[SAMPLES_PER_WINDOW];

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

bool readAccel(float &ax, float &ay, float &az) {
  uint8_t buf[6];
  if (!mpuReadBytes(ACCEL_XOUT_H, 6, buf)) return false;
  int16_t rawAx = (buf[0] << 8) | buf[1];
  int16_t rawAy = (buf[2] << 8) | buf[3];
  int16_t rawAz = (buf[4] << 8) | buf[5];
  ax = rawAx / ACCEL_SCALE * 9.80665;
  ay = rawAy / ACCEL_SCALE * 9.80665;
  az = rawAz / ACCEL_SCALE * 9.80665;
  return true;
}

String getIsoTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return "1970-01-01T00:00:00Z"; // fallback if NTP hasn't synced yet
  }
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buf);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);      // force station-only mode, not AP+STA
  WiFi.disconnect(true);    // clear any previous connection state
  delay(1000);

  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print("Status code: ");
    Serial.println(WiFi.status());
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected. IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("FAILED to connect after 20 seconds.");
  }
}

void sendWindow() {
  StaticJsonDocument<4096> doc;
  doc["device_id"] = "motor_01";
  doc["timestamp"] = getIsoTimestamp();
  doc["sampling_rate_hz"] = SAMPLING_RATE_HZ;

  JsonArray samples = doc.createNestedArray("samples");
  for (int i = 0; i < SAMPLES_PER_WINDOW; i++) {
    JsonObject s = samples.createNestedObject();
    s["ax"] = axBuf[i];
    s["ay"] = ayBuf[i];
    s["az"] = azBuf[i];
  }

  String payload;
  serializeJson(doc, payload);

  HTTPClient http;
  String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + String(ENDPOINT_PATH);
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  int httpCode = http.POST(payload);

  Serial.print("POST -> HTTP ");
  Serial.println(httpCode);
  if (httpCode > 0) {
    String response = http.getString();
    Serial.println("Response: " + response);
  } else {
    Serial.print("POST failed, error: ");
    Serial.println(http.errorToString(httpCode));
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  connectWiFi();

  // Sync time via NTP - needed for a valid ISO8601 timestamp
  configTime(0, 0, "pool.ntp.org");
  Serial.println("Waiting for NTP time sync...");
  struct tm timeinfo;
  int retries = 0;
  while (!getLocalTime(&timeinfo) && retries < 10) {
    delay(500);
    retries++;
  }

  // Sensor setup (raw register mode - see rig_bringup.ino for why)
  Wire.begin(21, 22);
  Wire.setClock(100000);
  delay(100);
  mpuWriteReg(PWR_MGMT_1, 0x00);
  delay(50);
  mpuWriteReg(ACCEL_CONFIG, 0x00);
  mpuWriteReg(GYRO_CONFIG, 0x00);
  Serial.println("Sensor initialized.");

  // Motor setup - runs at fixed speed so there's real vibration to capture
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  ledcAttach(ENA, PWM_FREQ, PWM_RES);
  ledcWrite(ENA, motorSpeed);
  Serial.println("Motor running. Beginning sample-and-send loop.");
}

void loop() {
  // Fill one window of samples
  for (int i = 0; i < SAMPLES_PER_WINDOW; i++) {
    float ax, ay, az;
    if (readAccel(ax, ay, az)) {
      axBuf[i] = ax;
      ayBuf[i] = ay;
      azBuf[i] = az;
    } else {
      axBuf[i] = ayBuf[i] = azBuf[i] = 0;
    }
    delay(SAMPLE_INTERVAL_MS);
  }

  if (WiFi.status() == WL_CONNECTED) {
    sendWindow();
  } else {
    Serial.println("WiFi disconnected, skipping send.");
  }
}
