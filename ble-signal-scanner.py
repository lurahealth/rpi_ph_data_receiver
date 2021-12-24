#!/usr/bin/env python 
from bluepy.btle import Scanner, DefaultDelegate, Peripheral, \
                        Service, Characteristic, UUID 
import sys

# Variables for BLE connections
global sensor_obj
rx_uuid       = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
tx_uuid       = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
notify_uuid   = "00002902-0000-1000-8000-00805f9b34fb"
notify_handle = 16
tx_handle     = 13
mac_add       = "df:96:da:db:05:5f"

# Callback when notifications are received, calls process_and_store_data
class NotifyDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle, data):
        print("** Notification received")

sensor_obj = Peripheral().withDelegate(NotifyDelegate())

# Callback to scanning object, prints new devices when discovered
class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

scanner = Scanner().withDelegate(ScanDelegate())

def write_rssi_to_csv(fname, rssi, ctr):
    fpath = "/home/pi/ph_receiver/rssi-logs/"
    logfile = fpath + fname
    with open(logfile, mode='a') as rssi_log:
        rssi_log.write(str(ctr) + ',' + str(rssi) + '\n')

def find_and_log_ble_strength(ctr):
    scanner.clear()
    scanner.start()
    scanner.process(2.0)
    devs = scanner.getDevices()
    for dev in devs:
        if dev.getValueText(9) is not None:
            if "LuraHealth" in dev.getValueText(9):
                print(str(dev.rssi))
                fname = "retainer-adv_IM_WITH-ANT_2.csv"
                write_rssi_to_csv(fname, dev.rssi, ctr)
                scanner.stop()

ctr = 0

while True:
    find_and_log_ble_strength(ctr)
    ctr = ctr + 1
