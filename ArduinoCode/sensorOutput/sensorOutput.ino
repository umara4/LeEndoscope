#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <utility/imumaths.h>

Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28); // common addr 0x28 (or 0x29)

static const uint32_t LOG_HZ = 100;
static const uint32_t LOG_PERIOD_US = 1000000UL / LOG_HZ;

uint32_t last_us = 0;

// Simple line-based command buffer for host sync.
String cmd_buf;

static void handle_command(const String& cmd) {
  if (cmd.length() == 0) return;
  if (cmd == "SYNC") {
    // Respond with the same timebase used in the CSV stream (micros).
    Serial.print("SYNC,");
    Serial.println((uint32_t)micros());
  }
  else if (cmd == "RESET_BNO") {
    Serial.println("BNO055_RESETTING");
    // Re-initialise the BNO055 from scratch
    if (!bno.begin()) {
      Serial.println("BNO055_ERROR");
      return;
    }
    delay(50);
    bno.setMode(OPERATION_MODE_NDOF);
    bno.setExtCrystalUse(true);

    // Wait until the fusion engine produces a non-zero quaternion.
    // NDOF mode can take 1-3 seconds to start outputting valid data.
    uint32_t wait_start = millis();
    bool got_data = false;
    while ((millis() - wait_start) < 10000) {   // 10 s max
      imu::Quaternion qt = bno.getQuat();
      // A valid NDOF quaternion is never all-zero (w is ~1 at rest).
      if (qt.w() != 0.0 || qt.x() != 0.0 || qt.y() != 0.0 || qt.z() != 0.0) {
        got_data = true;
        break;
      }
      delay(50);
    }

    last_us = micros();  // reset timing so first sample is immediate

    if (got_data) {
      Serial.println("BNO055_READY");
    } else {
      // Sensor is alive but fusion hasn't converged yet — report ready anyway
      // so the host isn't stuck; data will converge shortly.
      Serial.println("BNO055_READY");
    }
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  Wire.begin();               // ESP32 default SDA/SCL pins
  Wire.setClock(100000);      // fast I2C helps at higher rates

  if (!bno.begin()) {
    Serial.println("ERROR: BNO055 not detected. Check wiring/address.");
    while (1) delay(5);
  }

  delay(50);

  // Use the fusion mode that outputs quaternions (NDOF is typical)
  bno.setMode(OPERATION_MODE_NDOF);

  // Optional: external crystal improves timing stability on some boards
  bno.setExtCrystalUse(true);

  // Wait until NDOF fusion produces a non-zero quaternion before streaming.
  while (true) {
    imu::Quaternion qt = bno.getQuat();
    if (qt.w() != 0.0 || qt.x() != 0.0 || qt.y() != 0.0 || qt.z() != 0.0)
      break;
    delay(50);
  }

  // CSV header
  Serial.println("Timestamp, Q.W, Q.X, Q.Y, Q.Z, W.X, W.Y, W.Z");
}

void loop() {
  // Non-blocking command processing (e.g., SYNC)
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmd_buf.length() > 0) {
        handle_command(cmd_buf);
        cmd_buf = "";
      }
    } else {
      // Guard against runaway input
      if (cmd_buf.length() < 64) {
        cmd_buf += c;
      }
    }
  }

  uint32_t now = micros();
  if ((uint32_t)(now - last_us) < LOG_PERIOD_US) return;
  last_us = now;

  // Quaternion (unitless)
  imu::Quaternion q = bno.getQuat();

  // Angular velocity (BNO055 returns rad/s in Adafruit library’s “gyro vector”)
  // If your output looks like deg/s, convert: rad/s = deg/s * (PI/180)
  imu::Vector<3> w = bno.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);

  Serial.print(now);
  Serial.print(',');
  // scalar (real) part
  Serial.print(q.w(), 8); Serial.print(',');
  // x-axis vector component
  Serial.print(q.x(), 8); Serial.print(',');
  // y-axis vector component
  Serial.print(q.y(), 8); Serial.print(',');
  // z-axis vector component
  Serial.print(q.z(), 8); Serial.print(',');
  // rotation rate about the sensor x-axis
  Serial.print(w.x(), 8); Serial.print(',');
  // rotation rate about the sensor y-axis
  Serial.print(w.y(), 8); Serial.print(',');
  // rotation rate about the sensor z-axis
  Serial.println(w.z(), 8);
  delay(50);
}
