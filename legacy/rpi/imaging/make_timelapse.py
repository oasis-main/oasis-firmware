#Needs updating
#Make callable as python module
#Make sure cv2 is available
#Incorporate data export script

#imports
import os
import os.path
import sys

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')
sys.path.append('/home/pi/oasis-rpi/utils')

#main dependency
import cv2

#sending to cloud
from networking import db_tools as dbt
from utils import concurrent_state as cs

def tl_make(image_folder):

	#name of output timelapse
	#.avi = audio visual imput, not being conceited this time ;)
	video_name = "/home/pi/oasis-rpi/data_out/timelapse.avi"

	#loops throught the directory to get file names
	images = [img for img in os.listdir(image_folder) if img.endswith(".jpg")]
	##^^ THIS IS WHAT YOU WILL NEED TO MAKE SURE IS IN THE CORRECT ORDER
	##YOU CAN GET THIS LIST THEN SORT IT HOW YOU WANT THEN PROCESS AFTER
	##YOULL NOTICE WHEN FIRST RUN IT THAT THE ORDER IS OFF

	d = {}

	for i in images:
		num = i[13:-4]
		d[i] = float(num)

	sorted_dic = {k: v for k, v in sorted(d.items(), key=lambda item: item[1])}
	sorted_list = list(sorted_dic.keys())

	#getting info for formatting the images for timelapse
	frame = cv2.imread(os.path.join(image_folder, images[0]))
	height, width, layers = frame.shape

	#https://www.geeksforgeeks.org/saving-a-video-using-opencv/
	#Syntax: cv.VideoWriter(filename, fourcc, fps, frameSize)
	#Parameters:
	#	filename: Input video file
	#	fourcc: 4-character code of codec used to compress the frames
	#	fps: framerate of videostream
	#	framesize: Height and width of frame
	video = cv2.VideoWriter(video_name,cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'), 30, (width,height))

	#making the timelapse
	for image in sorted_list:
		#this shows you the order that images are getting
		#saved into the timelape
		print(image)
		#gets image data
		frame = cv2.imread(os.path.join(image_folder, image))
		#saves to video file
		video.write(frame)

	#closes everything out correctly
	cv2.destroyAllWindows()
	video.release()
	#reset_model.reset_image_feed()

def send_timelapse(path):
    #send new image to firebase
	user, db, storage = dbt.initialize_user(cs.structs["access_config"]["refresh_token"])
	dbt.store_file(user, storage, path, cs.structs["access_config"]["device_name"], "timelapse.avi")
	print("Sent timelapse")

	#tell firebase that there is a new timelapse
	dbt.patch_firebase(cs.structs["access_config"], "video_sent","1")
	print("Firebase has a timelapse in waiting")

if __name__ == '__main__':
	
	cs.load_state()

	#dir where images are stored
	image_folder = '/home/pi/oasis-rpi/data_out/image_feed'

	#make timelapses
	tl_make(image_folder)

	#send new timelapse to firebase
	send_timelapse("/home/pi/oasis-rpi/data_out/timelapse.avi")