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
import subprocess

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
WIFI  = 6
ERR   = 7

BLANK  = (0,0,0)
RED    = (255,0,0)
GREEN  = (0,255,0)
YELLOW = (255,255,0)

# Variables for BLE connections
global sensor_obj
sensor_name   = "Lura"
rx_uuid       = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
tx_uuid       = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
notify_uuid   = "00002902-0000-1000-8000-00805f9b34fb"
notify_handle = 16
tx_handle     = 13
mac_add       = "df:96:da:db:05:5f"
connected     = False

# Variables for timestamping
CST = timezone("US/Eastern")
fmt = "%Y-%m-%d %H:%M:%S" 

# Variables for packet CSV storage
csv_header   = "Time (YYYY-MM-DD HH-MM-SS), pH (calibrated), temp (mv), batt (mv), pH (mv)"
fpath        = "/home/pi/Desktop/csv_files/"
fname        = fpath # append with name of device
foutpath     = "/home/pi/Desktop/event_outputs/"
foutname     = foutpath # Append with name of device
fifteen_mins = timedelta(minutes = 5)

global remaining_packs
global total_packs
global data_buffer
global f
remaining_packs = 1
total_packs     = 1
data_buffer     = list()

# Set up the data csv file with appropriate column headers if they don't exist
def write_csv_header():
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

def log_connection_and_time(rssi):
    orig_time = datetime.now(CST)
    fout = open(foutname, "a+")
    fout.write(str(orig_time.strftime(fmt + ", " +  "Device connected, " + str(rssi) + "\n")))
    fout.close()

scanner = Scanner().withDelegate(ScanDelegate())
                
def check_for_stored_device_name():
   global prev_connection 
   global sensor_name
   prev_connection = False        
   if os.stat("/home/pi/Desktop/device_name.txt").st_size != 0:
        with open("device_name.txt") as f:
            stored_name = f.readline()
            print("stored name: " + stored_name)
            sensor_name = stored_name
        prev_connection = True

def store_device_name(name):
    f = open("/home/pi/Desktop/device_name.txt", "w")
    f.write(name)
    f.close()

def find_and_connect():
    global connected
    global fname
    global foutname
    while not connected:
        update_wifi_led()
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
                    scanner.stop()
                    if dev.rssi > -60:
                        fname = fpath + dev.getValueText(9) + ".csv"
                        foutname = foutpath + dev.getValueText(9) + ".csv"
                        sensor_obj.connect(dev.addr, dev.addrType)
                        print("Connected to lura health device")
                        write_csv_header()
                        store_device_name(dev.getValueText(9))
                        connected = True
                        pixels[CONN] = GREEN
                        log_connection_and_time(dev.rssi)
                        sensor_obj.writeCharacteristic(notify_handle, b'\x01\x00', True)
                    pixels[FOUND] = BLANK

def update_wifi_led():
    ps = subprocess.Popen(['iwconfig'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        output = subprocess.check_output(('grep', 'ESSID'), stdin=ps.stdout)
        pixels[WIFI] = GREEN
    except subprocess.CalledProcessError:
        # grep did not match any lines
        pixels[WIFI] = RED


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
        print(str(e) + "\n")
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
