//Include modules
#include <FastLED.h>

//set up LED controller
#define LEDPIN 1
#define NUMOFLEDS 35
CRGB leds[NUMOFLEDS];
String led_mode = "off";

void setup() {
  FastLED.addLeds<WS2812B, LEDPIN, GRB>(leds, NUMOFLEDS);
  Serial.begin(9600);
  
  while (!Serial) {
    delay(10);
  }

  //off (none, looping)
  if (led_mode == "off"){
    for (int i = 0; i <= 34; i++) {
      leds[i] = CRGB (100, 100, 100);
      FastLED.show();
      delay(1);
    }
  }
}
 
void loop() {
  delay(1000);
}
