import network # สำหรับ Wi-Fi
import machine # สำหรับควบคุม GPIO และ UART
import socket  # สำหรับ TCP/IP
import time    # สำหรับจัดการเวลา

# คุณจะต้องอัปโหลด/อิมพอร์ตไลบรารี Modbus RTU master และ Modbus TCP server ของคุณ
# ตัวอย่างเช่น ถ้าคุณมี 'modbus_rtu_master.py' และ 'modbus_tcp_server.py'
# from modbus_rtu_master import ModbusRTUMaster
# from modbus_tcp_server import ModbusTCPServer

# --- การตั้งค่า Wi-Fi ---
WIFI_SSID = "wifi-ice" # เปลี่ยนเป็นชื่อ Wi-Fi ของคุณ
WIFI_PASSWORD = "06062523" # เปลี่ยนเป็นรหัสผ่าน Wi-Fi ของคุณ
STATIC_IP = ('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8') # IP, Subnet, Gateway, DNS

# --- การตั้งค่า Modbus RTU ---
UART_ID = 1          # ใช้ UART 1 สำหรับ Modbus RTU
UART_TX_PIN = 5      # GPIO5 สำหรับ UART1 TX
UART_RX_PIN = 4      # GPIO4 สำหรับ UART1 RX
MAX485_DE_RE_PIN = 2 # GPIO2 สำหรับขา DE/RE ของ MAX485
MODBUS_RTU_BAUDRATE = 9600 # อัตรา Baud rate ของอุปกรณ์ Modbus RTU ของคุณ
MODBUS_SLAVE_ID = 1

# พื้นที่เก็บข้อมูลส่วนกลางสำหรับ Holding Registers (สำหรับเชื่อมข้อมูล RTU ไปยัง TCP)
# เริ่มต้นด้วยศูนย์สำหรับ 100 registers
holding_registers = [0] * 100

def connect_wifi():
    print("กำลังเชื่อมต่อ WiFi...", end="")
    nic = network.WLAN(network.STA_IF)
    nic.active(True)
    nic.ifconfig(STATIC_IP) # ตั้งค่า IP แบบ Static
    nic.connect(WIFI_SSID, WIFI_PASSWORD)
    max_wait = 20 # รอนานสุด 20 วินาที
    while max_wait > 0:
        if nic.isconnected():
            break
        max_wait -= 1
        print(".", end="")
        time.sleep(1)
    if not nic.isconnected():
        raise RuntimeError('การเชื่อมต่อ WiFi ล้มเหลว!')
    print("\nWiFi เชื่อมต่อแล้ว! IP:", nic.ifconfig()[0])
    return nic

# --- ฟังก์ชันช่วยสำหรับ Modbus RTU ---
# ส่วนนี้ขึ้นอยู่กับไลบรารี Modbus RTU ที่คุณเลือกอย่างมาก
class RTUMaster:
    def __init__(self, uart_id, tx_pin, rx_pin, de_re_pin, baudrate, slave_id):
        self.de_re_pin = machine.Pin(de_re_pin, machine.Pin.OUT)
        self.de_re_pin.value(0) # เริ่มต้นในโหมดรับ (receive)
        self.uart = machine.UART(uart_id, baudrate=baudrate, tx=tx_pin, rx=rx_pin)
        self.slave_id = slave_id
        # เริ่มต้นไลบรารี ModbusRTU master ของคุณที่นี่
        # ตัวอย่าง: self.modbus_master = ModbusRTUMaster(self.uart, self.de_re_pin)

    def read_holding_registers(self, start_address, quantity):
        self.de_re_pin.value(1) # เปิดใช้งานการส่ง (transmit)
        time.sleep_us(100) # หน่วงเวลาเล็กน้อยให้ฮาร์ดแวร์สลับโหมด
        # ตัวอย่าง: response = self.modbus_master.read_holding_registers(self.slave_id, start_address, quantity)
        # ตรงนี้จะเป็นเมธอดของไลบรารี ModbusRTU ที่คุณเลือกใช้
        # เพื่อความง่าย ลองจำลองข้อมูลไปก่อน
        dummy_data = [i + 1 for i in range(quantity)] # จำลองการอ่านค่าที่เพิ่มขึ้นเรื่อยๆ
        time.sleep_us(100) # หน่วงเวลาเล็กน้อยให้ฮาร์ดแวร์สลับโหมด
        self.de_re_pin.value(0) # เปิดใช้งานการรับ (receive)
        return dummy_data # คืนค่าเป็น list ของ register values

