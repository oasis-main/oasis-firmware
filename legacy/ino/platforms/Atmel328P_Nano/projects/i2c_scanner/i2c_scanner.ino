#include <Wire.h> // Include Wire library for I2C communication

#define WIRE Wire // Set I2C bus to use: Wire, Wire1, etc.

void initializeI2C() {
  WIRE.begin(); // Initialize the I2C bus
}

void initializeSerial() {
  Serial.begin(9600); // Start serial communication at 9600 baud
  while (!Serial); // Wait until the serial port is open
  Serial.println("\nI2C Scanner");
}

void scanForDevices() {
  // Initialize local variables
  byte error;
  int address;
  int nDevices = 0;

  Serial.println("Scanning..."); // Print scanning message

  // Iterate over all possible I2C addresses (1-127)
  for (address = 1; address < 127; address++) {
    error = performI2CTransmission(address); // Perform I2C transmission

    // Check if there was an error
    if (error == 0) {
      printDeviceFound(address); // If a device is found, print the address
      nDevices++;
    } else if (error == 4) {
      printUnknownError(address); // If there was an unknown error, print the address
    }
  }

  printDevicesFound(nDevices); // Print the number of devices found
}

byte performI2CTransmission(int address) {
  WIRE.beginTransmission(address); // Start transmission to device
  return WIRE.endTransmission(); // End transmission and return status
}

void printDeviceFound(int address) {
  Serial.print("I2C device found at address 0x"); 
  if (address < 16) 
    Serial.print("0");
  Serial.print(address, HEX); 
  Serial.println(" !");
}

void printUnknownError(int address) {
  Serial.print("Unknown error at address 0x"); 
  if (address < 16) 
    Serial.print("0");
  Serial.println(address, HEX); 
}

void printDevicesFound(int nDevices) {
  if (nDevices == 0) 
    Serial.println("No I2C devices found\n");
  else 
    Serial.println("done\n");
}

void loop() {
  scanForDevices(); // Search for I2C devices on the bus
  delay(5000); // Wait 5 seconds between scans
}

void setup() {
  initializeI2C(); // Initialize I2C
  initializeSerial(); // Initialize Serial communication
}

