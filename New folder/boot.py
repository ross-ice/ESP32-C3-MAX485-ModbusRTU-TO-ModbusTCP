# boot.py
# This file is executed on every boot (including wake-from-sleep)
import gc
import machine
import network
import time

# --- LED Configuration ---
LED_PIN = 21 # GPIO Pin for the built-in LED (Commonly GPIO21 for ESP32-C3 Super Mini)
led = None

# --- WiFi Configuration ---
WIFI_SSID = "wifi-ice"      # <<< ใส่ชื่อ WiFi ของคุณที่นี่
WIFI_PASSWORD = ""          # <<< ยืนยันว่าไม่มีรหัสผ่านสำหรับ wifi-ice

# --- Start of Debugging LED (Simple blink to confirm boot) ---
try:
    led = machine.Pin(LED_PIN, machine.Pin.OUT)
    # กระพริบ LED 3 ครั้ง เพื่อบ่งบอกว่า boot.py เริ่มทำงาน
    for _ in range(3):
        led.value(1) # เปิด LED
        time.sleep_ms(100)
        led.value(0) # ปิด LED
        time.sleep_ms(100)
except Exception as e:
    print(f"boot.py: Failed to initialize LED on pin {LED_PIN}: {e}. LED debug disabled.")
    led = None # ตั้งค่า led เป็น None หากเกิดข้อผิดพลาด
# --- End of Debugging LED ---

print("boot.py: Starting Wi-Fi connection...")

def connect_wifi():
 
    nic = network.WLAN(network.STA_IF)
    
    # ถ้ามีการเชื่อมต่ออยู่แล้ว ให้ยกเลิกก่อน (เพื่อความแน่ใจในสถานะเริ่มต้น)
    if nic.isconnected():
        nic.disconnect()
        time.sleep_ms(100)
        print("boot.py: Disconnecting existing WiFi connection.")

    if not nic.active():
        nic.active(True)
        print("boot.py: Wi-Fi STA interface activated.")
        time.sleep_ms(100) # ให้เวลา interface เริ่มทำงาน

    print(f"boot.py: Attempting to connect to SSID: '{WIFI_SSID}'", end="")
    
    # ไม่มี nic.config(txpower=...) เพราะพบว่าไม่จำเป็นและอาจก่อให้เกิดปัญหา
    nic.connect(WIFI_SSID, WIFI_PASSWORD)
    
    max_wait = 30 # รอนานสุด 30 วินาทีสำหรับการเชื่อมต่อ
    while max_wait > 0:
        status = nic.status()
        if status == network.STAT_GOT_IP:
            break
        if status == network.STAT_WRONG_PASSWORD:
            print("\nboot.py: Error: Incorrect WiFi password.")
            break
        if status == network.STAT_NO_AP_FOUND:
            print("\nboot.py: Error: WiFi AP not found.")
            break
        if status == network.STAT_CONNECT_FAIL:
            print("\nboot.py: Error: WiFi connection failed (general error).")
            break
        max_wait -= 1
        print(".", end="")
        time.sleep(1)
    
    if not nic.isconnected():
        final_status = nic.status()
        print(f"\nboot.py: WiFi connection failed! Final status: {final_status}")
        # กระพริบ LED เร็วๆ เพื่อบ่งบอกว่า WiFi เชื่อมต่อไม่ได้
        if led:
            for _ in range(10):
                led.value(1)
                time.sleep_ms(50)
                led.value(0)
                time.sleep_ms(50)
        return False # คืนค่า False หากเชื่อมต่อไม่ได้
    
    ip_info = nic.ifconfig()
    print("\nboot.py: WiFi Connected!")
    print(f"boot.py: IP Address: {ip_info[0]}")
    print(f"boot.py: Subnet Mask: {ip_info[1]}")
    print(f"boot.py: Gateway: {ip_info[2]}")
    print(f"boot.py: DNS Server: {ip_info[3]}")
    
    # เปิด LED ค้างไว้ เพื่อบ่งบอกว่า WiFi เชื่อมต่อสำเร็จ
    if led:
        led.value(1) 
    
    return True # คืนค่า True หากเชื่อมต่อสำเร็จ

# เรียกฟังก์ชันเชื่อมต่อ Wi-Fi ทันทีที่บูต
connect_wifi()
gc.collect() # ทำ Garbage collection เพื่อเคลียร์หน่วยความจำ