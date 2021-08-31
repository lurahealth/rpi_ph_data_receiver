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
from scipy import stats
import subprocess
import psutil

# # # # # # # # # # # # # # #
#   Restart program gracefully on error
# # # # # # # # # # # # # # # 
def restart_program():
    """Restarts the current program, with file objects and descriptors
       cleanup
    """

    try:
        p = psutil.Process(os.getpid())
        for handler in p.open_files() + p.connections():
            os.close(handler.fd)
    except Exception as e:
        print("Error: ")
        print(str(e))
        print("\n")
    python = sys.executable
    os.execl(python, python, *sys.argv)

# # # # # # # # # # # # # # #
#      GUI Layout   
# # # # # # # # # # # # # # #

import PySimpleGUI as sg

sg.theme('LightGrey1')

col2 = sg.Column([[sg.Frame('Device BLE Data:', [[sg.Column([
                                                      [sg.Text('             Time                       pH       Temp (*C)      Battery (mV)       pH (mV)')],
                                                      [sg.Multiline(key='-DATATABLE-',size=(68,27), autoscroll=True, auto_refresh=True, disabled=True)]],size=(500,480))]])]],pad=(0,0))

col1 = sg.Column([
    # Categories sg.Frame
    [sg.Frame('BLE Status:', [[sg.Text('DISCONNECTED', text_color='red', key='-BLE-')]])],
    # Information sg.Frame
    [sg.Frame('Calibration Points:',
                            [[sg.Text(), sg.Column([
                                     [sg.Text('Point 1, pH 10:', font='Ubuntu 13')],
                                     [sg.Multiline(key='-PT1-', size=(19,1), no_scrollbar=True, auto_refresh=True, disabled=True),
                                      sg.Button('Read Data', key='-PT1READ-', disabled=True)],
                                     [sg.Text('Point 2, pH 7:', font='Ubuntu 13')],
                                     [sg.Multiline(key='-PT2-', size=(19,1), no_scrollbar=True, auto_refresh=True, disabled=True),
                                      sg.Button('Read Data', key='-PT2READ-', disabled=True)],
                                     [sg.Text('Point 3, pH 4:', font='Ubuntu 13')],
                                     [sg.Multiline(key='-PT3-', size=(19,1), no_scrollbar=True, auto_refresh=True, disabled=True),
                                      sg.Button('Read Data', key='-PT3READ-', disabled=True)],
                                     [sg.Text('Calibration Instructions:')],
                                     [sg.Multiline(key='-INS-', size=(51,11), default_text='\n\n    Connect to Lura BLE device to continue', no_scrollbar=True, auto_refresh=True, disabled=True)],
                                     [sg.Button('CONTINUE', key='CONTINUE', bind_return_key=True, pad=(255,0))],
                             ], size=(380,460), pad=(0,0))]])], ], pad=(0,0))

col3 = sg.Column([[sg.Frame('Actions:',
                            [[sg.Column([[sg.Button(' EXIT ', pad=(20,0), button_color='OrangeRed'), sg.Button('RESTART')]],
                                        size=(290,45), pad=(0,0))]]),
                   sg.Frame('Calibration Results:',
                            [[sg.Column([[sg.Text('Sensitivity (mV / pH): ', font='Ubuntu 11', text_color='red'), sg.Text('          ', key='-SENS-'), sg.Text('R^2: ', font='Ubuntu 11', text_color='red'), sg.Text('               ', key='-R2-'), sg.Text('Offset (mV): ', font='Ubuntu 11', text_color='red'), sg.Text('           ', key='-OFFSET-')]], size=(550,45), pad=(30,0))]], pad=(10,0))]])

# The final layout is a simple one
layout = [[col1, col2],
          [col3]]


window = sg.Window('Lura Health Calibration Tool', layout, resizable=True)

# # # # # #  Helpers for updating GUI # # # # # # # 

def update_blestatus(connected):
    if connected is True:
        window.Element('-BLE-').Update(value='CONNECTED', text_color='green')
    else:
        window.Element('-BLE-').Update(value='DISCONNECTED', text_color='red')


def update_datatable(data):
    window.Element('-DATATABLE-').Update(value=data, append=True )


def check_continue():
    event, values = window.read(50)
    if event == 'CONTINUE':
        begin_cal()
    elif event == sg.WIN_CLOSED or event == ' EXIT ':
        graceful_exit()
    elif event == 'RESTART':
        begin_demo_proto()

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
# Found from https://simondlevy.academic.wlu.edu/files/software/kbhit.py
# 
# Implementation for non-blocking keyboard polling
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
import os

