//! Actuator Driver Templates
//!
//! Each function returns a string of Rust code that implements the actuator driver.

use crate::config::ActuatorType;

/// Get the driver code for an actuator type
pub fn get_actuator_driver(actuator_type: &ActuatorType) -> &'static str {
    match actuator_type {
        ActuatorType::Relay | ActuatorType::RelayNc => RELAY_DRIVER,
        ActuatorType::Led => LED_DRIVER,
        ActuatorType::Buzzer => BUZZER_DRIVER,
        ActuatorType::Pwm => PWM_DRIVER,
        ActuatorType::Servo => SERVO_DRIVER,
        ActuatorType::DcMotor => DC_MOTOR_DRIVER,
        ActuatorType::StepperA4988 | ActuatorType::StepperDrv8825 => STEPPER_DRIVER,
        ActuatorType::StepperTmc2209 => TMC2209_DRIVER,
        ActuatorType::Pca9685 => PCA9685_DRIVER,
        _ => GENERIC_ACTUATOR_DRIVER,
    }
}

/// Get required imports for an actuator type
pub fn get_actuator_imports(actuator_type: &ActuatorType) -> &'static str {
    match actuator_type {
        ActuatorType::Pwm | ActuatorType::Servo | ActuatorType::DcMotor => 
            "use embassy_time::{Duration, Timer};",
        ActuatorType::StepperA4988 | ActuatorType::StepperDrv8825 | ActuatorType::StepperTmc2209 =>
            "use embassy_time::{Duration, Timer};\nuse core::sync::atomic::{AtomicI32, Ordering};",
        ActuatorType::Pca9685 =>
            "use embedded_hal_async::i2c::I2c;",
        _ => "",
    }
}

// =============================================================================
// Relay - Digital on/off control
// =============================================================================
const RELAY_DRIVER: &str = r#"
/// Relay actuator (digital output)
pub struct Relay<P: OutputPin> {
    pin: P,
    normally_closed: bool,
    state: bool,
}

impl<P: OutputPin> Relay<P> {
    pub fn new(pin: P, normally_closed: bool) -> Self {
        let mut relay = Self { pin, normally_closed, state: false };
        relay.set(false);
        relay
    }
    
    pub fn set(&mut self, on: bool) {
        self.state = on;
        // NC relay: active low; NO relay: active high
        let pin_state = if self.normally_closed { !on } else { on };
        if pin_state {
            self.pin.set_high().ok();
        } else {
            self.pin.set_low().ok();
        }
    }
    
    pub fn on(&mut self) { self.set(true); }
    pub fn off(&mut self) { self.set(false); }
    pub fn toggle(&mut self) { self.set(!self.state); }
    pub fn is_on(&self) -> bool { self.state }
}
"#;

// =============================================================================
// LED - Digital or PWM control
// =============================================================================
const LED_DRIVER: &str = r#"
/// LED actuator (digital on/off)
pub struct Led<P: OutputPin> {
    pin: P,
    state: bool,
}

impl<P: OutputPin> Led<P> {
    pub fn new(pin: P) -> Self {
        let mut led = Self { pin, state: false };
        led.off();
        led
    }
    
    pub fn on(&mut self) {
        self.state = true;
        self.pin.set_high().ok();
    }
    
    pub fn off(&mut self) {
        self.state = false;
        self.pin.set_low().ok();
    }
    
    pub fn toggle(&mut self) {
        if self.state { self.off(); } else { self.on(); }
    }
    
    pub fn is_on(&self) -> bool { self.state }
}

/// LED with PWM brightness control
pub struct PwmLed<PWM> {
    pwm: PWM,
    brightness: u16,
    max_duty: u16,
}

impl<PWM: PwmPin> PwmLed<PWM> {
    pub fn new(pwm: PWM) -> Self {
        let max_duty = pwm.max_duty();
        Self { pwm, brightness: 0, max_duty }
    }
    
    pub fn set_brightness(&mut self, percent: u8) {
        let percent = percent.min(100);
        self.brightness = (self.max_duty as u32 * percent as u32 / 100) as u16;
        self.pwm.set_duty(self.brightness);
    }
    
    pub fn on(&mut self) { self.set_brightness(100); }
    pub fn off(&mut self) { self.set_brightness(0); }
}
"#;

