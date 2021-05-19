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
fpath        = "/home/pi/Desktop/calibration_csv_files/"
fname        = fpath # append with name of device
foutpath     = "/home/pi/Desktop/calibration_event_outputs/"
foutname     = foutpath # Append with name of device
fifteen_mins = timedelta(minutes = 5)

global remaining_packs
global total_packs
global data_buffer
global f
global receiving_buffer
global in_demo_proto_state
global in_precal_state
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
     # print("PROGRAM ENDING\n")
     pixels.fill((0,0,0))
     pixels[ERR] = RED
     t.sleep(1)

atexit.register(exit_handler)

# Send a packet saying "DONE" after all the data has been read in the case
# of buffered data packets
def send_done_packet():
    global receiving_buffer
    receiving_buffer = False
    
    print("Buffered data has been stored and logged. Continuing to calibration...")
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("DONE".encode('utf-8'), False)
    # print("DONE packet sent \n")
    
    
def read_cal_point(cal_point):
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    if cal_point == 1:
        tx_char.write("PT1_10.0".encode('utf-8'), False)
        print("\nStep 1: Please dip the Lura Health retainer into pH 10 buffer. Swirl the retainer briefly.")
        print("        Data will be printed for you to view. Press ENTER when you ready to store data as a calibration point.")
        input(" ")
        
    if cal_point == 2:
        tx_char.write("PT2_7.0".encode('utf-8'), False)
        print("\nStep 1: Please dip the Lura Health retainer into pH 7 buffer. Swirl the retainer briefly.")
        print("        Data will be printed for you to view. Press ENTER when you ready to store data as a calibration point.")
        input(" ")
        
    if cal_point == 3:
        tx_char.write("PT3_4.0".encode('utf-8'), False)
        print("\nStep 1: Please dip the Lura Health retainer into pH 4 buffer. Swirl the retainer briefly.")
        print("        Data will be printed for you to view. Press ENTER when you ready to store data as a calibration point.")
        input(" ")
        
def print_cal_instructions():
    print("\n*** Data will now be printed to this screen. New data is read every second.")
    print("    Data will be continually printed until you press the ENTER key.")
    print("    When you press the ENTER key, the 3 point calibration will start.")
    print(" ")
    print("*** Rows of data contain: pH value, temperature (*C), battery level (mV), pH value (mV).")
    print("    Before pressing ENTER and while data is printed, you may briefly test the device")
    print("    in pH buffers. Once you press the ENTER key, one set of pH data will be printed per calibration point.")
    input("\n\n        (press ENTER when you are finished reading the above instructions)\n")
    print("*** Starting to print data. Press ENTER when you are ready to begin calibration...\n")
    t.sleep(1)
        
def begin_demo_proto():
    global in_precal_state
    global in_demo_proto_state
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("DEMO_PROTO".encode('utf-8'), False)
    # begin_cal()
    in_precal_state = True
    in_demo_proto_state = True
    print_cal_instructions()
    
    
def begin_client_proto():
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("CLIENT_PROTO".encode('utf-8'), False)
    sleep(0.2)
    tx_char.write("STAYON".encode('utf-8'), False)


def begin_cal():
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("STARTCAL3".encode('utf-8'), False)
    print("\n*** 3 Point Calibration started succesfully")
    read_cal_point(1)
    read_cal_point(2)
    read_cal_point(3)
  


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
    global receiving_buffer
    global in_demo_proto_state
    
    if "TOTAL" in data:
        receiving_buffer = True
        in_demo_proto_state = False
        
    if "TOTAL" not in data and receiving_buffer == False and in_demo_proto_state == False:
        begin_demo_proto()

    if "TOTAL" in data:
        print("*** Buffered data is being received, one moment...")
        # Parse number of expected packets and store in expected_packets
        total_packs = int(data.split('_')[1])
        remaining_packs = total_packs
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
            print(str(time.strftime(fmt + "," +  data))[:-1]) # Remove trailing \n
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
            receiving_buffer = False
            total_packs = 1
            time = datetime.now(CST)
            adj_time = time - ((remaining_packs - 1) * fifteen_mins)
            data_buffer.append(str(adj_time.strftime(fmt + "," +  data))) 
            # print("*** WRITING TO FILE USING BUFFERED DATA ****")
            f = open(fname, "a+")
            for data in data_buffer:
                    f.write(data)
            f.close()
            for data in range(total_packs):
                data_buffer[data] = None
            data_buffer.clear()
            #  Start demo protocol and begin calibration
            print("*** Buffered data has been stored and logged. Continuing to calibration...")
            in_demo_proto_state = True
            begin_demo_proto()

# Callback when notifications are received, calls process_and_store_data
class NotifyDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    # Read data and store in csv file as appropriate
    def handleNotification(self, cHandle, data):
        # print("** Notification received")
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
    global receiving_buffer
    global in_demo_proto_state
    global in_precal_state
    
    while not connected:
        receiving_buffer    = False
        in_demo_proto_state = False
        in_precal_state     = False
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
                    print("*** Found lura device")
                    scanner.stop()
                    fname = fpath + dev.getValueText(9) + ".csv"
                    foutname = foutpath + dev.getValueText(9) + ".txt"
                    sensor_obj.connect(dev.addr, dev.addrType)
                    print("*** Connected to: " + str(dev.getValueText(9)))
                    write_csv_header()
                    store_device_name(dev.getValueText(9))
                    connected = True
                    pixels[CONN] = GREEN
                    # print("*** Preparing to receive data...")
                    log_connection_and_time()
                    sensor_obj.writeCharacteristic(notify_handle, b'\x01\x00', True)
                    pixels[FOUND] = BLANK


# Init script status to on
pixels.fill((0,0,0))
t.sleep(0.2)
pixels[PWR]  = GREEN
pixels[CONN] = RED

print("\n* * * * * * * * * * * * * * * * * * * * * * * * * * *")
print("*         Beginning 3 Point Calibration             *")
print("* * * * * * * * * * * * * * * * * * * * * * * * * * *")
print(" ")
print("*** BLE Scanning for Lura device...")

# Continually scan and connect to device if available
while True:
    try:
        find_and_connect()
        if sensor_obj.waitForNotifications(3.0):
            pass
    except Exception as e:
        global in_demo_proto_state 
        in_demo_proto_state = False
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
            # print(e)
            print("!!! * * * * * * * * * * * * * !!!")
            print("!!!    BLE connection lost    !!!")
            print("!!! * * * * * * * * * * * * * !!!")
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
