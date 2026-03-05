#include <ArduinoModbus.h>
#include <NeoSWSerial.h>

#define TIMEOUT 2000  // Timeout period in milliseconds

//Modbus communication
const int TX_PIN = 9;
const int RX_PIN = 8;

const int DE_PIN = 7;  // Driver Enable pin (Ties to Receiver Enable) for RS485 
const int RE_PIN = 6;  // Driver Enable pin (Ties to Driver Enable) for RS485 
const int SLAVE_ID = 1;
const int REGISTER_ID = 10;

NeoSWSerial Serial1(RX_PIN, TX_PIN); // RX, TX
uint8_t message[] = {0x01, 0x03, 0x00, 0x00, 0x00, 0x02, 0xC4, 0x0B};
uint8_t receivedMessage[256];  // To store the received message
uint8_t messageLength = 0;  // Length of the received message

void setup() {
  Serial.begin(9600);
  Serial.println("Starting setup...");
  Serial1.begin(9600);
  pinMode(DE_PIN, OUTPUT);  // Configure DE pin as output
  pinMode(RE_PIN, OUTPUT);  // Configure DE pin as output
  Serial.println("Finished setup!");
}

uint16_t calculateCRC(uint8_t *frame, uint8_t frameLength) {
  uint16_t temp, temp2, flag;
  temp = 0xFFFF;

  for (uint8_t i = 0; i < frameLength; i++) {
    temp = temp ^ frame[i];
    for (uint8_t j = 1; j <= 8; j++) {
      flag = temp & 0x0001;
      temp >>= 1;
      if (flag)
        temp ^= 0xA001;
    }
  }

  // Reverse byte order
  temp2 = temp >> 8;
  temp = (temp << 8) | temp2;
  temp &= 0xFFFF;
  return temp;
}

void loop() {
  Serial.println("Top of loop!");

  Serial.println("Sending Data...");
  digitalWrite(DE_PIN, HIGH);  // Set RS485 to send mode
  digitalWrite(RE_PIN, HIGH);  // Set RS485 to send mode
  for (uint8_t i = 0; i < sizeof(message); i++) {
    Serial1.write(message[i]); // Write each byte of the message
  }

  
  Serial.println("Waiting for the response...");
  digitalWrite(DE_PIN, LOW);  // Set RS485 to receive mode
  digitalWrite(RE_PIN, LOW);  // Set RS485 to receive mode
  unsigned long startTime = millis();
  messageLength = 0;
  while (millis() - startTime < TIMEOUT) {
    if (Serial1.available()) {
      receivedMessage[messageLength++] = Serial1.read();

      // If we received enough data (at least 5 bytes, for address, function, byte count, and CRC)
      if (messageLength >= 0) {
        // Calculate and validate the CRC
        uint16_t receivedCRC = ((uint16_t)receivedMessage[messageLength - 2] << 8) | receivedMessage[messageLength - 1];
        uint16_t calculatedCRC = calculateCRC(receivedMessage, messageLength - 2);  // Ignore the CRC field

        if (receivedCRC != calculatedCRC) {
          for(uint8_t i = 0; i < messageLength; i++) {
            Serial.print(receivedMessage[i], HEX);  // Print each byte in hexadecimal
            Serial.print(" ");  // Add a space between bytes for readability
            }
            Serial.println();  // Print a newline at the end
          break;
        } else {
          Serial.println("Failed CHECK");
          delay(1000);
          break;
        }
      } else {
      Serial.println("Message  not available.");
    }
  
  delay(1000);  // Delay before next loop (could be adjusted based on your needs)
}
  }  }
