#wifi.py
import network
import time

# กำหนดชื่อ Wi-Fi และรหัสผ่านของคุณ
SSID = 'wifi-ice'
PASSWORD = ''

# เริ่มต้นการเชื่อมต่อ Wi-Fi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

# รอให้เชื่อมต่อสำเร็จ
print("กำลังเชื่อมต่อ Wi-Fi...")
attempt = 0
while not wlan.isconnected() and attempt < 20:
    time.sleep(1)
    attempt += 1

# แสดงผลลัพธ์
if wlan.isconnected():
    print("เชื่อมต่อสำเร็จ!")
    print("IP address:", wlan.ifconfig()[0])
else:
    print("เชื่อมต่อไม่สำเร็จ 😓")