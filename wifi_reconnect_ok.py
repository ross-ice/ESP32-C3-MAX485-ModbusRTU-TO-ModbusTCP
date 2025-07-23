import network
import time

SSID = 'wifi-ice'
PASSWORD = ''

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def connect():
    if not wlan.isconnected():
        print("เชื่อมต่อ Wi-Fi...")
        wlan.connect(SSID, PASSWORD)
        for i in range(20):
            status = wlan.status()
            print(f"ลองครั้งที่ {i+1}, status: {status}")
            if status == 1010:  # GOT_IP
                break
            time.sleep(1)

connect()

while True:
    if not wlan.isconnected():
        print("หลุดการเชื่อมต่อ, กำลัง reconnect...")
        connect()
    else:
        print("🟢 Connected:", wlan.ifconfig()[0])
    time.sleep(5)