//Other people's hard work
use pyo3::prelude::*;
use rppal::gpio::*;

use rppal::gpio::OutputPin;
use rppal::gpio::InputPin;

use std::collections::{VecDeque, HashMap};

// A safe, Python-ready GPIO output class that operates on the hardware level
#[pyclass(unsendable)]
struct GpioOut{output: OutputPin}

#[pyclass(unsendable)]
struct GpioIn {input: InputPin,
               debouncing_count: u8,
               last_inputs: VecDeque,
               mode_count: HashMap,
}

// Behavior of the GPIO output class
#[pymethods]
impl GpioOut { 
    #[new] // call this from python with rusty_pins.GpioOut(pin#)
    fn new(pin: u8) -> Self { //this is like python __init__()
        let io_pin = Gpio::new().unwrap().get(pin).unwrap().into_output();
        GpioOut{output: io_pin}
    }
    
    fn set_high(&mut self){
        self.output.set_high();
    }

    fn set_low(&mut self){
        self.output.set_low();
    }

    fn is_high(&mut self){
        self.output.is_set_high();
    }

    fn is_low(&mut self){
        self.output.is_set_low();
    }
}

#[pymethods]
impl GpioIn {
    #[new]
    fn new(pin: u8, debouncing_count: u8) -> Self {
        let io_pin = Gpio::new().unwrap().get(pin).unwrap().into_input_pullup();
        GpioIn {
            input: io_pin,
            debouncing_count,
            last_inputs: VecDeque::with_capacity(debouncing_count),
            mode_count: HashMap::new(),
        }
    }

    fn read(&mut self) {
        let value = self.input.is_high();  // assuming `is_high()` returns a boolean
        self.last_inputs.push_back(value);
        if self.last_inputs.len() > self.debouncing_count {
            if let Some(val) = self.last_inputs.pop_front() {
                let count = self.mode_count.entry(val).or_insert(0);
                *count -= 1;
            }
        }
        let count = self.mode_count.entry(value).or_insert(0);
        *count += 1;
    }

    fn get_mode(&self) -> Option<bool> {
        self.mode_count.iter().max_by_key(|&(_, count)| count).map(|(&val, _)| val)
    }

    fn is_high(&mut self) -> bool {
        self.get_mode().unwrap_or(false)
    }

    fn is_low(&mut self) -> bool {
        !self.is_high()
    }
}

// A Python-ready GPIO I/O module
#[pymodule]
fn rusty_pins(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_class::<GpioOut>()?;
    m.add_class::<GpioIn>()?;
    Ok(())
}
