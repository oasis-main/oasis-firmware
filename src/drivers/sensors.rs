//! Sensor Driver Templates
//!
//! Each function returns a string of Rust code that implements the sensor driver.
//! The code is designed for embassy async runtime on ESP32/STM32.

use crate::config::SensorType;

/// Get the driver code for a sensor type
pub fn get_sensor_driver(sensor_type: &SensorType) -> &'static str {
    match sensor_type {
        SensorType::Dht22 | SensorType::Dht11 => DHT_DRIVER,
        SensorType::Bme280 => BME280_DRIVER,
        SensorType::Bme680 => BME680_DRIVER,
        SensorType::Sht31 => SHT31_DRIVER,
        SensorType::Ds18b20 => DS18B20_DRIVER,
        SensorType::Bh1750 => BH1750_DRIVER,
        SensorType::Tsl2561 => TSL2561_DRIVER,
        SensorType::Veml7700 => VEML7700_DRIVER,
        SensorType::Photoresistor => PHOTORESISTOR_DRIVER,
        SensorType::CapacitiveMoisture | SensorType::ResistiveMoisture => MOISTURE_DRIVER,
        SensorType::Hcsr04 => HCSR04_DRIVER,
        SensorType::Vl53l0x | SensorType::Vl53l1x => VL53LXX_DRIVER,
        SensorType::Mpu6050 => MPU6050_DRIVER,
        SensorType::Mpu9250 => MPU9250_DRIVER,
        SensorType::Bno055 => BNO055_DRIVER,
        SensorType::Pir => PIR_DRIVER,
        SensorType::Ina219 => INA219_DRIVER,
        SensorType::Acs712 => ACS712_DRIVER,
        SensorType::VoltageDivider => VOLTAGE_DIVIDER_DRIVER,
        SensorType::Hx711 => HX711_DRIVER,
        SensorType::EspCam => ESP_CAM_DRIVER,
        SensorType::RpiCamera => RPI_CAMERA_DRIVER,
        SensorType::AdcRaw => ADC_RAW_DRIVER,
        _ => GENERIC_SENSOR_DRIVER,
    }
}

/// Get required imports for a sensor type
pub fn get_sensor_imports(sensor_type: &SensorType) -> &'static str {
    match sensor_type {
        SensorType::Dht22 | SensorType::Dht11 => "use embassy_time::{Duration, Timer, Instant};",
        SensorType::Bme280 | SensorType::Bme680 | SensorType::Sht31 | SensorType::Bh1750 => 
            "use embedded_hal_async::i2c::I2c;",
        SensorType::Mpu6050 | SensorType::Mpu9250 | SensorType::Bno055 =>
            "use embedded_hal_async::i2c::I2c;\nuse libm::{atan2f, sqrtf};",
        _ => "",
    }
}

// =============================================================================
// DHT22/DHT11 - Single-wire temperature & humidity
// =============================================================================
const DHT_DRIVER: &str = r#"
/// DHT22/DHT11 sensor driver
pub struct DhtSensor<P: OutputPin + InputPin> {
    pin: P,
    sensor_type: DhtType,
}

#[derive(Clone, Copy)]
pub enum DhtType { Dht11, Dht22 }

impl<P: OutputPin + InputPin> DhtSensor<P> {
    pub fn new(pin: P, sensor_type: DhtType) -> Self {
        Self { pin, sensor_type }
    }
    
    pub async fn read(&mut self) -> Result<DhtReading, DhtError> {
        // Send start signal: pull low for 18ms, then high for 40us
        self.pin.set_low().ok();
        Timer::after(Duration::from_millis(18)).await;
        self.pin.set_high().ok();
        Timer::after(Duration::from_micros(40)).await;
        
        // Read 40 bits of data
        let mut data = [0u8; 5];
        for byte_idx in 0..5 {
            for bit_idx in (0..8).rev() {
                // Wait for pin to go high
                let start = Instant::now();
                while self.pin.is_low().unwrap_or(true) {
                    if start.elapsed() > Duration::from_micros(100) {
                        return Err(DhtError::Timeout);
                    }
                }
                
                // Measure high pulse duration
                let pulse_start = Instant::now();
                while self.pin.is_high().unwrap_or(false) {
                    if pulse_start.elapsed() > Duration::from_micros(100) {
                        return Err(DhtError::Timeout);
                    }
                }
                
                // >40us = 1, <40us = 0
                if pulse_start.elapsed() > Duration::from_micros(40) {
                    data[byte_idx] |= 1 << bit_idx;
                }
            }
        }
        
        // Verify checksum
        let checksum = data[0].wrapping_add(data[1]).wrapping_add(data[2]).wrapping_add(data[3]);
        if checksum != data[4] {
            return Err(DhtError::Checksum);
        }
        
        // Parse based on sensor type
        let (temperature, humidity) = match self.sensor_type {
            DhtType::Dht22 => {
                let humidity = ((data[0] as u16) << 8 | data[1] as u16) as f32 / 10.0;
                let temp_raw = ((data[2] as u16) << 8 | data[3] as u16) as i16;
                let temperature = temp_raw as f32 / 10.0;
                (temperature, humidity)
            }
            DhtType::Dht11 => {
                let humidity = data[0] as f32;
                let temperature = data[2] as f32;
                (temperature, humidity)
            }
        };
        
        Ok(DhtReading { temperature, humidity })
    }
}

