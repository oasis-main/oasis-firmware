use std::time::Duration;
use pyo3::prelude::*;
use serde_json::{Value};
use subprocess::{Popen,PopenConfig,ExitStatus};

pub mod fast_mutx;                                                                                        

// A safe, Python-ready subprocess class for spawning & managing unix children
#[pyclass(unsendable)]
struct Open{process: Popen, name: String}

#[pyfunction]
fn custom_signal(sig_filepath: String, id: String , signal: &str){
    let mut sig_obj = {
        // Load the first file into a string.
        let text = std::fs::read_to_string(&sig_filepath).unwrap();

        // Parse the string into a dynamically-typed JSON structure.
        serde_json::from_str::<Value>(&text).unwrap()
    };

    //lock this resource in the JSON structure
    sig_obj[id] = Value::String(String::from(signal));

    //write the new data back to the json file
    // Save the JSON structure into the other file.
    std::fs::write(
        sig_filepath,
        serde_json::to_string_pretty(&sig_obj).unwrap(),
    ).unwrap();
}

// Behavior of the subprocess class
#[pymethods]
impl Open { 
    #[new] 
    fn new(arg_list: Vec<String>, proc_name: String) -> Self { //this is like python __init__()
        let mut sub_proc = Popen::create(&arg_list[..], PopenConfig::default()).unwrap();
        sub_proc.detach();
        Open{process: sub_proc, name: proc_name}
    }
    
    fn wait(&mut self){ //don't do whatever's next until the child has exited
        self.process.wait().unwrap();
    }

    fn wait_timeout(&mut self, secs: u64){ //moves on after some time
        let seconds = Duration::new(secs, 0); //but DOES NOT KILL the child proc
        self.process.wait_timeout(seconds).unwrap();
    }

    fn exited(&mut self) -> bool{ //has it exited?
        let value = self.process.poll();
        if let Some(_exit_status) = value {
            true //yes -> return true
        } else {
            false //no -> return false
        }
    }

    fn exit_code(&mut self) -> u32{
        let value = self.process.exit_status();
        if let Some(ExitStatus::Exited(exit_status)) = value {
            exit_status //return the exit status
        } else {
            1000 //obviously a failure lol
        }  
    }

    fn terminate(&mut self, sig_filepath: Option<String>){ //not handled with OS signals now, we are going to set the signal manually
        match sig_filepath {
        None => self.process.terminate().unwrap(),
        Some(signal_filepath) =>  custom_signal(signal_filepath,String::from(&self.name), "terminated"), 
        }
    }
}

// A Python-ready subprocess managment module
#[pymodule]
fn rusty_pipes(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    
    // MULTI-PROCESSING
    m.add_class::<Open>()?;
    m.add_function(wrap_pyfunction!(custom_signal, m)?)?;
    
    //MUTUAL EXCLUSION
    m.add_function(wrap_pyfunction!(fast_mutx::lock, m)?)?;
    m.add_function(wrap_pyfunction!(fast_mutx::unlock, m)?)?;
    m.add_function(wrap_pyfunction!(fast_mutx::reset_locks, m)?)?;
    m.add_function(wrap_pyfunction!(fast_mutx::create_lock, m)?)?; 
    Ok(())
}