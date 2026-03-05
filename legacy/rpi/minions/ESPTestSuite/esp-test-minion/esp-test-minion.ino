#include <SoftwareSerial.h>
#include "ModbusRTUSlave.h"

#define RX_PIN 4
#define TX_PIN 0
#define DE_PIN 5
#define SLAVE_ID 1
#define BUFFER_SIZE 256

SoftwareSerial swSerial(RX_PIN, TX_PIN);
uint8_t buf[BUFFER_SIZE]; 
ModbusRTUSlave slave(swSerial, buf, sizeof(buf), DE_PIN);

uint16_t holdingRegister[1];

// Callbacks
int holdingRegisterRead(uint16_t index) {
  return holdingRegister[index];
}

bool holdingRegisterWrite(uint16_t index, uint16_t value) {
  holdingRegister[index] = value;
  return true;
}

void setup() {
  Serial.begin(9600);

  // Configure the Modbus Slave
  slave.configureHoldingRegisters(1, holdingRegisterRead, holdingRegisterWrite);
  slave.begin(SLAVE_ID, 9600, SERIAL_8N1); // 9600 baud rate, 8 data bits, No parity, 1 stop bit
}

void loop() {
  slave.poll();

  if(holdingRegister[0] != 0) {
    Serial.print("Value in Holding Register: ");
    Serial.println(holdingRegister[0]);
  }
}
