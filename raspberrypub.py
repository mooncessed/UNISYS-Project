import RPi.GPIO as IO
import time
import picamera
from time import sleep
import cv2 
import matplotlib.pyplot as plt
import numpy as np
import math
import paho.mqtt.client as mqtt
import os
import datetime
import sqlite3

def employeelog(id, name, intime, outtime, G1, G2, G3):
    
        sqliteConnection = sqlite3.connect('test.db')
        cursor = sqliteConnection.cursor()
        print("Connected to SQLite")

        sqlite_create_table_query = '''CREATE TABLE mytab1 (
                                       id INTEGER PRIMARY KEY,
                                       name TEXT NOT NULL,
                                       intime timestamp,
                                       outtime timestamp,
                                       G1 BOOL NOT NULL,
                                       G2 BOOL NOT NULL,
                                       G3 BOOL NOT NULL);'''
        sqliteConnection = sqlite3.connect('test.db')
        cursor = sqliteConnection.cursor()
        cursor.execute(sqlite_create_table_query)

        # insert developer detail
        sqlite_insert_with_param = """INSERT INTO 'mytab1'
                          ('id', 'name', 'intime', 'outtime','G1', 'G2', 'G3') 
                          VALUES (?, ?, ?, ?, ?, ?, ?);"""

        data_tuple = (id, name, intime, outtime,G1, G2, G3)
        cursor.execute(sqlite_insert_with_param, data_tuple)
        sqliteConnection.commit()
        print("Developer added successfully \n")

        # get developer detail
        sqlite_select_query = """SELECT name, intime, outtime, G1, G2, G3 from mytab1 where id = ?"""
        cursor.execute(sqlite_select_query, (1,))
        records = cursor.fetchall()

        for row in records:
            developer = row[0]
            joining_Date = row[1]
            print(developer, " joined on", intime)
            print("joining date type is", type(joining_Date))

        cursor.close()

   
        if sqliteConnection:
            sqliteConnection.close()
            print("sqlite connection is closed")

employeelog(1, 'Mark', datetime.datetime.now(),datetime.datetime.now(),1,1,1)

ledpin = 12
IO.setwarnings(False)
IO.setmode(IO.BCM)
IO.setup(22,IO.IN) #GPIO 14 for IR sensor input
IO.setup(12,IO.OUT) # led pin(for led controls)
camera = picamera.PiCamera() 




while(1):
    if(IO.setup(22,IO.IN) == False): # Person comes near the gate -> sensor input high
        camera.start_preview()
        sleep(5)
        camera.capture('/home/pi/Desktop/picture/imag.jpg') #camera module takes picture and saves it to memory
        camera.stop_preview()     



