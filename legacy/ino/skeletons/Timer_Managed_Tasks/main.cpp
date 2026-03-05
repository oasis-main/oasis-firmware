/*
  oasis-mcu is an internal standard regarding firmware architecture for more complex environmental microcontroller applications.
  It is designed to be a code-agnostic c++ control flow protocol that guides programmers on how to structure the management of 
  interfaces, data collection, processing, actuation, and communication for embedded applicaitons in a logical, readable way.
  
  Control Flow & Structure (See code sections below):

  Stages:

  [Opening]
  0. Imports
  1. Global Variables (last run time, waiting interval, and data for each section (segment according to stages that first read or write them in setup & loop below.)
  2. Section Functions (3-10 below) & Service Routine Definitions (eg. reboot, sleep, setup wifi)
  
  [Setup]
  3. Hardware (eg. GPIO, sensors, i2c, etc.)
  4. Networking (eg. option to wait for connection or proceed without connection)
  5. Interrupts (eg. button press, other input reading. should call a service routine in response)
  
  [Loop]
  6. Perform Sensor Reads (eg. images, temperature, moisture, co2, imu, etc.)
  7. Data Processing (eg. PID, Image Transformations, Raw Sensor Calibration etc.)
  8. Physical I/O (eg. Pulse Actuators, Flip Switches)
  9. Data Dispatch & Fetch (eg. Serial Communication, HTTPS, MQTTS, LoRA, etc.)
  10. Housekeeping (eg. Call a service routine)

  Rules:
  - '...' default placeholders in comment sections and section function definitions (0-2) indicate where the user should put their code. Leave these blank to do nothing in that section
  - For each operation in one section (the functions for) that must persist data to another, just use global variables and clearly section/comment them.
  - When using global variables, always remember to initialize and handle a default value when called downstream in case of missing data.
  - The stages after setup (2-5) are called sequentially in a loop, with last_run_time and waiting_interval variables declared globally for each section.
    Before calling a section, the current time is recorded and the difference with last_run_time is compared to waiting_interval. If so, we run. If not, we pass.  
    This is so that each piece of code is able to operate at a certain frequency relative to the requirements of network, business, and other processes (eg. rate-constrained database, positioning system relying on slow sensor, credential refresh)
    For a truly asynchronous runtime, please see the oasis-sbc library for Raspberry Pi, Jetson Nano, and other Single Board Computers
  - Only one section function should be allowed to write any given global variable. If any section downstream of 1 looks like it needs to share write access, you must instead create a separate variable to hold that result
  - Use the safest, simplest, stupidest, bare minimum c++ syntax that will get your job done. You should not need years of experience in embedded development to work with this architecture!
*/

//0. Imports
#include <Arduino.h>
#include <time.h> // For time management
/* YOUR CODE HERE */

//1. Global Variables (segment according to sections that first read or write them in setup & loop.)

//Setup (no timers here, since these are run only once on setup)
// hardware variables
/* YOUR CODE HERE */
// networking variables
/* YOUR CODE HERE */
// interrupt variables
/* YOUR CODE HERE */

//Loop (everything here is executed sequentially on a timed interval, which is set to zero by default)
// collect_data_last_run
unsigned long collect_data_last_run = 0;
// collect_data_waiting_interval
unsigned long collect_data_waiting_interval = 0; // milliseconds
// collect_data_variables
/* YOUR CODE HERE */

// process_data_last_run
unsigned long process_data_last_run = 0;
// process_data_waiting_interval
unsigned long process_data_waiting_interval = 0; // milliseconds
// process_data_variables
/* YOUR CODE HERE */

// actuate_io_last_run
unsigned long actuate_io_last_run = 0;
// actuate_io_waiting_interval
unsigned long actuate_io_waiting_interval = 0; // milliseconds
// actuate_io_variables
/* YOUR CODE HERE */

// communicate_last_run
unsigned long communicate_last_run = 0;
// communicate_waiting_interval
unsigned long communicate_waiting_interval = 0; // milliseconds
// communicate_variables
/* YOUR CODE HERE */

// misc_tasks_last_run
unsigned long misc_tasks_last_run = 0;
// misc_tasks_waiting_interval
unsigned long misc_tasks_waiting_interval = 0; // milliseconds
// misc_tasks_variables
/* YOUR CODE HERE */

//2. Service Routines (A) & Section Function (B) Definitions (eg. reboot, sleep, setup wifi. Called below in setup & loop)

//A:
/* YOUR CODE HERE */

//B:
void hardware(){
  /* YOUR CODE HERE */
}

void networking(){
  /* YOUR CODE HERE */
}

void set_interrupts(){
  /* YOUR CODE HERE */
}

void collect_data(){
  /* YOUR CODE HERE */
}

void process_data(){
  /* YOUR CODE HERE */
}

void actuate_io(){
  /* YOUR CODE HERE */
}

void communicate(){
  /* YOUR CODE HERE */
}

void misc_tasks(){
  /* YOUR CODE HERE */
}

//Run functions for stages 3-5
void setup() {
    Serial.begin(9600);
    
    //Call Section Function 3. Hardware (eg. GPIO, sensors, i2c, etc.)
    hardware();
    //Call Section Function 4. Networking (eg. option to wait for connection or proceed without connection)
    networking();
    //Call Section Function 5. Interrupts (eg. button press, other input reading. should call a service routine in response)
    set_interrupts();
}

//Run functions for sections 
void loop() {
  // Check if enough time has elapsed for section 6
  if (millis() - collect_data_last_run >= collect_data_waiting_interval) { 
      collect_data_last_run = millis();
      // Call Section Function 6. Perform Sensor Reads (eg. images, temperature, moisture, co2, imu, etc.)
      collect_data();
  }

  // Check if enough time has elapsed for section 7
  if (millis() - process_data_last_run >= process_data_waiting_interval) {
      process_data_last_run = millis();
      // Call Section Function 7. Data Processing (eg. PID, Image Transformations, Raw Sensor Calibration etc.)
      process_data();
  }

  // Check if enough time has elapsed for section 8
  if (millis() - actuate_io_last_run >= actuate_io_waiting_interval) {
      actuate_io_last_run = millis();
      // Call Section Function 8. Physical I/O (eg. Pulse Actuators, Flip Switches)
      actuate_io();
  }

  // Check if enough time has elapsed for section 9
  if (millis() - communicate_last_run >= communicate_waiting_interval) {
      communicate_last_run = millis();
      // Call Section Function 9. Data Dispatch & Fetch (Serial Communication, HTTPS, MQTTS, LoRA, etc.)
      communicate();
  }

  // Check if enough time has elapsed for section 10
  if (millis() - misc_tasks_last_run >= misc_tasks_waiting_interval) {
      misc_tasks_last_run = millis();
      // Call Section Function 10. Housekeeping (Call service routines(defined in section ))
      misc_tasks();
  }

}