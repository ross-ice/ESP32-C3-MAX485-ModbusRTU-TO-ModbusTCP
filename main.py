# main.py
import machine
import time
import network
import gc
from modbus_lib import ModbusRTUMaster, ModbusTCPServer # Import classes from our library

# --- WiFi Configuration ---
WIFI_SSID = "wifi-ice"      # <<<<< แก้ไขตรงนี้เป็นชื่อ WiFi ของคุณ
WIFI_PASSWORD = "06062523" # <<<<< แก้ไขตรงนี้เป็นรหัสผ่าน WiFi ของคุณ

# --- Modbus RTU Configuration ---
UART_ID = 1          # Use UART 1 for Modbus RTU
UART_TX_PIN = 5      # GPIO5 for UART1 TX (Check your ESP32-C3 pinout)
UART_RX_PIN = 4      # GPIO4 for UART1 RX (Check your ESP32-C3 pinout)
MAX485_DE_RE_PIN = 2 # GPIO2 for DE/RE of MAX485 (Check your wiring)
MODBUS_RTU_BAUDRATE = 9600 # <<<<< แก้ไขตาม Baud rate ของอุปกรณ์ Modbus RTU ของคุณ
MODBUS_SLAVE_ID = 1      # <<<<< แก้ไขตาม Slave ID ของอุปกรณ์ Modbus RTU ของคุณ

# Global data store for holding registers (to bridge RTU to TCP)
# Initialize with zeros for 100 registers
# Modbus registers are 16-bit (uint16_t in C, int in Python within range)
holding_registers = [0] * 100 

def connect_wifi_for_main():
    """Reconnects/checks WiFi status and returns IP. 
    Redundant if boot.py already handled it, but good for robustness."""
    nic = network.WLAN(network.STA_IF)
    if not nic.isconnected():
        print("WiFi was not connected, attempting to reconnect...")
        nic.active(True)
        nic.connect(network.WIFI_SSID, network.WIFI_PASSWORD) # Use constants from boot.py
        max_wait = 20
        while max_wait > 0:
            if nic.isconnected():
                break
            max_wait -= 1
            print(".", end="")
            time.sleep(1)
        if not nic.isconnected():
            raise RuntimeError('WiFi connection failed in main.py!')
    
    ip_info = nic.ifconfig()
    print("Main loop WiFi IP:", ip_info[0])
    return ip_info[0]

def main():
    global holding_registers

    # 1. Connect to WiFi (or confirm connection from boot.py)
    try:
        esp_ip = connect_wifi_for_main()
        if esp_ip is None:
            print("Failed to get IP, exiting main loop.")
            return
    except Exception as e:
        print(f"Failed to connect to WiFi in main: {e}")
        return

    # 2. Initialize Modbus RTU Master
    try:
        rtu_master = ModbusRTUMaster(UART_ID, UART_TX_PIN, UART_RX_PIN, MAX485_DE_RE_PIN, MODBUS_RTU_BAUDRATE, MODBUS_SLAVE_ID)
        print("Modbus RTU Master initialized.")
    except Exception as e:
        print(f"Failed to initialize Modbus RTU Master: {e}")
        return

    # 3. Initialize Modbus TCP Server
    try:
        tcp_server = ModbusTCPServer(esp_ip, 502, holding_registers)
        print("Modbus TCP Server initialized.")
    except Exception as e:
        print(f"Failed to initialize Modbus TCP Server: {e}")
        return

    last_rtu_read_time = time.ticks_ms()
    rtu_read_interval = 1000 # Read RTU every 1 second

    print("Starting main loop...")
    while True:
        gc.collect() # Periodically run garbage collection
        
        # Check for new Modbus TCP/IP client connections and process requests
        tcp_server.poll_for_clients()

        # Periodically read from Modbus RTU slave
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_rtu_read_time) >= rtu_read_interval:
            last_rtu_read_time = current_time
            # print("Reading from Modbus RTU slave...")
            
            try:
                # Read 100 holding registers starting from address 0
                rtu_data = rtu_master.read_holding_registers(0, 100)
                
                if rtu_data:
                    # Update the global holding_registers array that the TCP server uses
                    for i in range(len(rtu_data)):
                        if i < len(holding_registers): # Ensure we don't go out of bounds
                            holding_registers[i] = rtu_data[i]
                    # print("Modbus RTU read successful. Data updated.")
                    # print("Sample RTU Data (Reg 0-9):", holding_registers[0:10]) # For debugging
                else:
                    print("Modbus RTU read returned no data or failed.")
            except Exception as e:
                print(f"Error reading Modbus RTU: {e}")

        time.sleep_ms(10) # Small delay to yield to other tasks and avoid busy-waiting

if __name__ == "__main__":
    main()