class Hog_descriptor():
    def __init__(self, img, cell_size=16, bin_size=8):
        self.img = img
        self.img = np.sqrt(img / float(np.max(img)))
        self.img = self.img * 255
        self.cell_size = cell_size
        self.bin_size = bin_size
        self.angle_unit = 360 / self.bin_size
        assert type(self.bin_size) == int, "bin_size should be integer,"
        assert type(self.cell_size) == int, "cell_size should be integer,"

    def extract(self):
        height, width = self.img.shape
        gradient_magnitude, gradient_angle = self.global_gradient()
        gradient_magnitude = abs(gradient_magnitude)
        cell_gradient_vector = np.zeros((int(height / self.cell_size), int(width / self.cell_size), self.bin_size))
        for i in range(cell_gradient_vector.shape[0]):
            for j in range(cell_gradient_vector.shape[1]):
                cell_magnitude = gradient_magnitude[i * self.cell_size:(i + 1) * self.cell_size,
                                 j * self.cell_size:(j + 1) * self.cell_size]
                cell_angle = gradient_angle[i * self.cell_size:(i + 1) * self.cell_size,
                             j * self.cell_size:(j + 1) * self.cell_size]
                cell_gradient_vector[i][j] = self.cell_gradient(cell_magnitude, cell_angle)

        hog_image = self.render_gradient(np.zeros([height, width]), cell_gradient_vector)
        hog_vector = []
        for i in range(cell_gradient_vector.shape[0] - 1):
            for j in range(cell_gradient_vector.shape[1] - 1):
                block_vector = []
                block_vector.extend(cell_gradient_vector[i][j])
                block_vector.extend(cell_gradient_vector[i][j + 1])
                block_vector.extend(cell_gradient_vector[i + 1][j])
                block_vector.extend(cell_gradient_vector[i + 1][j + 1])
                mag = lambda vector: math.sqrt(sum(i ** 2 for i in vector))
                magnitude = mag(block_vector)
                if magnitude != 0:
                    normalize = lambda block_vector, magnitude: [element / magnitude for element in block_vector]
                    block_vector = normalize(block_vector, magnitude)
                hog_vector.append(block_vector)
        return hog_vector

    def global_gradient(self):
        gradient_values_x = cv2.Sobel(self.img, cv2.CV_64F, 1, 0, ksize=5)
        gradient_values_y = cv2.Sobel(self.img, cv2.CV_64F, 0, 1, ksize=5)
        gradient_magnitude = cv2.addWeighted(gradient_values_x, 0.5, gradient_values_y, 0.5, 0)
        gradient_angle = cv2.phase(gradient_values_x, gradient_values_y, angleInDegrees=True)
        return gradient_magnitude, gradient_angle

    def cell_gradient(self, cell_magnitude, cell_angle):
        orientation_centers = [0] * self.bin_size
        for i in range(cell_magnitude.shape[0]):
            for j in range(cell_magnitude.shape[1]):
                gradient_strength = cell_magnitude[i][j]
                gradient_angle = cell_angle[i][j]
                min_angle, max_angle, mod = self.get_closest_bins(gradient_angle)
                orientation_centers[min_angle] += (gradient_strength * (1 - (mod / self.angle_unit)))
                orientation_centers[max_angle] += (gradient_strength * (mod / self.angle_unit))
        return orientation_centers

    def get_closest_bins(self, gradient_angle):
        idx = int(gradient_angle / self.angle_unit)
        mod = gradient_angle % self.angle_unit
        if idx == self.bin_size:
            return idx - 1, (idx) % self.bin_size, mod
        return idx, (idx + 1) % self.bin_size, mod

    def render_gradient(self, image, cell_gradient):
        cell_width = self.cell_size / 2
        max_mag = np.array(cell_gradient).max()
        for x in range(cell_gradient.shape[0]):
            for y in range(cell_gradient.shape[1]):
                cell_grad = cell_gradient[x][y]
                cell_grad /= max_mag
                angle = 0
                angle_gap = self.angle_unit
                for magnitude in cell_grad:
                    angle_radian = math.radians(angle)
                    x1 = int(x * self.cell_size + magnitude * cell_width * math.cos(angle_radian))
                    y1 = int(y * self.cell_size + magnitude * cell_width * math.sin(angle_radian))
                    x2 = int(x * self.cell_size - magnitude * cell_width * math.cos(angle_radian))
                    y2 = int(y * self.cell_size - magnitude * cell_width * math.sin(angle_radian))
                    cv2.line(image, (y1, x1), (y2, x2), int(255 * math.sqrt(magnitude)))
                    angle += angle_gap
        return image


img = cv2.imread('/home/pi/Desktop/picture/imag.jpg', cv2.IMREAD_GRAYSCALE)
hog = Hog_descriptor(img, cell_size=4, bin_size=4)
vector = hog.extract()


broker_address=""

client = mqtt.Client("pub1")
client.connect(broker_address)
client.publish("camera/camera1", vector)
os.remove('/home/pi/Desktop/picture/imag.jpg')

def message_func(message, userdata, client):
	topic = str(message.topic)
	message = int(message.payload.decode("utf-8"))
	if message == 0 :
		GPIO.output(ledpin, GPIO.LOW)
		time.sleep(0.5)
	else:
		GPIO.output(ledpin, GPIO.HIGH)
		time.sleep(0.5)

client.subscribe("gatecommand/gate1")
client.on_message = messageFunction
client.loop_start()	