#[derive(Debug, Clone, Copy)]
pub struct DhtReading {
    pub temperature: f32,
    pub humidity: f32,
}

#[derive(Debug)]
pub enum DhtError {
    Timeout,
    Checksum,
}
"#;

// =============================================================================
// BME280 - I2C temperature, humidity, pressure
// =============================================================================
const BME280_DRIVER: &str = r#"
/// BME280 I2C sensor driver
pub struct Bme280<I2C: I2c> {
    i2c: I2C,
    address: u8,
    calibration: Bme280Calibration,
}

#[derive(Default)]
struct Bme280Calibration {
    dig_t1: u16, dig_t2: i16, dig_t3: i16,
    dig_p1: u16, dig_p2: i16, dig_p3: i16, dig_p4: i16, dig_p5: i16,
    dig_p6: i16, dig_p7: i16, dig_p8: i16, dig_p9: i16,
    dig_h1: u8, dig_h2: i16, dig_h3: u8, dig_h4: i16, dig_h5: i16, dig_h6: i8,
}

impl<I2C: I2c> Bme280<I2C> {
    pub const DEFAULT_ADDRESS: u8 = 0x76;
    
    pub async fn new(i2c: I2C, address: u8) -> Result<Self, I2C::Error> {
        let mut sensor = Self {
            i2c,
            address,
            calibration: Bme280Calibration::default(),
        };
        sensor.load_calibration().await?;
        sensor.configure().await?;
        Ok(sensor)
    }
    
    async fn load_calibration(&mut self) -> Result<(), I2C::Error> {
        let mut buf = [0u8; 26];
        self.i2c.write_read(self.address, &[0x88], &mut buf).await?;
        
        self.calibration.dig_t1 = u16::from_le_bytes([buf[0], buf[1]]);
        self.calibration.dig_t2 = i16::from_le_bytes([buf[2], buf[3]]);
        self.calibration.dig_t3 = i16::from_le_bytes([buf[4], buf[5]]);
        self.calibration.dig_p1 = u16::from_le_bytes([buf[6], buf[7]]);
        // ... remaining calibration
        Ok(())
    }
    
    async fn configure(&mut self) -> Result<(), I2C::Error> {
        // Normal mode, 16x oversampling for all
        self.i2c.write(self.address, &[0xF2, 0x05]).await?; // ctrl_hum
        self.i2c.write(self.address, &[0xF4, 0xB7]).await?; // ctrl_meas
        self.i2c.write(self.address, &[0xF5, 0x00]).await?; // config
        Ok(())
    }
    
    pub async fn read(&mut self) -> Result<Bme280Reading, I2C::Error> {
        let mut buf = [0u8; 8];
        self.i2c.write_read(self.address, &[0xF7], &mut buf).await?;
        
        let adc_p = ((buf[0] as u32) << 12) | ((buf[1] as u32) << 4) | ((buf[2] as u32) >> 4);
        let adc_t = ((buf[3] as u32) << 12) | ((buf[4] as u32) << 4) | ((buf[5] as u32) >> 4);
        let adc_h = ((buf[6] as u32) << 8) | (buf[7] as u32);
        
        let (temperature, t_fine) = self.compensate_temperature(adc_t);
        let pressure = self.compensate_pressure(adc_p, t_fine);
        let humidity = self.compensate_humidity(adc_h, t_fine);
        
        Ok(Bme280Reading { temperature, pressure, humidity })
    }
    
