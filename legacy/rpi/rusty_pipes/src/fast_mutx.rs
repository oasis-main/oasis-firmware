use pyo3::prelude::*;
use serde_json::*;
use std::time::Duration;
use std::thread;
use subprocess::{Popen,PopenConfig};

//Rust implementation of Lamport's fast mutual exclusion agorithm for system-level resources
//
//Citation:
//  "A Fast Mutual Exclusion Algorithm" - Leslie Lamport 1986, ACM Transactions on Computer Systems 1987, (C) Digital Equipment Corporation 1988 

//"...The best possible algorithm is one in which Si consists of the sequence write x, read y, write y, read x—a sequence that is abbreviated as w-x, r-y, w-y, r-x. 
// Let us assume that S is a series of i/o ops of this form with length i+1 
//  Thus each process first writes x (S0), then reads y (S1)., 
//  If it finds that y has its initial value, then it writes y (S2) and reads x (S3). 
//  If it finds that x has the value it wrote in its first operation, then it passes to allow execution of the critical section...

// After executing its critical section, a process must execute at least one write operation to indicate that the critical section is vacant and there is no contention. 
// The process cannot do this with a write of x, since every process writes x as the first access to shared memory when performing the protocol. 
//  Therefore, a process must write y (S4), resetting y to its initial value, after exiting the critical section..."

//In other words:
// w-x, r-y, w-y, r-x, critical section, w-y.

//Pesudocode:
//  start: ⟨x := i⟩;
//      if ⟨y ̸= 0⟩ then goto start fi; 
//          ⟨y := i⟩;
//      if ⟨x ̸= i⟩ then delay;
//          if ⟨y ̸= i⟩ then goto start fi fi;
//      critical section; 
//      ⟨y := 0⟩;

//The delay in the second then clause must be long enough so that, 
//if another process j read y equal to zero in the first if statement before i set y equal to i, 
//then j will either enter the second then clause or else execute the critical section and reset y to zero before i finishes executing the delay statement. 
//  (This delay is allowed because it is executed only if there is contention.)

