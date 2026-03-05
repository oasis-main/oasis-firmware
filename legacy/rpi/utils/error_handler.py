import traceback, sys

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

def full_stack():
    exc = sys.exc_info()[0]
    stack = traceback.extract_stack()[:-1]  # last one would be full_stack()
    if exc is not None:  # i.e. an exception is present
        del stack[-1]       # remove call of full_stack, the printed exception
                            # will contain the caught exception caller instead
    trc = 'Traceback (most recent call last):\n'
    stackstr = trc + ''.join(traceback.format_list(stack))
    if exc is not None:
         stackstr += '  ' + traceback.format_exc().lstrip(trc)
    return stackstr

#Decorator: https://www.geeksforgeeks.org/error-handling-in-python-using-decorators/
def Error_Handler(func):
    def Inner_Function(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except KeyboardInterrupt as k:
            print("Keyboard Interrupt") #Shame! Replace the following with a propper error logger
            #cs.write_state("/home/pi/oasis-rpi/configs/device_state.json", "device_error", "Interrupted", db_writer = None)
        
        except TypeError as t:
            print(f"{func.__name__} wrong data types.")
            print(full_stack()) #Shame! Replace the following with a propper error logger
            #cs.write_state("/home/pi/oasis-rpi/configs/device_state.json", "device_error", str(full_stack()), db_writer = None)
            #cs.write_state("/home/pi/oasis-rpi/configs/device_state.json", "led_status", "error", db_writer = None)
        
        except Exception as e:
            print(full_stack()) #Shame! Replace the following with a propper error loggers
            #cs.write_state("/home/pi/oasis-rpi/configs/device_state.json", "device_error", str(full_stack()), db_writer = None)
            #cs.write_state("/home/pi/oasis-rpi/configs/device_state.json", "led_status", "error", db_writer = None)
    
    return Inner_Function

