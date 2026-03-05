#include <Wire.h>
#include <Adafruit_BMP3XX.h>
#include <ArduinoModbus.h>

#define BMP_SDA A4 // BMP390 sensor SDA pin
#define BMP_SCL A5 // BMP390 sensor SCL pin
#define PIR_PIN 5 // PIR sensor pin
#define SOIL_MOISTURE_PIN A2 // Soil moisture sensor pin

Adafruit_BMP3XX bmp; // BMP390 sensor

void setup() {
  Wire.begin();
  Serial.begin(9600);
  
  if (!bmp.begin_I2C()) { 
    Serial.println("Could not find BMP390 sensor!");
  }

  pinMode(PIR_PIN, INPUT);

  if (!ModbusRTUClient.begin(9600)) {
  Serial.println("Failed to start Modbus RTU Client!");
  }
}

void loop() {
  if (!bmp.performReading()) {
    Serial.println("Failed to perform reading :(");
    return;
  }
  Serial.print("Temperature = ");
  Serial.print(bmp.temperature);
  Serial.println(" *C");

  Serial.print("Pressure = ");
  Serial.print(bmp.pressure / 100.0);
  Serial.println(" hPa");

  Serial.print("Approx altitude = ");
  Serial.print(bmp.readAltitude(1013.25)); // this should be adjusted to your local forcase
  Serial.println(" m");

  int pirValue = digitalRead(PIR_PIN);
  Serial.print("PIR Sensor = ");
  Serial.println(pirValue);

  int moistureValue = analogRead(SOIL_MOISTURE_PIN);
  Serial.print("Soil Moisture = ");
  Serial.println(moistureValue);

  //Modbus communication
  uint8_t serverId = 1;
  uint16_t address = 0;
  uint16_t value = 1234; // example data
  
  ModbusRTUClient.holdingRegisterWrite(serverId, address, value);

  delay(1000);
}
