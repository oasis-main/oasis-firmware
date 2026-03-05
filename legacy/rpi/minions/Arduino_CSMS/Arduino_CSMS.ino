const double OpenAirReading = 606;   //calibration data 1 Dry Cloth: 614, Open Air: 
const double WaterReading = 430;     //calibration data 2 Wet Cloth: 445, Submerged: 442
double MoistureLevel = 0;
double SoilMoisturePercentage = 0;
 
void setup() {
  Serial.begin(9600); // open serial port, set the baud rate to 9600 bps
}
 
void loop() {
  MoistureLevel = analogRead(A0);  //update based on the analog Pin selected
  //Serial.println(MoistureLevel); // Calibration
  
  
  SoilMoisturePercentage = map(MoistureLevel, OpenAirReading, WaterReading, 0, 100); //map translates raw reading from voltage to moisture
 
  if (SoilMoisturePercentage >= 100)
  {
    SoilMoisturePercentage = double(100);
  }
  else if (SoilMoisturePercentage <= 0)
  {
    SoilMoisturePercentage = double(0);
  }

     //print data to serial
    Serial.print("{"); //start the json
    Serial.print("\"substrate_moisture\": ");
    Serial.print(SoilMoisturePercentage);
    //Serial.print(", "); //no trailing comma, this is the last json field
    
    Serial.print("}"); //close the json and issue new line
    Serial.println();
  
  
  delay(1000);
}
