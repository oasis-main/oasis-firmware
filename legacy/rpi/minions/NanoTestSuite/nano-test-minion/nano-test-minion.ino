#include <ArduinoModbus.h>

void setup() {
  Serial.begin(9600);
  
  if (!ModbusRTUServer.begin(1, 9600)) {
    Serial.println("Failed to start Modbus RTU Server!");
  }

  // Configure a single holding register at address 0
  ModbusRTUServer.configureHoldingRegisters(0, 1);
}

void loop() {
  ModbusRTUServer.poll();
  
  // if register 0 changes, print new value
  int value = ModbusRTUServer.holdingRegisterRead(0);
  if (value != -1) {
    Serial.print("Received data: ");
    Serial.println(value);
  }
}
