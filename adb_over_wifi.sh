#!/bin/sh 
adb disconnect
adb tcpip 5555
sleep 3
IP=$(adb shell ip addr show wlan0  | grep 'inet ' | cut -d' ' -f6| cut -d/ -f1)
echo "Ip address: ${IP}"
adb connect $IP:5555