// =============================================================================
// Buzzer - Digital or PWM tone generation
// =============================================================================
const BUZZER_DRIVER: &str = r#"
/// Buzzer actuator
pub struct Buzzer<P: OutputPin> {
    pin: P,
}

impl<P: OutputPin> Buzzer<P> {
    pub fn new(pin: P) -> Self {
        let mut buzzer = Self { pin };
        buzzer.off();
        buzzer
    }
    
    pub fn on(&mut self) {
        self.pin.set_high().ok();
    }
    
    pub fn off(&mut self) {
        self.pin.set_low().ok();
    }
    
    pub async fn beep(&mut self, duration_ms: u32) {
        self.on();
        Timer::after(Duration::from_millis(duration_ms as u64)).await;
        self.off();
    }
    
    pub async fn beep_pattern(&mut self, pattern: &[(u32, u32)]) {
        for (on_ms, off_ms) in pattern {
            self.on();
            Timer::after(Duration::from_millis(*on_ms as u64)).await;
            self.off();
            Timer::after(Duration::from_millis(*off_ms as u64)).await;
        }
    }
}
"#;

// =============================================================================
// PWM - Generic PWM output
// =============================================================================
const PWM_DRIVER: &str = r#"
/// Generic PWM output
pub struct PwmOutput<PWM> {
    pwm: PWM,
    max_duty: u16,
}

impl<PWM: PwmPin> PwmOutput<PWM> {
    pub fn new(pwm: PWM) -> Self {
        let max_duty = pwm.max_duty();
        Self { pwm, max_duty }
    }
    
    /// Set duty cycle (0-65535 maps to 0-100%)
    pub fn set_duty(&mut self, duty: u16) {
        self.pwm.set_duty(duty);
    }
    
    /// Set duty cycle as percentage (0-100)
    pub fn set_percent(&mut self, percent: u8) {
        let duty = (self.max_duty as u32 * percent.min(100) as u32 / 100) as u16;
        self.pwm.set_duty(duty);
    }
    
    /// Ramp to target duty over duration
    pub async fn ramp_to(&mut self, target: u16, duration_ms: u32, steps: u32) {
        let current = self.pwm.get_duty();
        let step_duration = duration_ms / steps;
        let step_size = (target as i32 - current as i32) / steps as i32;
        
        for i in 0..steps {
            let duty = (current as i32 + step_size * i as i32) as u16;
            self.pwm.set_duty(duty);
            Timer::after(Duration::from_millis(step_duration as u64)).await;
        }
        self.pwm.set_duty(target);
    }
}
"#;

// =============================================================================
// Servo - PWM-controlled servo motor
// =============================================================================
const SERVO_DRIVER: &str = r#"
/// Servo motor (PWM-controlled)
pub struct Servo<PWM> {
    pwm: PWM,
    min_pulse_us: u16,
    max_pulse_us: u16,
    angle_range: u16,
    current_angle: u16,
    pwm_period_us: u32,
}

impl<PWM: PwmPin> Servo<PWM> {
    /// Create servo with default SG90 parameters
    pub fn new(pwm: PWM) -> Self {
        Self::with_config(pwm, 500, 2500, 180, 20000)
    }
    
    /// Create servo with custom pulse range and angle
    pub fn with_config(pwm: PWM, min_pulse_us: u16, max_pulse_us: u16, angle_range: u16, pwm_period_us: u32) -> Self {
        let mut servo = Self {
            pwm,
            min_pulse_us,
            max_pulse_us,
            angle_range,
            current_angle: 90,
            pwm_period_us,
        };
        servo.set_angle(90);
        servo
    }
    
    /// Set servo angle (0 to angle_range)
    pub fn set_angle(&mut self, angle: u16) {
        let angle = angle.min(self.angle_range);
        self.current_angle = angle;
        
        // Calculate pulse width
        let pulse_range = self.max_pulse_us - self.min_pulse_us;
        let pulse_us = self.min_pulse_us + (pulse_range as u32 * angle as u32 / self.angle_range as u32) as u16;
        
        // Convert to duty cycle
        let max_duty = self.pwm.max_duty();
        let duty = (max_duty as u32 * pulse_us as u32 / self.pwm_period_us) as u16;
        self.pwm.set_duty(duty);
    }
    
