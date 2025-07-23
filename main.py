# main.py
import machine
import time
import network
import gc
# นำเข้าคลาส Modbus ที่เราสร้างไว้ในไฟล์ modbus_lib.py
from modbus_lib import ModbusRTUMaster, ModbusTCPServer 

# --- WiFi Configuration (จำเป็นต้องมีใน main.py ด้วย เผื่อกรณี main.py รันเดี่ยวๆ หรือรีเซ็ต) ---
WIFI_SSID = "wifi-ice"
WIFI_PASSWORD = "" # <<<<< ยืนยันว่าไม่มีรหัสผ่านสำหรับ wifi-ice

# --- Modbus RTU Configuration ---
UART_ID = 1          # ใช้ UART 1 สำหรับ Modbus RTU (GPIO4/5)
UART_TX_PIN = 5      # GPIO5 สำหรับ UART1 TX
UART_RX_PIN = 4      # GPIO4 สำหรับ UART1 RX
MAX485_DE_RE_PIN = 2 # GPIO2 สำหรับขา DE/RE ของ MAX485
MODBUS_RTU_BAUDRATE = 9600 # <<<<< แก้ไขตาม Baud rate ของอุปกรณ์ Modbus RTU ของคุณ
MODBUS_SLAVE_ID = 1      # <<<<< แก้ไขตาม Slave ID ของอุปกรณ์ Modbus RTU ของคุณ

# พื้นที่เก็บข้อมูลส่วนกลางสำหรับ Holding Registers (เพื่อเชื่อมข้อมูลจาก RTU ไป TCP)
holding_registers = [0] * 100 

def connect_wifi_for_main():
    """เชื่อมต่อ Wi-Fi หรือยืนยันสถานะการเชื่อมต่อ และคืนค่า IP Address"""
    nic = network.WLAN(network.STA_IF)
    if not nic.isconnected(): # หาก Wi-Fi ไม่ได้เชื่อมต่อ (เช่น หลังจาก Soft Reboot)
        print("main.py: WiFi was not connected, attempting to reconnect...")
        nic.active(True)
        # ไม่มี nic.config(txpower=...) ที่นี่เช่นกัน
        nic.connect(WIFI_SSID, WIFI_PASSWORD)
        max_wait = 20
        while max_wait > 0:
            if nic.isconnected():
                break
            max_wait -= 1
            print(".", end="")
            time.sleep(1)
        if not nic.isconnected():
            status = nic.status()
            raise RuntimeError(f"main.py: WiFi connection failed: Status {status}")
    
    ip_info = nic.ifconfig()
    print("main.py: WiFi IP:", ip_info[0])
    return ip_info[0]

def main():
    global holding_registers

    # 1. เชื่อมต่อ Wi-Fi (หรือยืนยันการเชื่อมต่อจาก boot.py)
    try:
        esp_ip = connect_wifi_for_main()
        if esp_ip is None:
            print("main.py: Failed to get IP, exiting main loop.")
            return
    except Exception as e:
        print(f"main.py: Failed to connect to WiFi in main: {e}")
        return

    # 2. เริ่มต้น Modbus RTU Master
    try:
        rtu_master = ModbusRTUMaster(UART_ID, UART_TX_PIN, UART_RX_PIN, MAX485_DE_RE_PIN, MODBUS_RTU_BAUDRATE, MODBUS_SLAVE_ID)
        print("main.py: Modbus RTU Master initialized.")
    except Exception as e:
        print(f"main.py: Failed to initialize Modbus RTU Master: {e}")
        return

    # 3. เริ่มต้น Modbus TCP Server
    try:
        tcp_server = ModbusTCPServer(esp_ip, 502, holding_registers) 
        print("main.py: Modbus TCP Server initialized.")
    except Exception as e:
        print(f"main.py: Failed to initialize Modbus TCP Server: {e}")
        return

    last_rtu_read_time = time.ticks_ms()
    rtu_read_interval = 1000 # อ่าน Modbus RTU ทุก 1 วินาที (สามารถปรับได้)

    print("main.py: Starting main loop...")
    while True:
        gc.collect()
        
        tcp_server.poll_for_clients()

        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_rtu_read_time) >= rtu_read_interval:
            last_rtu_read_time = current_time

            try:
                rtu_data = rtu_master.read_holding_registers(0, 100)
                
                if rtu_data:
                    for i in range(len(rtu_data)):
                        if i < len(holding_registers):
                            holding_registers[i] = rtu_data[i]
                else:
                    print("main.py: Modbus RTU read returned no data or failed.")
            except Exception as e:
                print(f"main.py: Error reading Modbus RTU: {e}")

        time.sleep_ms(10)

if __name__ == "__main__":
    main()