// Basic demo for readings from Adafruit SCD30
#include <Adafruit_SCD30.h>
#include <Adafruit_VEML7700.h>

Adafruit_SCD30  scd30;
Adafruit_VEML7700 veml = Adafruit_VEML7700();

void setup() {
  Serial.begin(9600);
  while (!Serial) delay(10);     // will pause until serial console opens

  //Serial.println("Initialized Serial Port.");

  // Try to initialize scd30
  if (!scd30.begin()) {
    //Serial.println("Failed to find SCD30 Temp, Hum, & Co2 Sensor.");
    while (1) { delay(10); }
  }
  //Serial.println("SCD30 is online.");


  if (!veml.begin()) {
    //Serial.println("Failed to find VEML7700 Lux Sensor.");
    while (1);
  }
  //Serial.println("VEML7700 is online.");
  
  veml.setGain(VEML7700_GAIN_1);
  veml.setIntegrationTime(VEML7700_IT_800MS);
  veml.setLowThreshold(10000);
  veml.setHighThreshold(20000);
  veml.interruptEnable(true);

  //veml7700 debug
  //Serial.print(F("Gain: "));
  //switch (veml.getGain()) {
  //  case VEML7700_GAIN_1: Serial.println("1"); break;
  //  case VEML7700_GAIN_2: Serial.println("2"); break;
  //  case VEML7700_GAIN_1_4: Serial.println("1/4"); break;
  //  case VEML7700_GAIN_1_8: Serial.println("1/8"); break;
  //}

  //Serial.print(F("Integration Time (ms): "));
  //switch (veml.getIntegrationTime()) {
  //  case VEML7700_IT_25MS: Serial.println("25"); break;
  //  case VEML7700_IT_50MS: Serial.println("50"); break;
  //  case VEML7700_IT_100MS: Serial.println("100"); break;
  //  case VEML7700_IT_200MS: Serial.println("200"); break;
  //  case VEML7700_IT_400MS: Serial.println("400"); break;
  //  case VEML7700_IT_800MS: Serial.println("800"); break;
  //}

  //veml.powerSaveEnable(true);
  //veml.setPowerSaveMode(VEML7700_POWERSAVE_MODE4);

  //scd30 debug
  // if (!scd30.setMeasurementInterval(10)){
  //   Serial.println("Failed to set measurement interval");
  //   while(1){ delay(10);}
  // }
  //Serial.print("Measurement Interval: "); 
  //Serial.print(scd30.getMeasurementInterval()); 
  //Serial.println(" seconds");
}

void loop() {
  if (scd30.dataReady()){
    //Serial.println("Data available!");

    if (!scd30.read()){
      //Serial.println("Error reading sensor data"); 
      return;
    }

    Serial.print("{"); //start the json

    Serial.print("\"temperature\":");
    Serial.print((double(scd30.temperature)*double(1.8))+double(32));
    Serial.print(", ");
    
    Serial.print("\"humidity\": ");
    Serial.print(scd30.relative_humidity);
    Serial.print(", ");
    
    Serial.print("\"co2\": ");
    Serial.print(scd30.CO2, 2);
    Serial.print(", ");

    Serial.print("\"lux\": ");
    Serial.print(veml.readLux());
    //Serial.print(", "); //no trailing comma, this is the last json field
    
    Serial.print("}"); //close the json and issue new line
    Serial.println();
  } else {
    continue;
    //Serial.println("No data");
  }

  delay(100);
}