/// Lock
/// --
///
/// Obtain lock for a resource
#[pyfunction]
pub fn lock(lock_filepath: String, resource_key: String, loop_limit: Option<u64>) { 
    //loop(
    //S0: loop(load shared memory object, continue if fail), write x = x+1, copy x, continue if fail else proceed
    
    //S1: loop)load shared memory object, continue if fail), read y, proceed if y==0 else continue 

    //S2: loop(load shared memory object, continue if fail), write y = y+1, copy y, continue if fail else proceed

    //S3: loop(load shared memory object, continue if fail), read x, proceed if x == x_copy else delay ... loop(load_shared memory object, continue if fail), break if y==y_copy else continue) 
    //    )
    
    let limit = if let Some(i) = loop_limit {i} else {1000};

    let x_suffix = "_x";
    let y_suffix = "_y";

    let resource_lock_x = format!("{}{}", resource_key, x_suffix);
    let resource_lock_y = format!("{}{}", resource_key, y_suffix);

    //debugging
    //println!("{}", &resource_lock_x);
    //println!("{}", &resource_lock_x);

    'outer: for x in 0..limit+1{ //start attempting to load & write the lock  
        
        if x < limit {

            //S0:
            ////////////////////////////////////////////////////////////////////////////////////////////
            
            let mut x_write: i64 = 0; //make these to copy the initial write values
            let mut y_write: i64 = 0; //these are referenced to check for contentions
            
            for x in 0..limit+1{
                if x < limit {
                    //load the lock file into json
                    let lock_obj = {
                        // Load the first file into a string.
                        let text = std::fs::read_to_string(&lock_filepath);
                        //load shared memory object, continue if fail
                        match text {
                            Ok(json) => {// Parse the string into a dynamically-typed JSON structure.
                                serde_json::from_str::<Value>(&json)},
                            Err(_) => {thread::sleep(Duration::from_millis(100));
                                        continue;}
                        }
                    };

                    match lock_obj {
                        Ok(mut locks) => {//lock this resource in the JSON structure
                            //update the json value...
                            locks[&resource_lock_x] =  Value::Number(Number::from(locks[&resource_lock_x].as_i64().unwrap() + 1));
                            //write the new data back to the json file...
                            match std::fs::write(&lock_filepath, serde_json::to_string_pretty(&locks).unwrap()) {
                                Ok(()) => {
                                    x_write = locks[&resource_lock_x].as_i64().unwrap();
                                    break
                                },
                                Err(_) => {thread::sleep(Duration::from_millis(100));
                                            continue;}
                            }
                        },
                        Err(_) => {
                            thread::sleep(Duration::from_millis(100));
                            continue;
                        }
                    }
                } else {
                    println!("Error in fast mutex Stage 0");
                    thread::sleep(Duration::from_millis(250));
                    return
                }    
            }
            
            //S1:
            ////////////////////////////////////////////////////////////////////////////////////////////
            
            for x in 0..limit+1{
                if x < limit {
                
                    //load the lock file into json
                    let lock_obj = {
                        // Load the first file into a string.
                        let text = std::fs::read_to_string(&lock_filepath);
                        //load shared memory object, continue if fail
                        match text {
                            Ok(json) => {// Parse the string into a dynamically-typed JSON structure.
                                serde_json::from_str::<Value>(&json)},
                            Err(_) => {thread::sleep(Duration::from_millis(100));
                                        continue;}
                        }
                    };

                    match lock_obj {
                        Ok(locks) => {//lock this resource in the JSON structure
                            
                            //check to see if the json value is 0, ...
                            if locks[&resource_lock_y].as_i64().unwrap() == 0 {break} else {continue 'outer};
                        },
                        Err(_) => {
                            thread::sleep(Duration::from_millis(100));
                            continue;
                        }
                    }
                } else {
                    println!("Error in fast mutex Stage 1");
                    thread::sleep(Duration::from_millis(250));
                    return
                }
            }
        
            //S2:
            ////////////////////////////////////////////////////////////////////////////////////////////
            for x in 0..limit+1{
                if x < limit {
                
                    //load the lock file into json
                    let lock_obj = {
                        // Load the first file into a string.
                        let text = std::fs::read_to_string(&lock_filepath);
                        //load shared memory object, continue if fail
                        match text {
                            Ok(json) => {// Parse the string into a dynamically-typed JSON structure.
                                serde_json::from_str::<Value>(&json)},
                            Err(_) => {thread::sleep(Duration::from_millis(100));
                                        continue;}
                        }
                    };

                    match lock_obj {
                        Ok(mut locks) => {//lock this resource in the JSON structure
                            //update the json value...
                            locks[&resource_lock_y] =  Value::Number(Number::from(locks[&resource_lock_y].as_i64().unwrap() + 1));
                            //write the new data back to the json file...
                            match std::fs::write(&lock_filepath, serde_json::to_string_pretty(&locks).unwrap()) {
                                Ok(()) => {
                                    y_write = locks[&resource_lock_y].as_i64().unwrap();
                                    break
                                },
                                Err(_) => {thread::sleep(Duration::from_millis(100));
                                            continue;}
                            }
                        },
                        Err(_) => {thread::sleep(Duration::from_millis(100));
                                    continue;}
                    }

                } else {
                    println!("Error in fast mutex Stage 2");
                    thread::sleep(Duration::from_millis(250)); 
                    return
                }
            }

            //S3:
            ////////////////////////////////////////////////////////////////////////////////////////////
            for x in 0..limit+1{
                if x < limit {
                    //load the lock file into json
                    let lock_obj = {
                        // Load the first file into a string.
                        let text = std::fs::read_to_string(&lock_filepath);
                        //load shared memory object, continue if fail
                        match text {
                            Ok(json) => {// Parse the string into a dynamically-typed JSON structure.
                                serde_json::from_str::<Value>(&json)},
                            Err(_) => {thread::sleep(Duration::from_millis(100));
                                        continue;}
                        }
                    };

                    match lock_obj {
                        Ok(locks) => {//lock this resource in the JSON structure
                            
                            //check to see if the json value is 0, ...
                            if locks[&resource_lock_x].as_i64().unwrap() == x_write { //If no other process has written x
                                break 'outer //proceed, allow the function to return 
                            } else {
                                thread::sleep(Duration::from_millis(2000)); //ALGORITHM MAIN DELAY: Now wait just a gosh darn second!
                                
                                for x in 0..limit+1{
                                    if x < limit {
                                        //load the lock file into json
                                        let lock_obj = {
                                            // Load the first file into a string.
                                            let text = std::fs::read_to_string(&lock_filepath);
                                            //load shared memory object, continue if fail
                                            match text {
                                                Ok(json) => {// Parse the string into a dynamically-typed JSON structure.
                                                    serde_json::from_str::<Value>(&json)},
                                                Err(_) => {thread::sleep(Duration::from_millis(100));
                                                            continue;}
                                            }
                                        };
                            
                                        match lock_obj {
                                            Ok(locks) => {//lock this resource in the JSON structure
                                                
                                                //check to see if the json value is 0, ...
                                                if locks[&resource_lock_y].as_i64().unwrap() == y_write {break 'outer} else {continue 'outer};
                                            },
                                            Err(_) => {
                                                thread::sleep(Duration::from_millis(100));
                                                continue;
                                            }
                                        }
                                    } else {
                                        println!("Error in fast mutex Stage 3B");
                                        thread::sleep(Duration::from_millis(250)); 
                                    }
                                }
                            };
                        },
                        Err(_) => {
                            thread::sleep(Duration::from_millis(100));
                            continue;
                        }
                    }
                } else {
                    println!("Error in fast mutex Stage 4");
                    thread::sleep(Duration::from_millis(250)); 
                    return
                }
            }   

        } else {
            println!("Loop limit expired: lock(). Was not able to acquire {}.", &resource_key);
            let default_filepath = String::from("/home/pi/oasis-rpi/defaults/locks_default_template.json");
            reset_locks(lock_filepath,default_filepath);
            return
        }

        thread::sleep(Duration::from_millis(500)); //delay before the next iteration to give us some breathing room. rust loops fast

    }
    return
}

