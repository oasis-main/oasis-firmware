import time
import rusty_pipes

if __name__ == '__main__':
    '''
    print("Testing subprocess launcher...")
    test1 = rusty_pipes.Open(["python3", "test_child.py"],"test")
    test1.wait()
    print("test1: This should come after 'Goodbye!'")
    '''

    '''
    print("Testing wait for child exit w/ timeout...")
    test2 = rusty_pipes.Open(["python3", "test_child.py"],"test")
    test2.wait_timeout(2)
    print("test2: This should come after 'Hello!'")
    '''

    '''
    print("Testing wait for child exit...")
    test3 = rusty_pipes.Open(["python3", "test_child.py"],"test")
    print(test3.exited()) # should be false 
    test3.wait()
    print(test3.exited()) # should be true
    print("test3: This should come after 'True'")
    '''

    print(" ")
    print("Testing termination signal & catching...")
    test4 = rusty_pipes.Open(["python3", "test_child.py"],"test")
    time.sleep(1)
    print(test4.exited()) # should be false 
    #test4.terminate() #cannot terminate because does not handle signal
    test4.wait()
    print(test4.exited()) # should be true
    print("test4: This should come after 'True'")
    print("There should not be a 'Goodbye!'")
    
    
    