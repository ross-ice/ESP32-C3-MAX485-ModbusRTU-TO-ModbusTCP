# wifi_ap_test.py
import network
import time
import machine
import gc

# --- AP Configuration ---
# *** สำคัญ: กำหนดชื่อและรหัสผ่านสำหรับ AP ที่ ESP32-C3 จะสร้างขึ้นมาเอง ***
# ชื่อ AP (SSID) ที่คุณจะเห็นบนมือถือ/คอมพิวเตอร์
AP_SSID = "ESP32C3_AP_Test" 
# รหัสผ่านสำหรับ AP นี้ (ต้องมีอย่างน้อย 8 ตัวอักษรสำหรับ WPA2)
AP_PASSWORD = "password123" 

# --- LED Configuration (สำหรับบอร์ด ESP32-C3 Super Mini) ---
LED_PIN = 0 # ลองใช้ GPIO21 ถ้าไม่ติด ลองเปลี่ยนเป็น GPIO2 หรือขาอื่นตามเอกสารบอร์ด
led = None

print("Starting Wi-Fi AP Test...")

def blink_led(times, duration_ms):
    if led:
        for _ in range(times):
            led.value(1)
            time.sleep_ms(duration_ms)
            led.value(0)
            time.sleep_ms(duration_ms)

try:
    led = machine.Pin(LED_PIN, machine.Pin.OUT)
    print(f"LED on GPIO{LED_PIN} initialized.")
    blink_led(3, 100) # กระพริบ 3 ครั้งเพื่อบ่งบอกว่าโปรแกรมเริ่มทำงาน
except Exception as e:
    print(f"Could not initialize LED on GPIO{LED_PIN}: {e}. LED debug disabled.")
    led = None # ตั้งค่า led เป็น None หากเกิดข้อผิดพลาด

def start_ap_mode():
    print("\nAttempting to start Wi-Fi AP mode...")
    nic = network.WLAN(network.AP_IF) # กำหนดเป็นโหมด AP
    
    # ปิดโหมด STA_IF ก่อน (ถ้าเคยเปิด) เพื่อหลีกเลี่ยงความขัดแย้ง
    sta_nic = network.WLAN(network.STA_IF)
    if sta_nic.active():
        sta_nic.active(False)
        print("STA interface deactivated.")

    nic.active(True) # เปิดใช้งาน AP interface
    
    # ตั้งค่า SSID และ Password สำหรับ AP
    # MicroPython จะใช้ WPA2-PSK โดยอัตโนมัติถ้ามีรหัสผ่าน
    nic.config(essid=AP_SSID, password=AP_PASSWORD)
    
    # รอให้ AP interface พร้อมทำงาน
    max_wait = 10
    while not nic.active() and max_wait > 0:
        print(".", end="")
        time.sleep(1)
        max_wait -= 1

    if nic.active():
        ap_ip_info = nic.ifconfig()
        print(f"\n*** Wi-Fi AP mode started successfully! ***")
        print(f"AP SSID:   '{AP_SSID}'")
        print(f"AP IP:     {ap_ip_info[0]}")
        print(f"AP Mask:   {ap_ip_info[1]}")
        
        if led:
            led.value(1) # เปิด LED ค้างไว้ถ้า AP ทำงานได้
        return True
    else:
        print("\n*** Failed to start Wi-Fi AP mode! ***")
        if led:
            blink_led(10, 50) # กระพริบเร็วๆ ถ้า AP ไม่ทำงาน
        return False

# --- Main execution of the AP test script ---
gc.collect() # ทำ Garbage collection
start_ap_mode()

print("\nWi-Fi AP test complete. (Board will keep AP active if successful)")

# Loop forever to keep the board alive and AP active
while True:
    time.sleep(1)