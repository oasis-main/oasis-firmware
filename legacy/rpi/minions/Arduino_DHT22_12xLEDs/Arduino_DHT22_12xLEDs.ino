//Include modules
#include <Wire.h>
#include <DHT.h>
#include <FastLED.h>

// intiialize temp & hum sensor
#define DHTTYPE DHT22   // DHT 22  (AM2302)
#define DHTPIN 5
DHT dht(DHTPIN, DHTTYPE);

//set up LED controller
#define LEDPIN 2
#define NUMOFLEDS 12
CRGB leds[NUMOFLEDS];
String led_mode = "off";

double temperature, humidity;
int water_low = 0;

void setup() {
  FastLED.addLeds<WS2812B, LEDPIN, GRB>(leds, NUMOFLEDS);
  Serial.begin(9600);
  dht.begin();
  while (!Serial) {
    delay(10);
  }

  //pinMode(water_level_pin, INPUT_PULLUP);

  //off (none, looping)
  if (led_mode == "off"){
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (0, 0, 0);
      FastLED.show();
      delay(40);
    }
  }
}
 
void loop() {

  humidity = dht.readHumidity();
  temperature = dht.readTemperature();
  
  //print data to serial
  Serial.print("{"); //start the json

  Serial.print("\"temperature\":");
  Serial.print(temperature*double(1.80)+double(32)); //convert c to f
  Serial.print(", ");
    
  Serial.print("\"humidity\": ");
  Serial.print(humidity);
  //Serial.print(", "); //no trailing comma, this is the last json field
    
  Serial.print("}"); //close the json and issue new line
  Serial.println();

  //Mode Management
  if (Serial.available() > 0) {
    String led_data = Serial.readStringUntil('\n');
    led_mode = led_data;
  }
  
  //Connected, Running (green, looping)
  if (led_mode =="connected_running"){
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (0, 10, 0);
      FastLED.show();
      delay(40);
    }
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (0, 5, 0);
      FastLED.show();
      delay(40);
    } 
  }

  //Connected, Idle (green, static)
  if (led_mode =="connected_idle"){
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (0, 5, 0);
      FastLED.show();
      delay(40);
    }  
  }

  //Island, Running (white, looping)
  if (led_mode =="offline_running"){
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (10, 10, 10);
      FastLED.show();
      delay(40);
    }
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (5, 5, 5);
      FastLED.show();
      delay(40);
    } 
  }

  //Island, Idle (white, static)
  if (led_mode =="offline_idle"){
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (5, 5, 5);
      FastLED.show();
      delay(40);
    }  
  }

  //Master sends error message (red, static)
  if (led_mode =="error"){
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (5, 0, 0);
      FastLED.show();
      delay(40);
    }  
  }

  //AP-mode, Server accepting connections (blue, looping)
  if (led_mode =="accepting_wifi_connection"){
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (0, 0, 10);
      FastLED.show();
      delay(40);
    }
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (0, 0, 5);
      FastLED.show();
      delay(40);
    } 
  }

  //off (none, looping)
  if (led_mode == "off"){
    for (int i = 0; i <= 11; i++) {
      leds[i] = CRGB (0, 0, 0);
      FastLED.show();
      delay(40);
    }
  }

  Serial.println(led_mode);  
  
  delay(20);
}