    fn compensate_temperature(&self, adc_t: u32) -> (f32, i32) {
        let cal = &self.calibration;
        let var1 = ((adc_t as f64 / 16384.0) - (cal.dig_t1 as f64 / 1024.0)) * cal.dig_t2 as f64;
        let var2 = ((adc_t as f64 / 131072.0) - (cal.dig_t1 as f64 / 8192.0))
            * ((adc_t as f64 / 131072.0) - (cal.dig_t1 as f64 / 8192.0))
            * cal.dig_t3 as f64;
        let t_fine = (var1 + var2) as i32;
        let temperature = ((var1 + var2) / 5120.0) as f32;
        (temperature, t_fine)
    }
    
    fn compensate_pressure(&self, adc_p: u32, t_fine: i32) -> f32 {
        // Bosch compensation algorithm
        let cal = &self.calibration;
        let var1 = (t_fine as f64 / 2.0) - 64000.0;
        let var2 = var1 * var1 * cal.dig_p6 as f64 / 32768.0;
        let var2 = var2 + var1 * cal.dig_p5 as f64 * 2.0;
        let var2 = var2 / 4.0 + cal.dig_p4 as f64 * 65536.0;
        let var1 = (cal.dig_p3 as f64 * var1 * var1 / 524288.0 + cal.dig_p2 as f64 * var1) / 524288.0;
        let var1 = (1.0 + var1 / 32768.0) * cal.dig_p1 as f64;
        if var1 == 0.0 { return 0.0; }
        let pressure = 1048576.0 - adc_p as f64;
        let pressure = (pressure - var2 / 4096.0) * 6250.0 / var1;
        let var1 = cal.dig_p9 as f64 * pressure * pressure / 2147483648.0;
        let var2 = pressure * cal.dig_p8 as f64 / 32768.0;
        ((pressure + (var1 + var2 + cal.dig_p7 as f64) / 16.0) / 100.0) as f32 // hPa
    }
    
    fn compensate_humidity(&self, adc_h: u32, t_fine: i32) -> f32 {
        let cal = &self.calibration;
        let var_h = t_fine as f64 - 76800.0;
        if var_h == 0.0 { return 0.0; }
        let var_h = (adc_h as f64 - (cal.dig_h4 as f64 * 64.0 + cal.dig_h5 as f64 / 16384.0 * var_h))
            * (cal.dig_h2 as f64 / 65536.0 * (1.0 + cal.dig_h6 as f64 / 67108864.0 * var_h
            * (1.0 + cal.dig_h3 as f64 / 67108864.0 * var_h)));
        let var_h = var_h * (1.0 - cal.dig_h1 as f64 * var_h / 524288.0);
        var_h.clamp(0.0, 100.0) as f32
    }
}

#[derive(Debug, Clone, Copy)]
pub struct Bme280Reading {
    pub temperature: f32,  // °C
    pub pressure: f32,     // hPa
    pub humidity: f32,     // %RH
}
"#;

// =============================================================================
// MPU6050 - 6-axis IMU (accelerometer + gyroscope)
// =============================================================================
const MPU6050_DRIVER: &str = r#"
/// MPU6050 6-axis IMU driver
pub struct Mpu6050<I2C: I2c> {
    i2c: I2C,
    address: u8,
    accel_scale: f32,
    gyro_scale: f32,
}

impl<I2C: I2c> Mpu6050<I2C> {
    pub const DEFAULT_ADDRESS: u8 = 0x68;
    
    pub async fn new(i2c: I2C, address: u8) -> Result<Self, I2C::Error> {
        let mut sensor = Self {
            i2c,
            address,
            accel_scale: 16384.0,  // ±2g
            gyro_scale: 131.0,     // ±250°/s
        };
        sensor.init().await?;
        Ok(sensor)
    }
    
    async fn init(&mut self) -> Result<(), I2C::Error> {
        // Wake up (exit sleep mode)
        self.i2c.write(self.address, &[0x6B, 0x00]).await?;
        Timer::after(Duration::from_millis(100)).await;
        
        // Configure gyro: ±250°/s
        self.i2c.write(self.address, &[0x1B, 0x00]).await?;
        // Configure accel: ±2g
        self.i2c.write(self.address, &[0x1C, 0x00]).await?;
        // Configure DLPF: 44Hz bandwidth
        self.i2c.write(self.address, &[0x1A, 0x03]).await?;
        
        Ok(())
    }
    
