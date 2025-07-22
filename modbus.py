import network
import machine
import socket
import time

# --- WiFi Configuration ---
WIFI_SSID = "wifi-ice"
WIFI_PASSWORD = "06062523"
# ไม่ต้องประกาศ STATIC_IP แล้ว

def connect_wifi():
    print("Connecting to WiFi...", end="")
    nic = network.WLAN(network.STA_IF)
    nic.active(True)
    # ไม่ต้องเรียก nic.ifconfig(STATIC_IP)
    nic.connect(WIFI_SSID, WIFI_PASSWORD) # ESP32 จะพยายามรับ IP แบบ DHCP โดยอัตโนมัติ
    max_wait = 20
    while max_wait > 0:
        if nic.isconnected():
            break
        max_wait -= 1
        print(".", end="")
        time.sleep(1)
    if not nic.isconnected():
        raise RuntimeError('WiFi connection failed!')
    
    # แสดงข้อมูล IP ที่ได้รับจาก DHCP Server
    ip_info = nic.ifconfig()
    print("\nWiFi Connected!")
    print("IP Address:", ip_info[0])
    print("Subnet Mask:", ip_info[1])
    print("Gateway:", ip_info[2])
    print("DNS Server:", ip_info[3])
    return nic

# --- ส่วนอื่นๆ ของโค้ด (Modbus RTU, Modbus TCP Server) เหมือนเดิม ---

def main():
    global holding_registers

    # 1. Connect to WiFi
    try:
        nic_obj = connect_wifi() # รับ object ของ network interface กลับมา
        esp_ip = nic_obj.ifconfig()[0] # ดึง IP Address ที่ได้รับมา
    except Exception as e:
        print(f"Failed to connect to WiFi: {e}")
        return

    # 2. Initialize Modbus RTU Master
    # ...

    # 3. Initialize Modbus TCP Server
    tcp_server = ModbusTCPServer(esp_ip, 502, holding_registers) # ใช้ IP ที่ได้รับจาก DHCP
    
    # ...