# Windows
if os.name == 'nt':
    import msvcrt

# Posix (Linux, OS X)
else:
    import sys
    import termios
    import atexit
    from select import select


class KBHit:

    def __init__(self):
        '''Creates a KBHit object that you can call to do various keyboard things.
        '''

        if os.name == 'nt':
            pass

        else:

            # Save the terminal settings
            self.fd = sys.stdin.fileno()
            self.new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)

            # New terminal setting unbuffered
            self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)

            # Support normal-terminal reset at exit
            atexit.register(self.set_normal_term)


    def set_normal_term(self):
        ''' Resets to normal terminal.  On Windows this is a no-op.
        '''

        if os.name == 'nt':
            pass

        else:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)


    def getch(self):
        ''' Returns a keyboard character after kbhit() has been called.
            Should not be called in the same program as getarrow().
        '''

        s = ''

        if os.name == 'nt':
            return msvcrt.getch().decode('utf-8')

        else:
            return sys.stdin.read(1)


    def getarrow(self):
        ''' Returns an arrow-key code after kbhit() has been called. Codes are
        0 : up
        1 : right
        2 : down
        3 : left
        Should not be called in the same program as getch().
        '''

        if os.name == 'nt':
            msvcrt.getch() # skip 0xE0
            c = msvcrt.getch()
            vals = [72, 77, 80, 75]

        else:
            c = sys.stdin.read(3)[2]
            vals = [65, 67, 66, 68]

        return vals.index(ord(c.decode('utf-8')))


    def kbhit(self):
        ''' Returns True if keyboard character was hit, False otherwise.
        '''
        if os.name == 'nt':
            return msvcrt.kbhit()

        else:
            dr,dw,de = select([sys.stdin], [], [], 0)
            return dr != []
        
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 

# non-blocking keyboard input stuff
kb = KBHit()

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
global PT1mv
global PT2mv
global PT3mv
global PT1temp
global PT2temp
global PT3temp

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
     # subprocess.run(["sudo systemctl start ph_receiver.service"])
     # print("PROGRAM ENDING\n")
     begin_client_proto()
     pixels.fill((0,0,0))
     pixels[ERR] = RED
     t.sleep(1)

atexit.register(exit_handler)

# Send a packet saying "DONE" after all the data has been read in the case
# of buffered data packets
def send_done_packet():
    global receiving_buffer
    receiving_buffer = False
    
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("DONE".encode('utf-8'), False)
    
    
def read_cal_point(cal_point):
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    event, values = window.read(25)
    if event == sg.WIN_CLOSED or event == ' EXIT ':
        graceful_exit()
    elif event == 'RESTART':
        begin_demo_proto()
    window.Element('CONTINUE').Update(disabled=True)
    window.Element('-PT1READ-').Update(disabled=True)
    window.Element('-PT2READ-').Update(disabled=True)
    window.Element('-PT3READ-').Update(disabled=True)
    if cal_point == 1:
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='Step 1, pH 10: ',append=True)
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='Rinse the Lura Health retainer with water, then dip into pH 10 buffer. Swirl the retainer briefly.',append=True)
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='Click "Read Data" when you are ready to collect and store the calibration point.',append=True)
        window.Element('-PT1READ-').Update(disabled=False)
        pt_read = False
        while not pt_read: 
            event, values = window.read()
            if event == '-PT1READ-':
                pt_read = True
            if event == sg.WIN_CLOSED or event == ' EXIT ':
                graceful_exit()
            elif event == 'RESTART':
                begin_demo_proto()

        tx_char.write("PT1_10.0".encode('utf-8'), False)
        
    if cal_point == 2:
        window.Element('-INS-').Update(value='\n',append=False)
        window.Element('-INS-').Update(value='Step 2, pH 7:',append=True)
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='Rinse the Lura Health retainer with water, then dip into pH 7 buffer. Swirl the retainer briefly.',append=True)
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='Click "Read Data" when you are ready to collect and store the calibration point.',append=True)
        window.Element('-PT2READ-').Update(disabled=False)
        pt_read = False
        while not pt_read: 
            event, values = window.read()
            if event == '-PT2READ-':
                pt_read = True
        tx_char.write("PT2_7.0".encode('utf-8'), False)
        
    if cal_point == 3:
        window.Element('-INS-').Update(value='\n',append=False)
        window.Element('-INS-').Update(value='Step 3, pH 4:',append=True)
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='Rinse the Lura Health retainer with water, then dip into pH 4 buffer. Swirl the retainer briefly.',append=True)
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='\n',append=True)
        window.Element('-INS-').Update(value='Click "Read Data" when you are ready to collect and store the calibration point.',append=True)
        window.Element('-PT3READ-').Update(disabled=False)
        pt_read = False
        while not pt_read:
            event, values = window.read()
            if event == '-PT3READ-':
                pt_read = True
                window.Element('-PT3READ-').Update(disabled=True)
            if event == sg.WIN_CLOSED or event == ' EXIT ':
                graceful_exit()
            elif event == 'RESTART':
                begin_demo_proto()
            elif event == 'RESTART':
                begin_demo_proto()
        tx_char.write("PT3_4.0".encode('utf-8'), False)
        
