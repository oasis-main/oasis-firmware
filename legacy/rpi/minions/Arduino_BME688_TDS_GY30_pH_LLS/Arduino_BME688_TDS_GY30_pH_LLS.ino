#include <Wire.h>
#include <BH1750.h>
#include <DHT.h>

//temperature & humidity intiialize sensor
#define DHTTYPE DHT22   // DHT 22  (AM2302)
#define DHTPIN 5
DHT dht(DHTPIN, DHTTYPE);

//lux sensor intialize as lightMeter
BH1750 lightMeter;

//digital pin for water_low
int water_level_pin = 2;

//water_low data
int water_low = 0;
int waterSig4 = 0;
int waterSig3 = 0;
int waterSig2 = 0;
int waterSig1 = 0;
int waterSig0 = 0;

//pH data
const int pHanalogPin = A0; 
int sensorValue = 0; 
unsigned long int avgValue; 
double b;
int buf[10],temp;

//tds data
#define tdsanalogPin A0
#define VREF 5.0              // analog reference voltage(Volt) of the ADC
#define SCOUNT  30            // sum of sample point
int analogBuffer[SCOUNT];     // store the analog value in the array, read from ADC
int analogBufferTemp[SCOUNT];
int analogBufferIndex = 0;
int copyIndex = 0;
double averageVoltage = 0;
double tdsValue = 0;
double liquid_temp = 25;       // current liquid_temp for compensation

// tds median filtering algorithm
int getMedianNum(int bArray[], int iFilterLen){
  int bTab[iFilterLen];
  for (byte i = 0; i<iFilterLen; i++)
  bTab[i] = bArray[i];
  int i, j, bTemp;
  for (j = 0; j < iFilterLen - 1; j++) {
    for (i = 0; i < iFilterLen - j - 1; i++) {
      if (bTab[i] > bTab[i + 1]) {
        bTemp = bTab[i];
        bTab[i] = bTab[i + 1];
        bTab[i + 1] = bTemp;
      }
    }
  }
  if ((iFilterLen & 1) > 0){
    bTemp = bTab[(iFilterLen - 1) / 2];
  }
  else {
    bTemp = (bTab[iFilterLen / 2] + bTab[iFilterLen / 2 - 1]) / 2;
  }
  return bTemp;
}

void setup() {
 Serial.begin(9600); //start serial

 pinMode(water_level_pin, INPUT_PULLUP); //start digital pins
 dht.begin();
 
 pinMode(tdsanalogPin,INPUT); //start analog pins
 pinMode(pHanalogPin,INPUT);

 Wire.begin(); //start i2 bus & minions
 lightMeter.configure(BH1750::CONTINUOUS_HIGH_RES_MODE);
 lightMeter.begin();
}
 
void loop() {

 //temperature & humidity read sensor values
 double air_temperature_c = dht.readTemperature();
 double relative_humidity = dht.readHumidity();

 double lumen_per_sqm = lightMeter.readLightLevel();
 
 //ph read analog pin for pH 10 times
 for(int i=0;i<10;i++) { 
  buf[i]=analogRead(pHanalogPin);
  delay(10);
 }
 //ph calculate average value
 for(int i=0;i<9;i++){
  for(int j=i+1;j<10;j++){
   if(buf[i]>buf[j]) {
    temp=buf[i];
    buf[i]=buf[j];
    buf[j]=temp;
   }
  }
 }
 avgValue=0;
 for(int i=2;i<8;i++){
 avgValue+=buf[i];
 }

 //ph calculate from average voltage
 //make sure to calibrate sensor
 double pHVol=double(avgValue)*5.0/1024/6; 
 double pHValue = -5.45 * pHVol + 29.69; 

 //tds read voltages into buffer
 static unsigned long analogSampleTimepoint = millis();
  if(millis()-analogSampleTimepoint > 40U){     //every 40 milliseconds,read the analog value from the ADC
    analogSampleTimepoint = millis();
    analogBuffer[analogBufferIndex] = analogRead(tdsanalogPin);    //read the analog value and store into the buffer
    analogBufferIndex++;
    if(analogBufferIndex == SCOUNT){ 
      analogBufferIndex = 0;
    }
   }   

  //tds calculate from voltage
  static unsigned long printTimepoint = millis();
  if(millis()-printTimepoint > 800U){
    printTimepoint = millis();
    for(copyIndex=0; copyIndex<SCOUNT; copyIndex++){
      analogBufferTemp[copyIndex] = analogBuffer[copyIndex];
      // read the analog value more stable by the median filtering algorithm, and convert to voltage value
      averageVoltage = getMedianNum(analogBufferTemp,SCOUNT) * (double)VREF / 1024.0;
      //liquid_temp compensation formula: fFinalResult(25^C) = fFinalResult(current)/(1.0+0.02*(fTP-25.0)); 
      double compensationCoefficient = 1.0+0.02*(liquid_temp-25.0);
      //liquid_temp compensation
      double compensationVoltage=averageVoltage/compensationCoefficient;
      //convert voltage value to tds value
      tdsValue=(133.42*compensationVoltage*compensationVoltage*compensationVoltage - 255.86*compensationVoltage*compensationVoltage + 857.39*compensationVoltage)*0.5;
      
    }
  }

  //water_low read sensor 11into buffer
  if (digitalRead(water_level_pin) == HIGH)
  {
    waterSig0 = waterSig1;
    waterSig1 = waterSig2;
    waterSig2 = waterSig3;
    waterSig3 = waterSig4;
    waterSig4 = 1;
  }
  else
  {
    waterSig0 = waterSig1;
    waterSig1 = waterSig2;
    waterSig2 = waterSig3;
    waterSig3 = waterSig4;
    waterSig4 = 0;
  }

  //water_low true if last 5 sensor readings were all positive
  if (waterSig4 == 1 || waterSig3 == 1 || waterSig2 == 1 || waterSig1 == 1 || waterSig0 == 1)
  {
    water_low = 1;
  }
  else
  {
    water_low = 0;
  }
 
 //save data to known names
 double temperature = air_temperature_c;
 double humidity = relative_humidity;
 double lux = lumen_per_sqm;
 double pH = pHValue;
 double tds = tdsValue;
 int water_low = water_low;

 //print data to serial
 Serial.print("{"); //start the json

    Serial.print("\"temperature\":");
    Serial.print(temperature*double(1.80)+double(32)); //convert c to f
    Serial.print(", ");
    
    Serial.print("\"humidity\": ");
    Serial.print(humidity);
    Serial.print(", ");
    
    Serial.print("\"lux\": ");
    Serial.print(lux);
    Serial.print(", ");

    Serial.print("\"pH\": ");
    Serial.print(pH);
    Serial.print(", ");

    Serial.print("\"tds\": ");
    Serial.print(tds);
    Serial.print(", ");

    Serial.print("\"water_low\": ");
    Serial.print(water_low);
    //Serial.print(", "); //no trailing comma, this is the last json field
    
    Serial.print("}"); //close the json and issue new line
    Serial.println();

    //Serial.println(pHVol); //calibration of pH
 
 delay(1000);
}