# --- ตรรกะของ Modbus TCP Server ---
# ส่วนนี้ก็ขึ้นอยู่กับไลบรารี Modbus TCP เฉพาะ หรือถ้าคุณเขียนเอง
# ตัวอย่าง Modbus TCP server อย่างง่ายสำหรับ holding registers
class ModbusTCPServer:
    def __init__(self, ip, port, registers_data):
        self.ip = ip
        self.port = port
        self.registers = registers_data # อ้างอิงถึง list holding_registers ส่วนกลาง
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind((self.ip, self.port))
        self.s.listen(5) # รองรับการเชื่อมต่อสูงสุด 5 รายการ
        print(f"Modbus TCP Server กำลังรอการเชื่อมต่อบน {self.ip}:{self.port}")

    def handle_client(self, conn, addr):
        print(f"มีการเชื่อมต่อจาก {addr}")
        try:
            while True:
                data = conn.recv(256) # อ่านข้อมูลได้สูงสุด 256 ไบต์ (Modbus ADU)
                if not data:
                    break # ไม่มีข้อมูลเข้ามาแล้ว ตัดการเชื่อมต่อ

                # การ parse Modbus TCP แบบง่าย (ทำให้ง่ายขึ้นสำหรับตัวอย่าง)
                # Transaction ID (2 ไบต์)
                # Protocol ID (2 ไบต์, 0x0000 สำหรับ Modbus)
                # Length (2 ไบต์)
                # Unit ID (1 ไบต์)
                # Function Code (1 ไบต์)
                # Data ...
                trans_id = int.from_bytes(data[0:2], 'big')
                protocol_id = int.from_bytes(data[2:4], 'big')
                length = int.from_bytes(data[4:6], 'big')
                unit_id = data[6]
                function_code = data[7]

                response = b''
                if function_code == 0x03: # อ่าน Holding Registers
                    start_reg = int.from_bytes(data[8:10], 'big')
                    num_regs = int.from_bytes(data[10:12], 'big')
                    print(f"อ่าน Holding Registers: เริ่มต้น={start_reg}, จำนวน={num_regs}")

                    if start_reg + num_regs <= len(self.registers):
                        # สร้าง Response
                        response_data = b''
                        for i in range(num_regs):
                            # ตรวจสอบให้แน่ใจว่าค่าอยู่ในช่วง 16 บิต ถ้าจำเป็น
                            response_data += self.registers[start_reg + i].to_bytes(2, 'big')
                        
                        byte_count = len(response_data)
                        response = trans_id.to_bytes(2, 'big') + \
                                   (0x0000).to_bytes(2, 'big') + \
                                   (3 + byte_count).to_bytes(2, 'big') + \
                                   unit_id.to_bytes(1, 'big') + \
                                   function_code.to_bytes(1, 'big') + \
                                   byte_count.to_bytes(1, 'big') + \
                                   response_data
                    else:
                        # Error response สำหรับ Illegal data address
                        response = trans_id.to_bytes(2, 'big') + \
                                   (0x0000).to_bytes(2, 'big') + \
                                   (3).to_bytes(2, 'big') + \
                                   unit_id.to_bytes(1, 'big') + \
                                   (function_code | 0x80).to_bytes(1, 'big') + \
                                   (0x02).to_bytes(1, 'big') # Illegal Data Address
                else:
                    # Generic error สำหรับ unsupported function code
                    response = trans_id.to_bytes(2, 'big') + \
                               (0x0000).to_bytes(2, 'big') + \
                               (3).to_bytes(2, 'big') + \
                               unit_id.to_bytes(1, 'big') + \
                               (function_code | 0x80).to_bytes(1, 'big') + \
                               (0x01).to_bytes(1, 'big') # Illegal Function

                if response:
                    conn.sendall(response)
        except OSError as e:
            print(f"ข้อผิดพลาดในการเชื่อมต่อ: {e}")
        finally:
            conn.close()
            print(f"ปิดการเชื่อมต่อจาก {addr} แล้ว")

    def poll_for_clients(self):
        try:
            # ตั้ง timeout เพื่อให้ accept ไม่บล็อกตลอดไป
            self.s.settimeout(0.01)
            conn, addr = self.s.accept()
            # เป็นการดีกว่าที่จะจัดการ client แบบ non-blocking หรือใน thread/task แยกต่างหาก
            # แต่เพื่อความง่ายใน loop, เราเรียกโดยตรง
            self.handle_client(conn, addr)
        except OSError as e:
            if e.args[0] == 11: # errno 11 = EAGAIN, ไม่มี client กำลังรอ
                pass
            else:
                print(f"ข้อผิดพลาดในการรับการเชื่อมต่อของ Server: {e}")


# --- Loop หลัก ---
def main():
    global holding_registers

    # 1. เชื่อมต่อ Wi-Fi
    try:
        connect_wifi()
    except Exception as e:
        print(f"ไม่สามารถเชื่อมต่อ Wi-Fi: {e}")
        return

    # 2. เริ่มต้น Modbus RTU Master
    rtu_master = RTUMaster(UART_ID, UART_TX_PIN, UART_RX_PIN, MAX485_DE_RE_PIN, MODBUS_RTU_BAUDRATE, MODBUS_SLAVE_ID)

    # 3. เริ่มต้น Modbus TCP Server
    tcp_server = ModbusTCPServer(STATIC_IP[0], 502, holding_registers)

    last_rtu_read_time = time.ticks_ms()
    rtu_read_interval = 1000 # อ่าน RTU ทุก 1 วินาที

    while True:
        # ตรวจสอบการเชื่อมต่อ client Modbus TCP/IP ใหม่ๆ
        tcp_server.poll_for_clients()

        # อ่านข้อมูลจาก Modbus RTU slave เป็นระยะ
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_rtu_read_time) >= rtu_read_interval:
            last_rtu_read_time = current_time
            print("กำลังอ่านข้อมูลจาก Modbus RTU slave...")
            try:
                # ตรงนี้จะเรียกไลบรารี Modbus RTU เพื่ออ่านค่า
                rtu_data = rtu_master.read_holding_registers(0, 100)
                if rtu_data:
                    # อัปเดตอาร์เรย์ holding_registers ส่วนกลางที่ TCP server ใช้
                    for i in range(len(rtu_data)):
                        holding_registers[i] = rtu_data[i]
                    print("อ่าน Modbus RTU สำเร็จ. ข้อมูลถูกอัปเดตแล้ว.")
                else:
                    print("การอ่าน Modbus RTU ไม่ได้คืนค่าข้อมูล.")
            except Exception as e:
                print(f"ข้อผิดพลาดในการอ่าน Modbus RTU: {e}")

        time.sleep_ms(10) # หน่วงเวลาเล็กน้อย เพื่อให้งานอื่นๆ ทำงานได้และไม่ใช้ CPU ตลอดเวลา

if __name__ == "__main__":
    main()