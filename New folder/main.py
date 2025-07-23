# main.py
import machine
import time
import network
import gc
from modbus_lib import ModbusRTUMaster, ModbusTCPServer 

# --- WiFi Configuration ---
WIFI_SSID = "wifi-ice"
WIFI_PASSWORD = "" 

# --- Modbus RTU Configuration ---
UART_ID = 1          
UART_TX_PIN = 5      
UART_RX_PIN = 4      
MAX485_DE_RE_PIN = 2 
MODBUS_RTU_BAUDRATE = 9600 
MODBUS_SLAVE_ID = 1      

# พื้นที่เก็บข้อมูลส่วนกลางสำหรับ Holding Registers
holding_registers = [0] * 100 

# --- LED Configuration ---
LED_PIN = 21 
led = None
try:
    led = machine.Pin(LED_PIN, machine.Pin.OUT)
    led.value(0) # Ensure LED is off initially
except Exception:
    led = None

def blink_led_main(times, duration_ms):
    if led:
        for _ in range(times):
            led.value(1)
            time.sleep_ms(duration_ms)
            led.value(0)
            time.sleep_ms(duration_ms)

def connect_wifi_main_startup(max_retries=30): # เพิ่ม retry และ LED feedback

    nic = network.WLAN(network.STA_IF)

    if nic.isconnected():
        ip_info = nic.ifconfig()
        print(f"main.py: Wi-Fi already connected. IP: {ip_info[0]}")
        if led: led.value(1) # ให้แน่ใจว่า LED เปิดอยู่ถ้าเชื่อมต่อ
        return ip_info[0]

    print(f"\nmain.py: Starting Wi-Fi connection to SSID: '{WIFI_SSID}'...")
    if led: led.value(0) # ปิด LED ขณะพยายามเชื่อมต่อ

    if not nic.active():
        nic.active(True)
        time.sleep_ms(100)

    nic.connect(WIFI_SSID, WIFI_PASSWORD)
    
    for i in range(1, max_retries + 1):
        if nic.isconnected():
            ip_info = nic.ifconfig()
            print(f"main.py: ✅ Wi-Fi Connected! IP: {ip_info[0]}")
            print(f"main.py: Subnet Mask: {ip_info[1]}")
            print(f"main.py: Gateway: {ip_info[2]}")
            print(f"main.py: DNS Server: {ip_info[3]}")
            if led: led.value(1) # เปิด LED ถ้าเชื่อมต่อสำเร็จ
            return ip_info[0]
        
        # แสดงสถานะดิบ
        current_status = nic.status()
        print(f"main.py: ➡️ ลองครั้งที่ {i}/{max_retries}, สถานะ: {current_status}")
        
        # กระพริบ LED ในขณะที่รอ
        if led:
            led.value(1) 
            time.sleep_ms(50)
            led.value(0)
            time.sleep_ms(950) # รอรวม 1 วินาทีต่อการลอง 1 ครั้ง
        else:
            time.sleep(1)

    print(f"main.py: ❌ Failed to connect Wi-Fi after {max_retries} attempts. Final status code: {nic.status()}")
    if led: blink_led_main(10, 50) # กระพริบเร็วๆ ถ้าเชื่อมต่อไม่ได้
    return None

def main():
    global holding_registers

    # 1. เชื่อมต่อ Wi-Fi (ตอนนี้จัดการใน main.py โดยตรง)
    esp_ip = connect_wifi_main_startup()
    if esp_ip is None: 
        print("main.py: Critical: Initial Wi-Fi connection failed. Resetting board in 10 seconds...")
        time.sleep(10)
        machine.reset() # รีเซ็ตบอร์ดหากเชื่อมต่อ Wi-Fi ไม่ได้
        return # จะไม่ถึงตรงนี้ เพราะรีเซ็ตไปแล้ว

    # 2. เริ่มต้น Modbus RTU Master
    rtu_master = None
    try:
        rtu_master = ModbusRTUMaster(UART_ID, UART_TX_PIN, UART_RX_PIN, MAX485_DE_RE_PIN, MODBUS_RTU_BAUDRATE, MODBUS_SLAVE_ID)
        print("main.py: Modbus RTU Master initialized.")
    except Exception as e:
        print(f"main.py: Failed to initialize Modbus RTU Master: {e}. Resetting board in 5 seconds...")
        time.sleep(5)
        machine.reset() 
        return

    # 3. เริ่มต้น Modbus TCP Server
    tcp_server = None
    try:
        tcp_server = ModbusTCPServer(esp_ip, 502, holding_registers) 
        print("main.py: Modbus TCP Server initialized.")
    except Exception as e:
        print(f"main.py: Failed to initialize Modbus TCP Server: {e}. Resetting board in 5 seconds...")
        time.sleep(5)
        machine.reset() 
        return

    last_rtu_read_time = time.ticks_ms()
    rtu_read_interval = 1000 # อ่าน Modbus RTU ทุก 1 วินาที

    print("main.py: Starting main loop...")
    while True:
        gc.collect() 

        # --- ตรวจสอบสถานะ Wi-Fi และ Reconnect (เหมือนเดิม) ---
        nic = network.WLAN(network.STA_IF)
        if not nic.isconnected():
            print("\nmain.py: !!! Wi-Fi disconnected. Attempting to reconnect...")
            if led: led.value(0) 
            esp_ip = connect_wifi_main_startup() # ใช้ฟังก์ชันเดิมในการ reconnect
            if esp_ip is None:
                print("main.py: 🔴 Reconnect failed. Modbus TCP will be down. Resetting board in 10 seconds...")
                if tcp_server:
                    try:
                        tcp_server.close() 
                    except Exception as e:
                        print(f"main.py: Error closing TCP socket: {e}")
                    tcp_server = None 
                time.sleep(10) 
                machine.reset() # รีเซ็ตบอร์ดหาก reconnect ไม่ได้
                continue 
            else: 
                print("main.py: ✅ Wi-Fi reconnected. Attempting to re-initialize Modbus TCP server.")
                if tcp_server is None:
                    try:
                        tcp_server = ModbusTCPServer(esp_ip, 502, holding_registers) 
                        print("main.py: Modbus TCP Server re-initialized.")
                    except Exception as e:
                        print(f"main.py: Failed to re-initialize Modbus TCP Server: {e}. Resetting board in 5 seconds...")
                        time.sleep(5)
                        machine.reset()
                        continue


        # --- Modbus TCP Server Polling ---
        if tcp_server and tcp_server.s: 
            tcp_server.poll_for_clients()

        # --- Modbus RTU Master Reading ---
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_rtu_read_time) >= rtu_read_interval:
            last_rtu_read_time = current_time

            if rtu_master: 
                try:
                    rtu_data = rtu_master.read_holding_registers(0, 100)
                    
                    if rtu_data:
                        # print(f"main.py: RTU data read: {rtu_data[0:5]}...") 
                        for i in range(len(rtu_data)):
                            if i < len(holding_registers):
                                holding_registers[i] = rtu_data[i] 
                    # else:
                        # print("main.py: Modbus RTU read returned no data or failed.")
                except Exception as e:
                    print(f"main.py: Error reading Modbus RTU: {e}")

        time.sleep_ms(10) 

if __name__ == "__main__":
    main()