# boot.py
# This file is executed on every boot (including wake-from-sleep)
import gc
import machine
import network
import time

# --- WiFi Configuration ---
WIFI_SSID = "wifi-ice"      # <<<<< แก้ไขตรงนี้เป็นชื่อ WiFi ของคุณ
WIFI_PASSWORD = "06062523" # <<<<< แก้ไขตรงนี้เป็นรหัสผ่าน WiFi ของคุณ

def connect_wifi():
    print("Connecting to WiFi...", end="")
    nic = network.WLAN(network.STA_IF)
    nic.active(True)
    nic.connect(WIFI_SSID, WIFI_PASSWORD) # รับ IP แบบ DHCP โดยอัตโนมัติ
    
    max_wait = 20 # รอนานสุด 20 วินาที
    while max_wait > 0:
        if nic.isconnected():
            break
        max_wait -= 1
        print(".", end="")
        time.sleep(1)
    
    if not nic.isconnected():
        print("\nWiFi connection failed!")
        # Optional: Restart or go into deep sleep if WiFi fails completely
        # machine.reset() 
        return None # Return None if connection fails
    
    ip_info = nic.ifconfig()
    print("\nWiFi Connected!")
    print("IP Address:", ip_info[0])
    print("Subnet Mask:", ip_info[1])
    print("Gateway:", ip_info[2])
    print("DNS Server:", ip_info[3])
    return ip_info[0] # Return the assigned IP address

# Connect to WiFi on boot
gc.collect() # Garbage collection to free up memory
# Call connect_wifi and store the IP globally or pass it to main.py
# For simplicity, main.py will get the IP again
# Alternatively, you could write the IP to a file for main.py to read