    /// Set servo by microseconds pulse width
    pub fn set_pulse_us(&mut self, pulse_us: u16) {
        let pulse_us = pulse_us.clamp(self.min_pulse_us, self.max_pulse_us);
        let max_duty = self.pwm.max_duty();
        let duty = (max_duty as u32 * pulse_us as u32 / self.pwm_period_us) as u16;
        self.pwm.set_duty(duty);
        
        // Update current angle estimate
        let pulse_range = self.max_pulse_us - self.min_pulse_us;
        self.current_angle = ((pulse_us - self.min_pulse_us) as u32 * self.angle_range as u32 / pulse_range as u32) as u16;
    }
    
    /// Sweep from current angle to target
    pub async fn sweep_to(&mut self, target_angle: u16, duration_ms: u32) {
        let start = self.current_angle;
        let steps = duration_ms / 20; // 50Hz update rate
        
        for i in 0..=steps {
            let angle = start as i32 + ((target_angle as i32 - start as i32) * i as i32 / steps as i32);
            self.set_angle(angle as u16);
            Timer::after(Duration::from_millis(20)).await;
        }
    }
    
    pub fn get_angle(&self) -> u16 { self.current_angle }
}
"#;

// =============================================================================
// DC Motor - PWM + direction control
// =============================================================================
const DC_MOTOR_DRIVER: &str = r#"
/// DC Motor with PWM speed and direction control (L298N, TB6612, etc.)
pub struct DcMotor<PWM, DIR1: OutputPin, DIR2: OutputPin> {
    pwm: PWM,
    dir1: DIR1,
    dir2: DIR2,
    max_duty: u16,
    speed: i16,  // -100 to 100
}

impl<PWM: PwmPin, DIR1: OutputPin, DIR2: OutputPin> DcMotor<PWM, DIR1, DIR2> {
    pub fn new(pwm: PWM, dir1: DIR1, dir2: DIR2) -> Self {
        let max_duty = pwm.max_duty();
        let mut motor = Self { pwm, dir1, dir2, max_duty, speed: 0 };
        motor.stop();
        motor
    }
    
    /// Set speed (-100 to 100, negative = reverse)
    pub fn set_speed(&mut self, speed: i16) {
        let speed = speed.clamp(-100, 100);
        self.speed = speed;
        
        if speed == 0 {
            self.stop();
        } else if speed > 0 {
            self.dir1.set_high().ok();
            self.dir2.set_low().ok();
            let duty = (self.max_duty as u32 * speed.abs() as u32 / 100) as u16;
            self.pwm.set_duty(duty);
        } else {
            self.dir1.set_low().ok();
            self.dir2.set_high().ok();
            let duty = (self.max_duty as u32 * speed.abs() as u32 / 100) as u16;
            self.pwm.set_duty(duty);
        }
    }
    
    /// Stop motor (coast)
    pub fn stop(&mut self) {
        self.pwm.set_duty(0);
        self.dir1.set_low().ok();
        self.dir2.set_low().ok();
        self.speed = 0;
    }
    
    /// Brake motor (short windings)
    pub fn brake(&mut self) {
        self.pwm.set_duty(self.max_duty);
        self.dir1.set_high().ok();
        self.dir2.set_high().ok();
        self.speed = 0;
    }
    
    /// Ramp speed over time
    pub async fn ramp_to(&mut self, target_speed: i16, duration_ms: u32) {
        let start = self.speed;
        let steps = duration_ms / 20;
        
        for i in 0..=steps {
            let speed = start + ((target_speed - start) * i as i16 / steps as i16);
            self.set_speed(speed);
            Timer::after(Duration::from_millis(20)).await;
        }
    }
    
    pub fn get_speed(&self) -> i16 { self.speed }
}
"#;

// =============================================================================
// Stepper Motor - A4988/DRV8825 driver
// =============================================================================
const STEPPER_DRIVER: &str = r#"
/// Stepper motor driver (A4988, DRV8825)
pub struct StepperMotor<STEP: OutputPin, DIR: OutputPin, EN: OutputPin> {
    step_pin: STEP,
    dir_pin: DIR,
    enable_pin: EN,
    steps_per_rev: u32,
    position: AtomicI32,
    step_delay_us: u32,
}

