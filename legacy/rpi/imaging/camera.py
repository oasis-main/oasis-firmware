#---------------------------------------------------------------------------------------
#Manages Camera Timing & Image transmission
#---------------------------------------------------------------------------------------
import sys
import signal

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

#import libraries
import time
from imaging import noir_ndvi

import rusty_pipes
from utils import concurrent_state as cs
from utils import error_handler as err
from networking import db_tools as dbt

resource_name = "camera"

def take_picture(image_path):
    if cs.structs["hardware_config"]["camera_settings"]["awb_mode"] == "on":
        #take picture and save to standard location: libcamera-still -e png -o test.png
        still = rusty_pipes.Open(["raspistill", "-e", "jpg",  "-o", str(image_path)],"raspistill") #snap: call the camera. "-w", "1920", "-h", "1080",
        still.wait()
    else:
        still = rusty_pipes.Open(["raspistill", "-e", "jpg",  "-o", str(image_path), "-awb", "off", "-awbg", cs.structs["hardware_config"]["camera_settings"]["awb_red"] + "," + cs.structs["hardware_config"]["camera_settings"]["awb_blue"]],"raspistill") #snap: call the camera. "-w", "1920", "-h", "1080",
        still.wait()
    
    exit_status = still.exit_code()
    return exit_status

def take_video(video_path, duration):
    """
    Captures a video using the Raspberry Pi camera.
    
    Args:
    - video_path (str): Path to save the captured video.
    - duration (int): Length of the video capture in seconds.
    
    Returns:
    - int: Exit status of the raspivid command.
    """
    # Convert duration from seconds to milliseconds
    duration_millis = duration * 1000
    
    if cs.structs["hardware_config"]["camera_settings"]["awb_mode"] == "on":
        # Take video and save to specified path
        video_cmd = ["raspivid", "-e", "h264", "-o", str(video_path), "-t", str(duration_millis)]
        video_process = rusty_pipes.Open(video_cmd, "raspivid")
        video_process.wait()
    else:
        awb_values = "{},{}".format(cs.structs["hardware_config"]["camera_settings"]["awb_red"], 
                                    cs.structs["hardware_config"]["camera_settings"]["awb_blue"])
        video_cmd = ["raspivid", "-e", "h264", "-o", str(video_path), "-t", str(duration_millis), 
                     "-awb", "off", "-awbg", awb_values]
        video_process = rusty_pipes.Open(video_cmd, "raspivid")
        video_process.wait()
    
    exit_status = video_process.exit_code()
    return exit_status

def save_to_feed(image_path):
    #timestamp image
    timestamp = time.time()
    #move timestamped image into feed
    save_most_recent = rusty_pipes.Open(["cp", str(image_path), "/home/pi/oasis-rpi/data_out/image_feed/image_at_" + str(timestamp)+'.jpg'],"cp")
    save_most_recent.wait()

def send_image(path, image_filename):
    #send new image to firebase
    
    user, db, storage = dbt.initialize_user(cs.structs["access_config"]["refresh_token"])
    dbt.store_file(user, storage, path, cs.structs["access_config"]["device_name"], image_filename)
    print("Sent image")

    #tell firebase that there is a new image
    dbt.patch_firebase(cs.structs["access_config"], "image_sent", "1")
    print("Firebase has an image in waiting")

#define a function to actuate element
def actuate(interval: int, nosleep = False): #interval is amount of time between shots in minutes, nosleep skips the wait

    exit_status = take_picture('/home/pi/oasis-rpi/data_out/image.jpg')
    
    if exit_status == 0:

        #Load, resize, and save image:
        image = noir_ndvi.cv2.imread('/home/pi/oasis-rpi/data_out/image.jpg')
        height, width = image.shape[:2]
        print("Original Height:" + str(height))
        print("Original Width:" + str(width))
        
        max_dimension = 2500
        existing_aspect_ratio = int(width) / int(height)

        if width > height:
            new_width = max_dimension
            new_height = int(new_width / existing_aspect_ratio)
        else:
            new_height = max_dimension
            new_width = int(new_height * existing_aspect_ratio)

        print("New Height:" + str(new_height))
        print("New Width:" + str(new_width))
        resized_image = noir_ndvi.cv2.resize(image, (new_width, new_height), interpolation=noir_ndvi.cv2.INTER_AREA)
        noir_ndvi.cv2.imwrite('/home/pi/oasis-rpi/data_out/image.jpg' ,resized_image)

        #Get NDVI if active
        if cs.structs["feature_toggles"]["ndvi"] == "1":
            noir_ndvi.convert_image('/home/pi/oasis-rpi/data_out/image.jpg')

        #Save to feed if active
        if cs.structs["feature_toggles"]["save_images"] == "1":
            save_to_feed('/home/pi/oasis-rpi/data_out/image.jpg')

        #Sent to cloud if connected
        if cs.structs["device_state"]["connected"] == "1":
            #send new image to firebase
            send_image('/home/pi/oasis-rpi/data_out/image.jpg', image_filename="image.jpg")

        if nosleep == True:
            return
        else:
            time.sleep(interval*60) #once the physical resource itself is done being used, we can free it
                                        #not a big deal if someone actuates again while the main spawn is waiting
                                        #so long as they aren't doing so with malicious intent (would need DB or root access, make sure to turn off SSH or change your password)
    else:
        print("Was not able to take picture!")
        time.sleep(5)

if __name__ == '__main__':
    cs.check_lock(resource_name) #no hardware acquisition happens on import
    signal.signal(signal.SIGTERM, cs.wrapped_sys_exit) #so we can check for the lock in __main__
    try:    
        while True:
            cs.load_state()
            if (time.time() - float(cs.structs["hardware_config"]["camera_settings"]["last_picture_time"])) > (float(cs.structs["hardware_config"]["camera_settings"]["picture_frequency"])*60): #convert setting (minutes) to base units (seconds)
                cs.write_nested_state("/home/pi/oasis-rpi/configs/hardware_config.json", "camera_settings" ,"last_picture_time", str(time.time()), db_writer = dbt.patch_firebase) #we MUST ALWAYS write before sleeping, otherwise the program will double-count the wait period!
                actuate(int(cs.structs["hardware_config"]["camera_settings"]["picture_frequency"]))
            else:
                time.sleep(1)
    except SystemExit:
        print("Camera was terminated.")
    except KeyboardInterrupt:
        print("Camera was interrupted.")
    except TypeError:
        print("Tried do image stuff without an image. Is your camera properly set up?")
        print(err.full_stack())
        time.sleep(10)
    except Exception:
        print("Camera encountered an error!")
        print(err.full_stack())
    finally:
        print("Shutting down camera...")
        cs.rusty_pipes.unlock(cs.lock_filepath, resource_name)

        