def print_cal_instructions():
    global in_precal_state
    read_window_helper() 
    window.Element('-INS-').Update(value="Data will now be printed to this screen. New data is read every second. ",append=False)
    window.Element('-INS-').Update(value="When you press the CONTINUE button, data will pause and the 3 point calibration will start.\n",append=True)
    window.Element('-INS-').Update(value='\n',append=True)

    window.Element('-INS-').Update(value="Rows of data contain:  ",append=True)
    window.Element('-INS-').Update(value='\n',append=True)
    window.Element('-INS-').Update(value="      pH, temperature (*C), battery (mV), pH (mV).",append=True)
    window.Element('-INS-').Update(value='\n',append=True)
    window.Element('-INS-').Update(value='\n',append=True)
    window.Element('-INS-').Update(value="Before clicking CONTINUE and while data is printed, you may test the device in pH buffers. Instructions for calibration will be printed after you click CONTINUE.",append=True)
    in_precal_state = True
        
def begin_demo_proto():
    global in_demo_proto_state
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("DEMO_PROTO".encode('utf-8'), False)
    in_demo_proto_state = True
    print_cal_instructions()
    
def send_stayon_command():
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("STAYON".encode('utf-8'), False)
    
    
    
def begin_client_proto():
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("CLIENT_PROTO".encode('utf-8'), False)
    tx_char.write("STAYON".encode('utf-8'), False)


def begin_cal():
    global sensor_obj
    global in_precal_state
    in_precal_state = False
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("STARTCAL3".encode('utf-8'), False)

    read_window_helper() 
    window.Element('-INS-').Update(value="3 Point Calibration started succesfully.",append=False)
    window.Element('-INS-').Update(value='\n',append=True)
    window.Element('-INS-').Update(value='\n',append=True)
    read_cal_point(1)
    read_cal_point(2)
    read_cal_point(3)

def get_calibration_vals():
    global PT1mv
    global PT2mv
    global PT3mv
    global PT1temp
    global PT2temp
    global PT3temp

    
    avg_temp = (float(PT1temp) + float(PT2temp) + float(PT3temp)) / 3
    
    x = [int(PT1mv), int(PT2mv), int(PT3mv)]
    y = [10, 7, 4]
    
    # Inverse Y = Mx + B to M = (Y - B)/x    
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    window.read(1)
    window.Element('-SENS-').Update(value=str(1/slope)[:5])
    window.Element('-OFFSET-').Update(value=str(intercept/slope*(-1))[:5])
    window.Element('-R2-').Update(value=str(r_value)[:5])

    orig_time = datetime.now(CST)
    fout = open(fname, "a+")
    fout.write(str(orig_time.strftime(fmt + "Sensitivity (mV / pH): " + str(1/slope)[:5] + "   Offset (mV): " + str(intercept/slope*(-1))[:5] + "   r val: " + str(r_value)[:5] + "temp (*C): " + str(avg_temp)[:5] + "\n")))
    fout.close()
   

