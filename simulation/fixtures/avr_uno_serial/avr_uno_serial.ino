void setup(){ Serial.begin(9600); pinMode(13, OUTPUT); }
unsigned long n=0;
void loop(){ digitalWrite(13, n&1); Serial.print("tick "); Serial.println(n++); delay(100); if(n>5){ while(1){} } }