impl<STEP: OutputPin, DIR: OutputPin, EN: OutputPin> StepperMotor<STEP, DIR, EN> {
    /// Create stepper with steps per revolution (200 for 1.8° motor)
    pub fn new(step_pin: STEP, dir_pin: DIR, enable_pin: EN, steps_per_rev: u32) -> Self {
        let mut stepper = Self {
            step_pin,
            dir_pin,
            enable_pin,
            steps_per_rev,
            position: AtomicI32::new(0),
            step_delay_us: 1000,  // Default: 1000 steps/sec
        };
        stepper.disable();
        stepper
    }
    
    /// Enable motor driver
    pub fn enable(&mut self) {
        self.enable_pin.set_low().ok();  // Active low
    }
    
    /// Disable motor driver (allows free rotation)
    pub fn disable(&mut self) {
        self.enable_pin.set_high().ok();
    }
    
    /// Set speed in RPM
    pub fn set_speed_rpm(&mut self, rpm: u32) {
        if rpm > 0 {
            self.step_delay_us = 60_000_000 / (rpm * self.steps_per_rev);
        }
    }
    
    /// Set speed in steps per second
    pub fn set_speed_sps(&mut self, sps: u32) {
        if sps > 0 {
            self.step_delay_us = 1_000_000 / sps;
        }
    }
    
    /// Step a number of steps (blocking)
    pub async fn step(&mut self, steps: i32) {
        if steps == 0 { return; }
        
        // Set direction
        if steps > 0 {
            self.dir_pin.set_high().ok();
        } else {
            self.dir_pin.set_low().ok();
        }
        
        let abs_steps = steps.abs() as u32;
        for _ in 0..abs_steps {
            self.step_pin.set_high().ok();
            Timer::after(Duration::from_micros(self.step_delay_us as u64 / 2)).await;
            self.step_pin.set_low().ok();
            Timer::after(Duration::from_micros(self.step_delay_us as u64 / 2)).await;
        }
        
        self.position.fetch_add(steps, Ordering::Relaxed);
    }
    
    /// Move to absolute position
    pub async fn move_to(&mut self, target: i32) {
        let current = self.position.load(Ordering::Relaxed);
        self.step(target - current).await;
    }
    
    /// Rotate by degrees
    pub async fn rotate_degrees(&mut self, degrees: f32) {
        let steps = (degrees * self.steps_per_rev as f32 / 360.0) as i32;
        self.step(steps).await;
    }
    
    /// Get current position in steps
    pub fn get_position(&self) -> i32 {
        self.position.load(Ordering::Relaxed)
    }
    
    /// Reset position to zero
    pub fn zero(&self) {
        self.position.store(0, Ordering::Relaxed);
    }
}
"#;

// =============================================================================
// TMC2209 - UART-controlled stepper driver
// =============================================================================
const TMC2209_DRIVER: &str = r#"
/// TMC2209 stepper driver with UART control
pub struct Tmc2209<UART, STEP: OutputPin, DIR: OutputPin> {
    uart: UART,
    step_pin: STEP,
    dir_pin: DIR,
    address: u8,
    steps_per_rev: u32,
    microsteps: u8,
}

impl<UART, STEP: OutputPin, DIR: OutputPin> Tmc2209<UART, STEP, DIR> {
    pub fn new(uart: UART, step_pin: STEP, dir_pin: DIR, address: u8) -> Self {
        Self {
            uart,
            step_pin,
            dir_pin,
            address,
            steps_per_rev: 200,
            microsteps: 16,
        }
    }
    
    /// Configure via UART (current, microsteps, stealthchop, etc.)
    pub async fn configure(&mut self, current_ma: u16, microsteps: u8, stealthchop: bool) {
        self.microsteps = microsteps;
        // TMC2209 UART protocol implementation would go here
        // Register writes for GCONF, IHOLD_IRUN, CHOPCONF, etc.
    }
    
    /// Enable StealthChop for quiet operation
    pub async fn set_stealthchop(&mut self, enabled: bool) {
        // Write to GCONF register
    }
    
    /// Set run current in milliamps
    pub async fn set_current(&mut self, current_ma: u16) {
        // Write to IHOLD_IRUN register
    }
    