def print_data_after_cal():
    global sensor_obj
    tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
    tx_char = tx_char_list[0]
    tx_char.write("DEMO_PROTO".encode('utf-8'), False)

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
    global PT1mv
    global PT2mv
    global PT3mv
    global PT1temp
    global PT2temp
    global PT3temp
    
    if "PT" in data:
        if "PT1" in data:
            PT1mv = data.split()[1]
            PT1temp = data.split()[3]
            read_window_helper()
            window.Element('-PT1-').Update(value=str(PT1mv + ' mV,  ' + PT1temp + ' *C  '))
        elif "PT2" in data:
            PT2mv = data.split()[1]
            PT2temp = data.split()[3]
            read_window_helper()
            window.Element('-PT2-').Update(value=str(PT2mv + ' mV,  ' + PT2temp + ' *C  '))
        elif "PT3" in data:
            PT3mv = data.split()[1]
            PT3temp = data.split()[3]
            read_window_helper()
            window.Element('-PT3-').Update(value=str(PT3mv + ' mV,  ' + PT3temp + ' *C  '))
    
    if "M=" in data:
        
        orig_time = datetime.now(CST)
        fout = open(fname, "a+")
        fout.write(str(orig_time.strftime(fmt + "," + data + " !! 20 byte clamped packet from nRF\n")))
        fout.close()
        get_calibration_vals()
        window.read(5)
        window.Element('-INS-').Update(value='Calibration complete. \n\nData will now be printed to the screen.\n', append=False)
        window.Element('-INS-').Update(value='You can verify your calibration results in pH buffers.\n\n', append=True)
        window.Element('-INS-').Update(value='Press EXIT or RESTART to exit and resume normal operation or restart this calibration tool.', append=True)

        tx_char_list = sensor_obj.getCharacteristics(uuid=tx_uuid)
        tx_char = tx_char_list[0]
        tx_char.write("DEMO_PROTO".encode('utf-8'), False)
        
    if "TOTAL" in data:
        receiving_buffer = True
        in_demo_proto_state = False
        
    if "TOTAL" not in data and receiving_buffer == False and in_demo_proto_state == False:
        begin_demo_proto()

    if "TOTAL" in data:
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
            if "PT" in data or "M=" in data: f.write(str(time.strftime(fmt + "," +  data + "\n")))
            else: f.write(str(time.strftime(fmt + "," +  data)))
            f.close()
            if "CALBEGIN" not in data and "PT" not in data and "M=" not in data:
                ph, temp, batt, ph_mv = str(data).split(',')
                update_datatable(str("    " + time.strftime(fmt + "         " + ph + "          " + temp + "              " + batt + "                  " + ph_mv )))
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
            f = open(fname, "a+")
            for data in data_buffer:
                    f.write(data)
            f.close()
            for data in range(total_packs):
                data_buffer[data] = None
            data_buffer.clear()
            #  Start demo protocol and begin calibration
            in_demo_proto_state = True
            begin_demo_proto()

# Callback when notifications are received, calls process_and_store_data
class NotifyDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    # Read data and store in csv file as appropriate
    def handleNotification(self, cHandle, data):
        check_continue()
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
            sensor_name = stored_name
        prev_connection = True

def store_device_name(name):
    f = open("/home/pi/Desktop/device_name.txt", "w")
    f.write(name)
    f.close()

def read_window_helper():
    event, values = window.read(10)
    if event == sg.WIN_CLOSED or event == ' EXIT ':
        graceful_exit()
    elif event == 'RESTART':
        begin_demo_proto()

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
        read_window_helper()
        update_blestatus(False)
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
                    fname = fpath + dev.getValueText(9) + ".csv"
                    foutname = foutpath + dev.getValueText(9) + ".txt"
                    sensor_obj.connect(dev.addr, dev.addrType)
                    read_window_helper()
                    update_blestatus(True)
                    write_csv_header()
                    store_device_name(dev.getValueText(9))
                    connected = True
                    pixels[CONN] = GREEN
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
print("*** Opening graphical tool and BLE Scanning for Lura device...")

def graceful_exit():
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

# Continually scan and connect to device if available
while True:
    try:
        global in_precal_state
        event, values = window.read(25)
        if event == sg.WIN_CLOSED or event == ' EXIT ':
                graceful_exit()
        elif event == 'RESTART':
                begin_demo_proto()
        find_and_connect()
        if sensor_obj.waitForNotifications(3.0):
            event, values = window.read(25)
            if event == 'CONTINUE' and in_precal_state == True:
                begin_cal()
            pass
        event, values = window.read(25)
        if (in_precal_state == True and (kb.kbhit() or event == 'CONTINUE')):
            c = kb.getch()
            if ord(c) == 10:
                in_precal_state = False
                begin_cal()
            if (event == 'CONTINUE'):
               in_precal_state = False
               begin_cal()
    
    except Exception as e:
        print("!!! Whoops, there was a problem in the application !!!\n!!! Please check /home/pi/Desktop/calibration_event_outputs for more info !!!\n")
        print(e)
        global in_demo_proto_state 
        read_window_helper()
        update_blestatus(False)
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
                restart_program() 
                #sys.exit(0)
            except SystemExit:
                pixels.fill((0,0,0))
                t.sleep(1)
                pixels[ERR] = RED
                restart_program()
                #os._exit(0)
        elif "disconnected" in str(e):
            connected = False
            pixels[CONN] = RED
            print("!!! * * * * * * * * * * * * * !!!")
            print("!!!    BLE connection lost    !!!")
            print("!!! * * * * * * * * * * * * * !!!")
            remaining_packs = 1
            total_packs = 1
            restart_program()
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
    
