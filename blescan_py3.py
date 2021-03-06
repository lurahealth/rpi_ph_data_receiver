#!/usr/bin/env python 
from bluepy.btle import Scanner, DefaultDelegate, Peripheral, \
                        Service, Characteristic, UUID 
from datetime import datetime 
from datetime import timedelta
from pytz     import timezone
import sys
import os
import math
import board
import neopixel
import time as t
import atexit

# Variables for neopixel strip
#
# LED indicators for script running (PWR), scanning (SCAN), Lura
# device found (FOUND), connection to lura device (CONN), receiving
# data (DATA), any errors (ERR)
pixels = neopixel.NeoPixel(board.D18, 8, brightness=0.01, \
                           auto_write=True, pixel_order=neopixel.GRB)
PWR   = 0
SCAN  = 2
FOUND = 3
CONN  = 4
DATA  = 5
ERR   = 7

BLANK  = (0,0,0)
RED    = (255,0,0)
GREEN  = (0,255,0)
YELLOW = (255,255,0)

# Variables for BLE connections
global sensor_obj
sensor_name   = "Lura_Test_Dan"
rx_uuid       = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
tx_uuid       = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
notify_uuid   = "00002902-0000-1000-8000-00805f9b34fb"
notify_handle = 16
tx_handle     = 13
mac_add       = "df:96:da:db:05:5f"
connected     = False

# Variables for timestamping
CST = timezone("Asia/Hong_Kong")
fmt = "%Y-%m-%d %H:%M:%S" 

# Variables for packet CSV storage
csv_header   = "Time (YYYY-MM-DD HH-MM-SS), pH (calibrated), temp (ADC), batt (ADC), pH (ADC)"
fpath        = "/home/pi/ph_receiver/csv_files/"
fname        = fpath + "data.csv"
foutpath     = "/home/pi/ph_receiver/"
foutname     = foutpath + "output.csv"
fifteen_mins = timedelta(minutes = 15)

global remaining_packs
global total_packs
global data_buffer
global f
remaining_packs = 1
total_packs     = 1
data_buffer     = list()

# Set up the data csv file with appropriate column headers if they don't exist
f = open(fname, "a+")
f.seek(0)
if csv_header not in f.readline():
    f.write(csv_header + "\n")
f.close()

def exit_handler():
     print("PROGRAM ENDING\n")
     pixels.fill((0,0,0))
     pixels[ERR] = RED
     t.sleep(1)

atexit.register(exit_handler)

# Send a packet saying "DONE" after all the data has been read in the case
# of buffered data packets
def send_done_packet():
    print("Sending done packet")
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("DONE".encode('utf-8'), False)
    print("DONE packet sent \n")

# Store data using back dating timestamp protocol when writing to csv file, if 
# multiple packets are sent
#
# If multiple packets are to be sent, first packet will follow format of 
# "TOTAL_XXXXX" where XXXXX is a positive integer value
def process_and_store_data(data):
    global f
    global remaining_packs
    global total_packs
    global data_buffer
    global connected

    print("remaining packs = " + str(remaining_packs))

    if "TOTAL" in data:
        # Parse number of expected packets and store in expected_packets
        total_packs = int(data.split('_')[1])
        remaining_packs = total_packs
        print("receiving buffered data, total packs = " + str(total_packs))
        # Open program status file, write, close
        orig_time = datetime.now(CST)
        fout = open(foutname, "a+")
        fout.write(str(orig_time.strftime(fmt + "," +  " Connected " + \
                                          "with " + str(total_packs) + " packet to receive\n")))
        fout.close()
    elif remaining_packs == total_packs:
        orig_time = datetime.now(CST)
        time = orig_time - ((remaining_packs - 1) * fifteen_mins)
        # Write to file if only 1 total packet, store in temp array otherwise
        if total_packs == 1:
            f = open(fname, "a+")
            f.write(str(time.strftime(fmt + "," +  data)))
            f.close()
        else:
           data_buffer.append(str(time.strftime(fmt + "," +  data))) 
           remaining_packs -= 1
           if remaining_packs == 1:
                return
    elif remaining_packs < total_packs and remaining_packs is not 1:
        time = datetime.now(CST)
        time = time - ((remaining_packs - 1) * fifteen_mins)
        data_buffer.append(str(time.strftime(fmt + "," +  data))) 
        if remaining_packs is not 1:
                remaining_packs -= 1
                if remaining_packs == 1:
                        return

    if remaining_packs == 1:
        # Iterate through buffer and write data to file
        if total_packs > 1:
            total_packs = 1
            time = datetime.now(CST)
            adj_time = time - ((remaining_packs - 1) * fifteen_mins)
            data_buffer.append(str(adj_time.strftime(fmt + "," +  data))) 
            print("*** WRITING TO FILE USING BUFFERED DATA ****")
            f = open(fname, "a+")
            for data in data_buffer:
                    f.write(data)
            f.close()
            for data in range(total_packs):
                data_buffer[data] = None
            data_buffer.clear()

