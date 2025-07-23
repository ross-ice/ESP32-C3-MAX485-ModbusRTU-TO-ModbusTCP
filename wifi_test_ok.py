import network
import time

SSID = 'wifi-ice'
PASSWORD = ''

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

for i in range(20):
    print(f"รอบที่ {i+1}, isconnected: {wlan.isconnected()}, status: {wlan.status()}")
    if wlan.isconnected():
        break
    time.sleep(1)

if wlan.isconnected():
    print("✅ เชื่อมต่อสำเร็จ")
    print("IP:", wlan.ifconfig()[0])
else:
    print("❌ เชื่อมต่อไม่สำเร็จ")