    /// Read stallguard value for sensorless homing
    pub async fn read_stallguard(&mut self) -> u16 {
        // Read SG_RESULT from DRV_STATUS
        0
    }
}
"#;

// =============================================================================
// PCA9685 - I2C PWM driver (16 channels)
// =============================================================================
const PCA9685_DRIVER: &str = r#"
/// PCA9685 16-channel PWM driver
pub struct Pca9685<I2C: I2c> {
    i2c: I2C,
    address: u8,
}

impl<I2C: I2c> Pca9685<I2C> {
    pub const DEFAULT_ADDRESS: u8 = 0x40;
    
    pub async fn new(i2c: I2C, address: u8) -> Result<Self, I2C::Error> {
        let mut driver = Self { i2c, address };
        driver.init().await?;
        Ok(driver)
    }
    
    async fn init(&mut self) -> Result<(), I2C::Error> {
        // Reset
        self.i2c.write(self.address, &[0x00, 0x00]).await?;
        Timer::after(Duration::from_millis(5)).await;
        
        // Set to ~50Hz for servos (prescale = 121)
        self.set_frequency(50).await?;
        
        // Auto-increment, all call
        self.i2c.write(self.address, &[0x00, 0x21]).await?;
        Ok(())
    }
    
    /// Set PWM frequency (24-1526 Hz)
    pub async fn set_frequency(&mut self, freq_hz: u16) -> Result<(), I2C::Error> {
        let prescale = (25_000_000.0 / (4096.0 * freq_hz as f64) - 1.0) as u8;
        
        // Must be in sleep mode to change prescale
        let mut mode1 = [0u8; 1];
        self.i2c.write_read(self.address, &[0x00], &mut mode1).await?;
        
        self.i2c.write(self.address, &[0x00, (mode1[0] & 0x7F) | 0x10]).await?; // Sleep
        self.i2c.write(self.address, &[0xFE, prescale]).await?; // Set prescale
        self.i2c.write(self.address, &[0x00, mode1[0]]).await?; // Restore mode
        Timer::after(Duration::from_micros(500)).await;
        self.i2c.write(self.address, &[0x00, mode1[0] | 0x80]).await?; // Restart
        
        Ok(())
    }
    
    /// Set channel PWM (0-4095)
    pub async fn set_pwm(&mut self, channel: u8, on: u16, off: u16) -> Result<(), I2C::Error> {
        let reg = 0x06 + 4 * channel;
        self.i2c.write(self.address, &[
            reg,
            (on & 0xFF) as u8,
            (on >> 8) as u8,
            (off & 0xFF) as u8,
            (off >> 8) as u8,
        ]).await
    }
    
    /// Set channel duty cycle (0-100%)
    pub async fn set_duty(&mut self, channel: u8, percent: u8) -> Result<(), I2C::Error> {
        let off = (4095 * percent.min(100) as u16 / 100) as u16;
        self.set_pwm(channel, 0, off).await
    }
    
    /// Set servo angle on channel
    pub async fn set_servo_angle(&mut self, channel: u8, angle: u8) -> Result<(), I2C::Error> {
        // Map 0-180° to ~102-512 (500-2500µs at 50Hz)
        let pulse = 102 + (angle.min(180) as u16 * 410 / 180);
        self.set_pwm(channel, 0, pulse).await
    }
    
    /// Turn channel fully on
    pub async fn full_on(&mut self, channel: u8) -> Result<(), I2C::Error> {
        self.set_pwm(channel, 4096, 0).await
    }
    
    /// Turn channel fully off
    pub async fn full_off(&mut self, channel: u8) -> Result<(), I2C::Error> {
        self.set_pwm(channel, 0, 4096).await
    }
}
"#;

const GENERIC_ACTUATOR_DRIVER: &str = r#"
/// Generic actuator placeholder
pub struct GenericActuator<P: OutputPin> {
    pin: P,
}

impl<P: OutputPin> GenericActuator<P> {
    pub fn new(pin: P) -> Self { Self { pin } }
    pub fn set_high(&mut self) { self.pin.set_high().ok(); }
    pub fn set_low(&mut self) { self.pin.set_low().ok(); }
}
"#;
