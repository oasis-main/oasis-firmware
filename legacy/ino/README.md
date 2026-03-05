# oasis-arduino
  oasis-arduino is an internal standard regarding firmware architecture for more complex environmental microcontroller applications.
  It is designed to be a code-agnostic c++ control flow protocol that guides programmers on how to structure the management of 
  interfaces, data collection, processing, actuation, and communication for embedded applicaitons in a logical, readable way. this template is a good starting point for organizing Arduino programs, particularly for complex projects that involve multiple tasks such as sensor reading, data processing, actuation, and communication. The template helps ensure that the code is structured and modular, which makes it easier to understand, maintain, and modify. The time-based execution control of different sections allows for managing different tasks at different frequencies, which can be useful in many applications.

  However, every project is unique, and this template may need to be adapted to fit the specific needs and requirements of your application. For simpler projects, this structure might be overly complex and could be simplified. Additionally, you might need to consider specific libraries or peripherals that your project   requires, and make sure they're properly integrated into the template.
  
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

# Resources
Arduino CLI:
https://arduino.github.io/arduino-cli/0.20/
https://roboticsbackend.com/arduino-create-library/

Arduino Esp WiFi:
https://github.com/tzapu/WiFiManager

Arduino Nano Wifi:
https://www.arduino.cc/reference/en/libraries/wifinina/
http://www.getmicros.net/nano33-iot-and-wifi-example.php