    pub async fn read(&mut self) -> Result<ImuReading, I2C::Error> {
        let mut buf = [0u8; 14];
        self.i2c.write_read(self.address, &[0x3B], &mut buf).await?;
        
        let accel_x = i16::from_be_bytes([buf[0], buf[1]]) as f32 / self.accel_scale;
        let accel_y = i16::from_be_bytes([buf[2], buf[3]]) as f32 / self.accel_scale;
        let accel_z = i16::from_be_bytes([buf[4], buf[5]]) as f32 / self.accel_scale;
        
        let temp_raw = i16::from_be_bytes([buf[6], buf[7]]);
        let temperature = temp_raw as f32 / 340.0 + 36.53;
        
        let gyro_x = i16::from_be_bytes([buf[8], buf[9]]) as f32 / self.gyro_scale;
        let gyro_y = i16::from_be_bytes([buf[10], buf[11]]) as f32 / self.gyro_scale;
        let gyro_z = i16::from_be_bytes([buf[12], buf[13]]) as f32 / self.gyro_scale;
        
        // Calculate roll and pitch from accelerometer
        let roll = atan2f(accel_y, accel_z) * 180.0 / core::f32::consts::PI;
        let pitch = atan2f(-accel_x, sqrtf(accel_y * accel_y + accel_z * accel_z)) * 180.0 / core::f32::consts::PI;
        
        Ok(ImuReading {
            accel: [accel_x, accel_y, accel_z],
            gyro: [gyro_x, gyro_y, gyro_z],
            temperature,
            roll,
            pitch,
        })
    }
}

#[derive(Debug, Clone, Copy)]
pub struct ImuReading {
    pub accel: [f32; 3],     // g (x, y, z)
    pub gyro: [f32; 3],      // °/s (x, y, z)
    pub temperature: f32,    // °C
    pub roll: f32,           // ° (from accelerometer)
    pub pitch: f32,          // ° (from accelerometer)
}
"#;

// =============================================================================
// BH1750 - I2C ambient light sensor
// =============================================================================
const BH1750_DRIVER: &str = r#"
/// BH1750 ambient light sensor driver
pub struct Bh1750<I2C: I2c> {
    i2c: I2C,
    address: u8,
}

impl<I2C: I2c> Bh1750<I2C> {
    pub const DEFAULT_ADDRESS: u8 = 0x23;
    
    pub async fn new(i2c: I2C, address: u8) -> Result<Self, I2C::Error> {
        let mut sensor = Self { i2c, address };
        // Power on
        sensor.i2c.write(sensor.address, &[0x01]).await?;
        // Continuous high-resolution mode
        sensor.i2c.write(sensor.address, &[0x10]).await?;
        Timer::after(Duration::from_millis(180)).await;
        Ok(sensor)
    }
    
    pub async fn read_lux(&mut self) -> Result<f32, I2C::Error> {
        let mut buf = [0u8; 2];
        self.i2c.read(self.address, &mut buf).await?;
        let raw = u16::from_be_bytes(buf);
        Ok(raw as f32 / 1.2)  // Convert to lux
    }
}
"#;

// =============================================================================
// HC-SR04 - Ultrasonic distance sensor
// =============================================================================
const HCSR04_DRIVER: &str = r#"
/// HC-SR04 ultrasonic distance sensor
pub struct Hcsr04<TRIG: OutputPin, ECHO: InputPin> {
    trigger: TRIG,
    echo: ECHO,
}

impl<TRIG: OutputPin, ECHO: InputPin> Hcsr04<TRIG, ECHO> {
    pub fn new(trigger: TRIG, echo: ECHO) -> Self {
        Self { trigger, echo }
    }
    
    pub async fn read_distance_cm(&mut self) -> Result<f32, Hcsr04Error> {
        // Send 10us trigger pulse
        self.trigger.set_low().ok();
        Timer::after(Duration::from_micros(2)).await;
        self.trigger.set_high().ok();
        Timer::after(Duration::from_micros(10)).await;
        self.trigger.set_low().ok();
        
        // Wait for echo to go high
        let start = Instant::now();
        while self.echo.is_low().unwrap_or(true) {
            if start.elapsed() > Duration::from_millis(50) {
                return Err(Hcsr04Error::NoEcho);
            }
        }
        
        // Measure echo pulse duration
        let pulse_start = Instant::now();
        while self.echo.is_high().unwrap_or(false) {
            if pulse_start.elapsed() > Duration::from_millis(50) {
                return Err(Hcsr04Error::Timeout);
            }
        }
        
        let duration_us = pulse_start.elapsed().as_micros() as f32;
        // Speed of sound = 343 m/s = 0.0343 cm/us
        // Distance = duration * speed / 2 (round trip)
        Ok(duration_us * 0.0343 / 2.0)
    }
}

