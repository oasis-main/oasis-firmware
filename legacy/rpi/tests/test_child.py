import sys
import time
import signal

def wrapped_sys_exit(*args):
    print("See ya!")
    sys.exit()

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, wrapped_sys_exit)
    print("Hello!")
    time.sleep(10)
    print("Goodbye!")
