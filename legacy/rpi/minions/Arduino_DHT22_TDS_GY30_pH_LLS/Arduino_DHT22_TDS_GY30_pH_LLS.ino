//dependencies
#include <Wire.h> //i2c
#include <BH1750.h> //lux
#include <DHT.h> //temp & hum
#include <OneWire.h> //liquid temp
#include <DallasTemperature.h> 

//temperature & humidity intiialize sensor
#define DHTTYPE DHT22   // DHT 22  (AM2302)
#define DHTPIN 5
DHT dht(DHTPIN, DHTTYPE);

//lux sensor intialize as lightMeter
BH1750 lightMeter;

//ph data
const int phanalogPin = A0; 
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

//liquid temp setup & data
#define ONE_WIRE_BUS 2 // Define to which pin of the Arduino the 1-Wire bus is connected
OneWire oneWire(ONE_WIRE_BUS); // Create a new instance of the oneWire class to communicate with any OneWire device
DallasTemperature sensors(&oneWire); // Pass the oneWire reference to DallasTemperature library

void setup() {
 Serial.begin(9600); //start serial

 dht.begin();
 
 pinMode(tdsanalogPin,INPUT); //start analog pins
 pinMode(phanalogPin,INPUT);

 Wire.begin(); //start i2 bus & minions
 lightMeter.configure(BH1750::CONTINUOUS_HIGH_RES_MODE);
 lightMeter.begin();

 sensors.begin(); // Start up the 1-Wirelibrary
}
 
void loop() {

 //temperature & humidity read sensor values
 double air_temperature_c = dht.readTemperature();
 double relative_humidity = dht.readHumidity();

//lux levels read sensor values
 double lumen_per_sqm = lightMeter.readLightLevel();
 
 //ph read analog pin for ph 10 times
 for(int i=0;i<10;i++) { 
  buf[i]=analogRead(phanalogPin);
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
 double phVol=double(avgValue)*5.0/1024/6; 
 double phValue = -5.45 * phVol + 29.69; 

 //read subsurface temperature
 //Send the command for all devices on the bus to perform a temperature conversion:
 sensors.requestTemperatures();

  // Fetch the temperature in degrees Celsius for device index:
  double tempC = sensors.getTempCByIndex(0); // the index 0 refers to the first device
  // Fetch the temperature in degrees Fahrenheit for device index:
  double tempF = sensors.getTempFByIndex(0);

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
      double compensationCoefficient = 1.0+0.02*(tempC-25.0);
      //liquid_temp compensation
      double compensationVoltage=averageVoltage/compensationCoefficient;
      //convert voltage value to tds value
      tdsValue=(133.42*compensationVoltage*compensationVoltage*compensationVoltage - 255.86*compensationVoltage*compensationVoltage + 857.39*compensationVoltage)*0.5;
      
    }
  }

 //save data to known names
 double temperature = air_temperature_c;
 double humidity = relative_humidity;
 double lux = lumen_per_sqm;
 double subsurface_temperature = tempC;
 double ph = phValue;
 double tds = tdsValue;

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

    Serial.print("\"ph\": ");
    Serial.print(ph);
    Serial.print(", ");

    Serial.print("\"tds\": ");
    Serial.print(tds);
    Serial.print(", ");

    Serial.print("\"subsurface_temperature\": ");
    Serial.print(subsurface_temperature);
    //Serial.print(", "); //no trailing comma, this is the last json field
    
    Serial.print("}"); //close the json and issue new line
    Serial.println();

    //Serial.println(phVol); //calibration of ph
 
 delay(1000);
}
