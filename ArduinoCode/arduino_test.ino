#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <utility/imumaths.h>

Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);

void setup() {
  Serial.begin(9600);
  Serial.println("Orientation Sensor Test"); Serial.print('"');

  if (!bno.begin()){
    Serial.print("No BNO055 detected.");
  }

  delay(1000);

  bno.setExtCrystalUse(true);

  Serial.print("Initialized successfully.");
  
}

void loop() {
  sensors_event_t event;
  bno.getEvent(&event);

  Serial.print("X: ");
  Serial.print(event.orientation.x, 4);
  Serial.print("\tY: ");
  Serial.print(event.orientation.y, 4);
  Serial.print("\tZ: ");
  Serial.print(event.orientation.z, 4);
  Serial.print("\t: ");
  Serial.print(event.orientation.x, 4);
  Serial.print("\t: ");
  Serial.print(event.orientation.y, 4);
  Serial.print("\t: ");
  Serial.print(event.orientation.z, 4);

  delay(50);
}