# Callback when notifications are received, calls process_and_store_data
class NotifyDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    # Read data and store in csv file as appropriate
    def handleNotification(self, cHandle, data):
        print("** Notification received")
        pixels[DATA] = GREEN
        process_and_store_data(data.decode("utf-8"))
        pixels[DATA] = BLANK

sensor_obj = Peripheral().withDelegate(NotifyDelegate())

# Callback to scanning object, prints new devices when discovered
class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

def log_connection_and_time():
    orig_time = datetime.now(CST)
    fout = open(foutname, "a+")
    fout.write(str(orig_time.strftime(fmt + ", " +  "Device connected\n")))
    fout.close()

scanner = Scanner().withDelegate(ScanDelegate())
                
def find_and_connect():
    global connected
    while not connected:
        scanner.clear()
        scanner.start()
        pixels[SCAN] = GREEN
        scanner.process(1.0)                    
        devs = scanner.getDevices()
        for dev in devs:
            if dev.getValueText(9) is not None:
                if sensor_name in dev.getValueText(9):
                    pixels[FOUND] = GREEN
                    pixels[SCAN]  = BLANK
                    print("Found lura device")
                    scanner.stop()
                    sensor_obj.connect(dev.addr, dev.addrType)
                    print("Connected to lura health device")
                    connected = True
                    pixels[CONN] = GREEN
                    print("Enabling notifications")
                    log_connection_and_time()
                    sensor_obj.writeCharacteristic(notify_handle, b'\x01\x00', True)
                    pixels[FOUND] = BLANK

# Init script status to on
pixels.fill((0,0,0))
t.sleep(1)
pixels[PWR]  = GREEN
pixels[CONN] = RED

# Continually scan and connect to device if available
while True:
    try:
        find_and_connect()
        if sensor_obj.waitForNotifications(3.0):
            pass
    except Exception as e:
        time = datetime.now(CST)
        fout = open(foutname, "a+")
        fout.write(str(time.strftime(fmt)))
        fout.write(", " + str(e) + "\n")
        fout.close()
        if "Failed" in str(e):
            try:
                pixels.fill((0,0,0))
                t.sleep(1)
                pixels[ERR] = RED
                sys.exit(0)
            except SystemExit:
                pixels.fill((0,0,0))
                t.sleep(1)
                pixels[ERR] = RED
                os._exit(0)
        elif "disconnected" in str(e):
            connected = False
            pixels[CONN] = RED
            print(e)
            print("Restarting now\n")
            remaining_packs = 1
            total_packs = 1 
            continue
        else:
            try:
                pixels.fill((0,0,0))
                t.sleep(1)
                pixels[ERR] = RED
                sys.exit(0)
            except SystemExit:
                pixels.fill((0,0,0))
                t.sleep(1)
                pixels[ERR] = RED
                os._exit(0)
    else:
        continue
