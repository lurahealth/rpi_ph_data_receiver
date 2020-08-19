# rpi_ph_data_receiver
This repository contains a python script to continually scan for a Lura Health pH Sensor device and log device data when connected.

The python script is to be installed on a Raspberry Pi Zero W and automatically run on boot with a systemd service. The python script
depends on bluepy, datetime, and neopixel libraries (as well as a few others). All data is automatically logged into csv files, and
there is a csv file for script status/error logging as well as a csv file for the actual data. The Lura Health pH Sensor device must
be calibrated prior to interfacing with this system, if calibrated pH values are desired. 

The Raspberry Pi Zero W is intended to be embedded within a 3D printed case, attached to an 8x1 Neopixel strip and powered by a 
5000 mAh power bank. 

![RPi Case](https://github.com/lurahealth/rpi_ph_data_receiver/blob/master/images/case_transparent1.png?raw=true)
