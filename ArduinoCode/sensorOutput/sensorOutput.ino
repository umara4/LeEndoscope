#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_LSM6DSO32.h>

Adafruit_LSM6DSO32 lsm;

static const uint32_t LOG_HZ = 833;
static const uint32_t LOG_PERIOD_US = 1000000UL / LOG_HZ;  // ~1200 us

uint32_t last_us = 0;
bool sensor_ok = false;

// Simple line-based command buffer for host sync.
String cmd_buf;

// Helper: (re)configure sensor ODR and ranges
static bool configure_sensor() {
  lsm.setAccelRange(LSM6DSO32_ACCEL_RANGE_4_G);
  lsm.setGyroRange(LSM6DS_GYRO_RANGE_1000_DPS);
  lsm.setAccelDataRate(LSM6DS_RATE_833_HZ);
  lsm.setGyroDataRate(LSM6DS_RATE_833_HZ);
  return true;
}

static void handle_command(const String& cmd) {
  if (cmd.length() == 0) return;
  if (cmd == "SYNC") {
    Serial.print("SYNC,");
    Serial.println((uint32_t)micros());
  }
  else if (cmd == "RESET_IMU") {
    Serial.println("IMU_RESETTING");
    Wire.begin();
    Wire.setClock(400000);
    if (!lsm.begin_I2C()) {
      Serial.println("IMU_ERROR");
      return;
    }
    configure_sensor();
    delay(100);
    sensor_ok = true;
    last_us = micros();
    Serial.println("IMU_READY");
  }
}

void setup() {
  Serial.setTxBufferSize(1024);
  Serial.begin(921600);
  delay(500);

  Wire.begin();
  Wire.setClock(400000);

  if (lsm.begin_I2C()) {
    configure_sensor();
    delay(100);
    sensor_ok = true;
    Serial.println("Timestamp, A.X, A.Y, A.Z, W.X, W.Y, W.Z");
  } else {
    // Sensor not found -- keep serial alive so RESET_IMU can retry later
    Serial.println("IMU_ERROR_STARTUP");
  }
}

void loop() {
  // Always process commands, even if sensor is not ready
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmd_buf.length() > 0) {
        handle_command(cmd_buf);
        cmd_buf = "";
      }
    } else {
      if (cmd_buf.length() < 64) {
        cmd_buf += c;
      }
    }
  }

  if (!sensor_ok) return;

  uint32_t now = micros();
  if ((uint32_t)(now - last_us) < LOG_PERIOD_US) return;
  last_us = now;

  sensors_event_t accel, gyro, temp;
  lsm.getEvent(&accel, &gyro, &temp);

  char buf[96];
  int len = snprintf(buf, sizeof(buf),
    "%lu,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n",
    (unsigned long)now,
    accel.acceleration.x, accel.acceleration.y, accel.acceleration.z,
    gyro.gyro.x, gyro.gyro.y, gyro.gyro.z);
  Serial.write(buf, len);
}
