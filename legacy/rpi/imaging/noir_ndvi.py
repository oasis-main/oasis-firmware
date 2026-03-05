
import cv2
import numpy as np
from imaging import fastiecm
#from picamera import PiCamera
#import picamera.array

'''
#No longer needed as we always call from the same camera now
def capture_stream(red,blue): #capture RGB stream from camera
    print("Capturing RGB array...")
    
    cam = PiCamera()
    #cam.rotation = 180
    #cam.resolution = (1920, 1080) # Uncomment if using a Pi Noir camera
    #cam.resolution = (2592, 1952) # Comment this line if using a Pi Noir camera
    stream = picamera.array.PiRGBArray(cam)
    cam.awb_gains = (red,blue)
    cam.capture(stream, format='bgr')
    original = stream.array
    stream.close()
    cam.close()

    return original
'''

#move color intensity 
def contrast_stretch(im):
    print("Stretching contrast...")
    
    in_min = np.percentile(im, 5)
    in_max = np.percentile(im, 95)

    out_min = 0.0
    out_max = 255.0

    out = im - in_min
    out *= ((out_min - out_max) / (in_min - in_max))
    out += in_min

    return out

#calculate NDVI
def calc_ndvi(image):
    print("Calculating NDVI...")
    b, g, r = cv2.split(image)
    bottom = r.astype(float) + b.astype(float)
    np.seterr(divide='ignore', invalid='ignore')  # Ignore division by zero warning
    ndvi = np.divide(np.subtract(r, b), bottom, out=np.zeros_like(bottom), where=bottom!=0)
    return ndvi

#take the raw file from 
def convert_image(image_path):
    #create and configure camera object 
    original = cv2.imread('/home/pi/oasis-rpi/data_out/image.jpg') #save contrasted image
    contrasted = contrast_stretch(original) #apply contrast to the image
    cv2.imwrite('/home/pi/oasis-rpi/data_out/contrasted.jpg', contrasted) #save contrasted image

    ndvi = calc_ndvi(cv2.imread('/home/pi/oasis-rpi/data_out/contrasted.jpg')) #calculate image ndvi
    ndvi_contrasted = contrast_stretch(ndvi) #apply stretch the contrast a second time
    cv2.imwrite('/home/pi/oasis-rpi/data_out/ndvi_pre_cm.jpg', ndvi_contrasted) #save ndvi image

    print("Applying color map...")
    color_map_prep = cv2.imread('/home/pi/oasis-rpi/data_out/ndvi_pre_cm.jpg').astype(np.uint8) #prep colour mapping
    color_mapped_image = cv2.applyColorMap(color_map_prep, fastiecm.fastiecm) #apply colour mapping
    cv2.imwrite(image_path, color_mapped_image) #save cm'd image

    print("NDVI & Intermediary images saved to disk.")

if __name__ == '__main__':
    print("No main program here. Sorry! Look at the file to see importable functions.")


