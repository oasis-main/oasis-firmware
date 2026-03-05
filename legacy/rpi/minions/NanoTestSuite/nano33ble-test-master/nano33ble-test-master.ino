#include <ArduinoModbus.h>

//Modbus communication
const int DE_PIN = 7;  // Driver Enable pin (Ties to Receiver Enable) for RS485 
const int RE_PIN = 6;  // Driver Enable pin (Ties to Driver Enable) for RS485 
const int SLAVE_ID = 001;
const int REGISTER_ID = 00;

void setup() {
  Serial.begin(9600);
  Serial1.begin(9600);
  pinMode(DE_PIN, OUTPUT);  // Configure DE pin as output
  pinMode(RE_PIN, OUTPUT);  // Configure DE pin as output

  if (!ModbusRTUClient.begin(Serial1)) {
    Serial.println("Failed to start Modbus RTU Client!");
  }
  
}

void loop() {
  uint16_t value = 1234; // example data

  ModbusRTUClient.holdingRegisterRead

  digitalWrite(DE_PIN, LOW);  // Set RS485 to receive mode
  digitalWrite(RE_PIN, LOW);  // Set RS485 to receive mode
  delay(100);
  long readValue = ModbusRTUClient.holdingRegisterRead(SLAVE_ID, REGISTER_ID);
  if (readValue < 0) {
    Serial.println("Modbus Read#1 Failed");
    Serial.println(ModbusRTUClient.lastError());
  } else {
    Serial.print("Read#1 Value: ");
    Serial.println(readValue);
  }

  delay(1000);
}