/// Unlock
/// --
///
/// Obtain lock for a resource, should fail if lock is not held
#[pyfunction]
pub fn unlock(lock_filepath: String, resource_key: String, loop_limit: Option<u64>) { //equivalent to reset_lock (singular)
    //loop(
    //    S4: loop(load shared memory object, continue if fail), write y = 0, continue if fail, else break
    //    )

    let limit = if let Some(i) = loop_limit {i} else {1000};
    let y_suffix = "_y";
    let resource_lock_y = format!("{}{}", &resource_key, &y_suffix);

    for x in 0..limit+1{ //start attempting to load & write the lock
        if x < limit {
            //load the lock file into json
            let lock_obj = {
                // Load the first file into a string.
                let text = std::fs::read_to_string(&lock_filepath);

                match text {
                    Ok(json) => { // If read to string successful
                        serde_json::from_str::<Value>(&json) // Try parse string into JSON & return result.
                    },
                    Err(_) => {thread::sleep(Duration::from_millis(100));
                                continue;} // If read failed, continue to next iteration
                }
            };
            
            match lock_obj { //examine the parse attempt
                
                Ok(mut locks) => {
                    locks[&resource_lock_y] = Value::Number(Number::from(0)); // Lock this resource in the JSON structure
                
                    match serde_json::to_string_pretty(&locks){   
                        Ok(json) => {
                            match std::fs::write(&lock_filepath, json) {
                                Ok(()) => return, //If write successful, break the loop
                                Err(_) => {thread::sleep(Duration::from_millis(100));
                                            continue;} // Otherwise, try the next iteration
                            }
                        }

                        Err(_) => {thread::sleep(Duration::from_millis(100));
                                    continue;} 
                    }
                },
                
                Err(_) => {thread::sleep(Duration::from_millis(100));
                            continue; // If parse failed, continue to next iteration
                }
            }
            
        } else {
            println!("Loop limit expired: unlock(). Was not able to free {}", &resource_key);
            let default_filepath = String::from("/home/pi/oasis-rpi/defaults/locks_default_template.json");
            reset_locks(lock_filepath,default_filepath);
            return
        }

    }
    return
}

/// reset_locks
/// --
///
/// Reset all locks:  This fails because the reset cannot load a valid json (too safe, go figure...)
#[pyfunction]
pub fn reset_locks(lock_filepath: String, default_filepath: String) {
    let cp = String::from("cp");
    let arg_list= vec!(&cp, &default_filepath, &lock_filepath);
    let mut sub_proc = Popen::create(&arg_list[..], PopenConfig::default()).unwrap();
    sub_proc.detach();

}
/// create_lock
/// --
///
/// Obtain lock for a resource
#[pyfunction]
pub fn create_lock(lock_filepath: String, resource_key: String) {
    let file_exists = std::path::Path::new(&lock_filepath).exists();

    let x_suffix = "_x";
    let y_suffix = "_y";
    let resource_lock_x = format!("{}{}", &resource_key, &x_suffix);
    let resource_lock_y = format!("{}{}", &resource_key, &y_suffix);


    if file_exists { //load file, append, write
        
        //load the lock file into json
        let lock_obj = {
            // Load the first file into a string.
            let text = std::fs::read_to_string(&lock_filepath);

            match text {
                Ok(json) => {// Parse the string into a dynamically-typed JSON structure.
                    serde_json::from_str::<Value>(&json)},
                Err(_) => {
                    panic!();
                }
            }
        };
    
        match lock_obj {
            Ok(mut locks) => {//lock this resource in the JSON structure
                
                //write the new data back to the json struct
                locks[&resource_lock_x] = Value::Number(Number::from(0));
                locks[&resource_lock_y] = Value::Number(Number::from(0));
            
                // Save the JSON structure into the other file.
                match std::fs::write(&lock_filepath, serde_json::to_string_pretty(&locks).unwrap()) {
                    Ok(()) => println!("New lock-set created successfully for {}", resource_key),
                    Err(_) => {println!("Error writing new locks to json file!");}
                }
            },
            
            Err(_) => {
                println!("Error parsing lockfile from text to json!");
            }
        }

    } else { //create file, append, write
        let file = std::fs::File::create(&lock_filepath);
        
        match file {
            Ok(_file) => {println!("New lock-file created!")
            
            },
            Err(_) => {println!("Failed to create new file.")}
        };

        //https://stackoverflow.com/questions/67846025/rust-json-how-to-convert-str-to-json-response-in-rust
        let locks = serde_json::json!({
            resource_lock_x: Number::from(0),
            resource_lock_y: Number::from(0) 
        });
        
        match std::fs::write(&lock_filepath, serde_json::to_string_pretty(&locks).unwrap()) {
            Ok(()) => println!("New lock-set created for {}", &resource_key),
            Err(_) => println!("Failed to create new lock-set for {}", &resource_key)
        };
    }
}