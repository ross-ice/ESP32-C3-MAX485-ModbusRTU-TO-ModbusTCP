# wifi_test.py
import network
import time
import machine
import gc

# --- WiFi Configuration ---
# *** สำคัญ: แก้ไข WIFI_SSID และ WIFI_PASSWORD ให้ถูกต้อง ***
WIFI_SSID = "wifi-ice"      # <<<<< แก้ไขชื่อ WiFi ของคุณที่นี่
WIFI_PASSWORD = "" # <<<<< แก้ไขรหัสผ่าน WiFi ของคุณที่นี่

# --- LED Configuration (สำหรับบอร์ด ESP32-C3 Super Mini) ---
LED_PIN = 0 # ลองใช้ GPIO21 ถ้าไม่ติด ลองเปลี่ยนเป็น GPIO2 หรือขาอื่นตามเอกสารบอร์ด
led = None

print("Starting WiFi Test...")

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

def test_wifi_connection():
    print("\nAttempting to connect to WiFi...")
    nic = network.WLAN(network.STA_IF)
    
    # ตรวจสอบสถานะก่อน active/connect
    print(f"Initial Wi-Fi status: {nic.status()}")

    if not nic.active():
        nic.active(True)
        print("Wi-Fi STA interface activated.")
        time.sleep_ms(100) # ให้เวลา interface เริ่มทำงาน

    print(f"Attempting to connect to SSID: '{WIFI_SSID}'")
    nic.connect(WIFI_SSID, WIFI_PASSWORD)
    
    max_wait = 30 # รอนานสุด 30 วินาทีสำหรับการเชื่อมต่อ
    while max_wait > 0:
        current_status = nic.status()
        print(f"Current Wi-Fi status: {current_status} ({network_status_to_string(current_status)})", end="")
        if nic.isconnected():
            print("\n") # ขึ้นบรรทัดใหม่เมื่อเชื่อมต่อสำเร็จ
            break
        max_wait -= 1
        print(".", end="")
        time.sleep(1)
    
    if nic.isconnected():
        ip_info = nic.ifconfig()
        print("\n*** WiFi Connected Successfully! ***")
        print(f"IP Address:   {ip_info[0]}")
        print(f"Subnet Mask:  {ip_info[1]}")
        print(f"Gateway:      {ip_info[2]}")
        print(f"DNS Server:   {ip_info[3]}")
        if led:
            led.value(1) # เปิด LED ค้างไว้ถ้าเชื่อมต่อสำเร็จ
        return True
    else:
        final_status = nic.status()
        print("\n*** WiFi Connection Failed! ***")
        print(f"Final Wi-Fi status: {final_status} ({network_status_to_string(final_status)})")
        if led:
            blink_led(10, 50) # กระพริบเร็วๆ ถ้าเชื่อมต่อไม่ได้
        return False

def network_status_to_string(status):
    # ฟังก์ชันช่วยแปลงสถานะตัวเลขให้เป็นข้อความที่เข้าใจง่าย
    if status == network.STAT_IDLE:
        return "IDLE"
    elif status == network.STAT_CONNECTING:
        return "CONNECTING"
    elif status == network.STAT_WRONG_PASSWORD:
        return "WRONG_PASSWORD"
    elif status == network.STAT_NO_AP_FOUND:
        return "NO_AP_FOUND"
    elif status == network.STAT_CONNECT_FAIL:
        return "CONNECT_FAIL (General Error)"
    elif status == network.STAT_GOT_IP:
        return "GOT_IP (Connected)"
    else:
        return f"UNKNOWN ({status})"

# --- Main execution of the test script ---
gc.collect() # ทำ Garbage collection
test_wifi_connection()

print("\nWiFi test complete.")

# Loop forever to keep the board alive and LED state
while True:
    time.sleep(1)