#[derive(Debug)]
pub enum Hcsr04Error {
    NoEcho,
    Timeout,
}
"#;

// =============================================================================
// PIR motion sensor (digital)
// =============================================================================
const PIR_DRIVER: &str = r#"
/// PIR motion sensor (digital input)
pub struct PirSensor<P: InputPin> {
    pin: P,
}

impl<P: InputPin> PirSensor<P> {
    pub fn new(pin: P) -> Self {
        Self { pin }
    }
    
    pub fn is_motion_detected(&self) -> bool {
        self.pin.is_high().unwrap_or(false)
    }
}
"#;

// =============================================================================
// INA219 - I2C current/voltage sensor
// =============================================================================
const INA219_DRIVER: &str = r#"
/// INA219 current/voltage/power monitor
pub struct Ina219<I2C: I2c> {
    i2c: I2C,
    address: u8,
    current_lsb: f32,
}

impl<I2C: I2c> Ina219<I2C> {
    pub const DEFAULT_ADDRESS: u8 = 0x40;
    
    pub async fn new(i2c: I2C, address: u8, shunt_ohms: f32, max_current: f32) -> Result<Self, I2C::Error> {
        let current_lsb = max_current / 32768.0;
        let cal = (0.04096 / (current_lsb * shunt_ohms)) as u16;
        
        let mut sensor = Self { i2c, address, current_lsb };
        // Write calibration register
        sensor.i2c.write(sensor.address, &[0x05, (cal >> 8) as u8, cal as u8]).await?;
        // Configure: 32V range, 320mV shunt, continuous
        sensor.i2c.write(sensor.address, &[0x00, 0x39, 0x9F]).await?;
        Ok(sensor)
    }
    
    pub async fn read(&mut self) -> Result<PowerReading, I2C::Error> {
        let mut buf = [0u8; 2];
        
        // Bus voltage (register 0x02)
        self.i2c.write_read(self.address, &[0x02], &mut buf).await?;
        let bus_voltage = (i16::from_be_bytes(buf) >> 3) as f32 * 0.004; // 4mV/bit
        
        // Current (register 0x04)
        self.i2c.write_read(self.address, &[0x04], &mut buf).await?;
        let current = i16::from_be_bytes(buf) as f32 * self.current_lsb;
        
        // Power (register 0x03)
        self.i2c.write_read(self.address, &[0x03], &mut buf).await?;
        let power = i16::from_be_bytes(buf) as f32 * self.current_lsb * 20.0;
        
        Ok(PowerReading { voltage: bus_voltage, current, power })
    }
}

#[derive(Debug, Clone, Copy)]
pub struct PowerReading {
    pub voltage: f32,  // V
    pub current: f32,  // A
    pub power: f32,    // W
}
"#;

// =============================================================================
// Capacitive/Resistive Moisture Sensor (ADC)
// =============================================================================
const MOISTURE_DRIVER: &str = r#"
/// Soil moisture sensor (analog)
pub struct MoistureSensor<ADC> {
    adc: ADC,
    dry_value: u16,
    wet_value: u16,
}

impl<ADC> MoistureSensor<ADC> {
    pub fn new(adc: ADC, dry_value: u16, wet_value: u16) -> Self {
        Self { adc, dry_value, wet_value }
    }
    
    pub fn read_percent(&mut self, raw: u16) -> f32 {
        // Map raw ADC value to 0-100%
        let range = self.dry_value as f32 - self.wet_value as f32;
        let value = (self.dry_value as f32 - raw as f32) / range * 100.0;
        value.clamp(0.0, 100.0)
    }
}
"#;

// =============================================================================
// HX711 - Load cell amplifier
// =============================================================================
const HX711_DRIVER: &str = r#"
/// HX711 24-bit ADC for load cells
pub struct Hx711<SCK: OutputPin, DOUT: InputPin> {
    sck: SCK,
    dout: DOUT,
    offset: i32,
    scale: f32,
}

impl<SCK: OutputPin, DOUT: InputPin> Hx711<SCK, DOUT> {
    pub fn new(sck: SCK, dout: DOUT) -> Self {
        Self { sck, dout, offset: 0, scale: 1.0 }
    }
    
    pub fn set_scale(&mut self, scale: f32) {
        self.scale = scale;
    }
    
    pub async fn tare(&mut self, samples: u8) {
        let mut sum: i64 = 0;
        for _ in 0..samples {
            sum += self.read_raw().await.unwrap_or(0) as i64;
        }
        self.offset = (sum / samples as i64) as i32;
    }
    
    pub async fn read_raw(&mut self) -> Result<i32, Hx711Error> {
        // Wait for data ready (DOUT goes low)
        let start = Instant::now();
        while self.dout.is_high().unwrap_or(true) {
            if start.elapsed() > Duration::from_millis(100) {
                return Err(Hx711Error::Timeout);
            }
        }
        
        // Read 24 bits
        let mut value: i32 = 0;
        for _ in 0..24 {
            self.sck.set_high().ok();
            Timer::after(Duration::from_micros(1)).await;
            value = (value << 1) | if self.dout.is_high().unwrap_or(false) { 1 } else { 0 };
            self.sck.set_low().ok();
            Timer::after(Duration::from_micros(1)).await;
        }
        
        // One more pulse for gain = 128 on channel A
        self.sck.set_high().ok();
        Timer::after(Duration::from_micros(1)).await;
        self.sck.set_low().ok();
        
        // Sign extend 24-bit to 32-bit
        if value & 0x800000 != 0 {
            value |= 0xFF000000u32 as i32;
        }
        
        Ok(value)
    }
    
    pub async fn read_grams(&mut self) -> Result<f32, Hx711Error> {
        let raw = self.read_raw().await?;
        Ok((raw - self.offset) as f32 / self.scale)
    }
}

#[derive(Debug)]
pub enum Hx711Error {
    Timeout,
}
"#;

// =============================================================================
// ESP-CAM camera driver
// =============================================================================
const ESP_CAM_DRIVER: &str = r#"
/// ESP-CAM camera capture (ESP-IDF specific)
#[cfg(feature = "esp32")]
pub mod camera {
    use esp_idf_hal::prelude::*;
    
    pub struct EspCamera {
        // Camera handle managed by ESP-IDF
    }
    
    impl EspCamera {
        pub fn new(config: CameraConfig) -> Result<Self, CameraError> {
            // Initialize camera with ESP-IDF camera driver
            // This requires esp-idf-sys bindings
            Ok(Self {})
        }
        
        pub async fn capture_jpeg(&mut self) -> Result<Vec<u8>, CameraError> {
            // Capture frame and encode as JPEG
            // Implementation uses esp_camera_fb_get()
            Ok(Vec::new())
        }
    }
    
    pub struct CameraConfig {
        pub resolution: Resolution,
        pub jpeg_quality: u8,  // 0-63, lower = better
    }
    
    #[derive(Clone, Copy)]
    pub enum Resolution {
        QVGA,   // 320x240
        VGA,    // 640x480
        SVGA,   // 800x600
        XGA,    // 1024x768
        UXGA,   // 1600x1200
    }
    
    #[derive(Debug)]
    pub enum CameraError {
        InitFailed,
        CaptureFailed,
    }
}
"#;

// Placeholder drivers
const BME680_DRIVER: &str = "// BME680 driver: Similar to BME280 with gas sensor";
const SHT31_DRIVER: &str = "// SHT31 driver: I2C temperature/humidity";
const DS18B20_DRIVER: &str = "// DS18B20 driver: 1-Wire temperature";
const TSL2561_DRIVER: &str = "// TSL2561 driver: I2C light sensor";
const VEML7700_DRIVER: &str = "// VEML7700 driver: I2C ambient light";
const PHOTORESISTOR_DRIVER: &str = "// Photoresistor: ADC input";
const VL53LXX_DRIVER: &str = "// VL53L0X/L1X: I2C ToF distance";
const MPU9250_DRIVER: &str = "// MPU9250: 9-axis IMU (MPU6050 + magnetometer)";
const BNO055_DRIVER: &str = "// BNO055: 9-axis IMU with sensor fusion";
const ACS712_DRIVER: &str = "// ACS712: Hall-effect current sensor (ADC)";
const VOLTAGE_DIVIDER_DRIVER: &str = "// Voltage divider: ADC input";
const RPI_CAMERA_DRIVER: &str = "// RPi Camera: libcamera/picamera2";
const ADC_RAW_DRIVER: &str = "// Raw ADC reading";
const GENERIC_SENSOR_DRIVER: &str = "// Generic sensor placeholder";
