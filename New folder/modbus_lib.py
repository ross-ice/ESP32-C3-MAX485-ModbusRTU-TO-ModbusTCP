# modbus_lib.py
import machine
import time
import struct
import socket
import sys

# --- Modbus RTU Master Implementation ---
class ModbusRTUMaster:
    def __init__(self, uart_id, tx_pin, rx_pin, de_re_pin, baudrate, slave_id):
        self.de_re_pin = machine.Pin(de_re_pin, machine.Pin.OUT)
        self.de_re_pin.value(0) # ตั้งค่าขา DE/RE เป็น LOW เพื่อเข้าสู่โหมดรับ (Receive Mode)
        
        # กำหนด UART ด้วยขา TX/RX ที่ถูกต้อง และตั้งค่า timeout สำหรับการรับส่งข้อมูล
        self.uart = machine.UART(uart_id, baudrate=baudrate, tx=tx_pin, rx=rx_pin, timeout=100, timeout_char=10)
        self.slave_id = slave_id

    def _calculate_crc(self, data):
        """คำนวณ Modbus RTU CRC (Cyclic Redundancy Check)"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if (crc & 0x0001):
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, 'little') # คืนค่า CRC แบบ Little-endian

    def read_holding_registers(self, start_address, quantity):
        if not (1 <= quantity <= 125): # ตรวจสอบจำนวน Register ที่สามารถอ่านได้ (FC03 สูงสุด 125)
            # print("Error: Quantity must be between 1 and 125.")
            return None

        # สร้าง ADU (Application Data Unit) สำหรับ Modbus RTU Request
        # ประกอบด้วย: Slave ID (1 byte) + Function Code (1 byte) + Start Address (2 bytes) + Quantity (2 bytes)
        pdu = bytearray([
            self.slave_id,
            0x03, # Function Code: Read Holding Registers (0x03)
            (start_address >> 8) & 0xFF, # Start Address High Byte
            start_address & 0xFF,       # Start Address Low Byte
            (quantity >> 8) & 0xFF,      # Quantity High Byte
            quantity & 0xFF            # Quantity Low Byte
        ])
        
        crc = self._calculate_crc(pdu) # คำนวณ CRC
        adu = pdu + crc # รวม PDU กับ CRC เพื่อสร้าง ADU

        self.de_re_pin.value(1) # ตั้งค่าขา DE/RE เป็น HIGH เพื่อเปิดใช้งานการส่ง (Transmit Mode)
        time.sleep_us(100) # หน่วงเวลาเล็กน้อยเพื่อให้ MAX485 สลับโหมด

        self.uart.write(adu) # ส่งคำขอ Modbus RTU ผ่าน UART

        # รอจนกว่าข้อมูลจะถูกส่งออกไปหมด (อาจไม่จำเป็นเสมอไป แต่ช่วยให้มั่นใจ)
        self.uart.flush() 

        time.sleep_us(100) # หน่วงเวลาเล็กน้อยก่อนสลับไปโหมดรับ
        self.de_re_pin.value(0) # ตั้งค่าขา DE/RE เป็น LOW เพื่อเปิดใช้งานการรับ (Receive Mode)

        # อ่าน Response จาก Modbus RTU Slave
        # Response ที่คาดหวัง: Slave ID (1) + FC (1) + Byte Count (1) + Data (2*quantity) + CRC (2)
        # ความยาวขั้นต่ำของ Response คือ 5 ไบต์ (ถ้ามีแค่ 1 Register + CRC)
        expected_len = 1 + 1 + 1 + (quantity * 2) + 2 

        response_buffer = bytearray(expected_len)
        bytes_read = 0
        
        # คำนวณ timeout based on UART settings (timeout และ timeout_char)
        timeout_ms = self.uart.timeout + self.uart.timeout_char * expected_len 
        start_time = time.ticks_ms()

        # วนลูปอ่านไบต์จนกว่าจะครบตามที่คาดหวัง หรือหมดเวลา
        while bytes_read < expected_len and time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            if self.uart.any(): # ตรวจสอบว่ามีข้อมูลในบัฟเฟอร์ UART หรือไม่
                byte = self.uart.read(1) # อ่านทีละ 1 ไบต์
                if byte:
                    response_buffer[bytes_read] = byte[0]
                    bytes_read += 1
            else:
                time.sleep_us(100) # หน่วงเวลาเล็กน้อยเพื่อไม่ให้ CPU ทำงานหนักเกินไป

        if bytes_read < 5: # Response สั้นเกินไปที่จะเป็น Modbus ที่ถูกต้อง
            # print(f"RTU response too short: {bytes_read} bytes. Raw: {response_buffer[:bytes_read].hex()}")
            return None # ไม่ใช่ Response ที่ถูกต้อง

        # ตรวจสอบ Response พื้นฐาน
        if response_buffer[0] != self.slave_id: # ตรวจสอบ Slave ID
            # print(f"RTU: Slave ID mismatch. Expected {self.slave_id}, Got {response_buffer[0]}")
            return None
        
        # ตรวจสอบว่าเป็นการตอบกลับแบบ Exception หรือไม่ (Function Code จะถูก OR ด้วย 0x80)
        if (response_buffer[1] & 0x80) == 0x80:
            exception_code = response_buffer[2]
            # print(f"RTU Exception: Function Code {response_buffer[1] & 0x7F}, Exception Code {exception_code}")
            return None

        if response_buffer[1] != 0x03: # ตรวจสอบ Function Code ว่าเป็น 0x03 หรือไม่
            # print(f"RTU: Function Code mismatch. Expected 0x03, Got {response_buffer[1]}")
            return None

        response_byte_count = response_buffer[2]
        if response_byte_count != (quantity * 2): # ตรวจสอบจำนวนไบต์ของข้อมูล
            # print(f"RTU: Byte count mismatch. Expected {quantity * 2}, Got {response_byte_count}")
            return None
        
        # ตรวจสอบ CRC
        received_crc = int.from_bytes(response_buffer[bytes_read-2:bytes_read], 'little')
        calculated_crc = int.from_bytes(self._calculate_crc(response_buffer[0:bytes_read-2]), 'little')
        
        if received_crc != calculated_crc:
            # print(f"RTU: CRC mismatch. Received 0x{received_crc:04X}, Calculated 0x{calculated_crc:04X}")
            return None

        # ดึงข้อมูล Register ออกมา (แต่ละ Register เป็น 16-bit)
        registers = []
        for i in range(quantity):
            # Registers เป็น 2 ไบต์ต่อหนึ่ง Register และเป็น Big-endian
            register_value = struct.unpack('>H', response_buffer[3 + i*2 : 3 + i*2 + 2])[0]
            registers.append(register_value)
            
        return registers

# --- Modbus TCP Server Implementation ---
class ModbusTCPServer:
    def __init__(self, ip, port, registers_data):
        self.ip = ip
        self.port = port
        self.registers = registers_data # อ้างอิงถึงลิสต์ holding_registers ส่วนกลาง
        self.s = None # Initialize socket to None
        self._setup_socket()

    def _setup_socket(self):
        try:
            if self.s:
                self.s.close() # ปิด socket เก่าถ้ามี
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # อนุญาตให้ใช้ Address ซ้ำได้
            self.s.bind((self.ip, self.port))
            self.s.listen(5) # ฟังการเชื่อมต่อได้สูงสุด 5 รายการ
            self.s.settimeout(0.1) # ตั้ง timeout สำหรับ accept เพื่อให้ไม่บล็อกโปรแกรมหลัก
            print(f"Modbus TCP Server listening on {self.ip}:{self.port}")
        except Exception as e:
            print(f"Error setting up Modbus TCP Server socket: {e}")
            self.s = None # ตั้งเป็น None ถ้ามีปัญหา

    def _process_modbus_request(self, request_adu):
        # โครงสร้าง Modbus TCP ADU:
        # Transaction ID (2 bytes)
        # Protocol ID (2 bytes, 0x0000 สำหรับ Modbus)
        # Length (2 bytes)
        # Unit ID (1 byte)
        # Function Code (1 byte)
        # Data ...

        if len(request_adu) < 8: # ความยาว ADU ขั้นต่ำ
            return None # คำขอไม่ถูกต้อง

        trans_id = int.from_bytes(request_adu[0:2], 'big')
        protocol_id = int.from_bytes(request_adu[2:4], 'big')
        length = int.from_bytes(request_adu[4:6], 'big')
        unit_id = request_adu[6]
        function_code = request_adu[7]

        response_pdu_data = b''
        exception_code = 0x00 # ไม่มี Exception (ค่าเริ่มต้น)

        if function_code == 0x03: # Read Holding Registers (Function Code 0x03)
            if len(request_adu) < 12: # ตรวจสอบความสมบูรณ์ของคำขอ FC03
                exception_code = 0x01 # Illegal Function (ความยาวไม่ถูกต้อง)
            else:
                start_reg = int.from_bytes(request_adu[8:10], 'big')
                num_regs = int.from_bytes(request_adu[10:12], 'big')
                
                # print(f"TCP Req: Read Holding Registers Start={start_reg}, Num={num_regs}")

                # ตรวจสอบความถูกต้องของ Address และ Quantity
                if not (0 <= start_reg < len(self.registers) and 
                        1 <= num_regs <= 125 and 
                        (start_reg + num_regs) <= len(self.registers)):
                    exception_code = 0x02 # Illegal Data Address
                else:
                    byte_count = num_regs * 2
                    response_pdu_data += byte_count.to_bytes(1, 'big') # เพิ่ม Byte Count ใน PDU
                    for i in range(num_regs):
                        # Pack ค่า Register เป็น 16-bit unsigned short (H) แบบ Big-endian (>)
                        response_pdu_data += struct.pack('>H', self.registers[start_reg + i])
        else:
            exception_code = 0x01 # Illegal Function (ฟังก์ชันโค้ดไม่รองรับ)

        # สร้าง Response ADU
        response_adu = bytearray()
        response_adu += trans_id.to_bytes(2, 'big') # Transaction ID
        response_adu += protocol_id.to_bytes(2, 'big') # Protocol ID (0x0000 สำหรับ Modbus TCP)

        if exception_code != 0x00:
            # สร้าง Exception Response PDU
            response_pdu = bytearray([
                unit_id,
                function_code | 0x80, # ตั้งค่า MSB เพื่อระบุว่าเป็น Exception
                exception_code
            ])
        else:
            # สร้าง Normal Response PDU
            response_pdu = bytearray([unit_id, function_code]) + response_pdu_data

        response_adu += len(response_pdu).to_bytes(2, 'big') # ความยาวของ PDU
        response_adu += response_pdu

        return response_adu

    def poll_for_clients(self):
        if not self.s: # ตรวจสอบว่า socket ถูกสร้างขึ้นมาอย่างถูกต้อง
            # print("Modbus TCP Server socket not initialized.")
            return

        try:
            conn, addr = self.s.accept() # พยายามรับการเชื่อมต่อใหม่ (ไม่บล็อกเนื่องจาก timeout)
            # print(f"Connection from {addr}")
            
            conn.settimeout(0.01) # ตั้ง timeout สำหรับ client socket เพื่อไม่ให้บล็อกโปรแกรมหลัก
            try:
                # อ่าน Modbus TCP ADU ทั้งหมด (สูงสุด 260 ไบต์)
                request_adu = conn.recv(260) 
                
                if request_adu: # ถ้าได้รับข้อมูล
                    response_adu = self._process_modbus_request(request_adu) # ประมวลผลคำขอ
                    if response_adu:
                        conn.sendall(response_adu) # ส่ง Response กลับไป
                # else:
                #     print(f"Client {addr} disconnected or sent no data.")

            except socket.timeout:
                pass # ไม่มีข้อมูลได้รับภายในเวลาที่กำหนด, ดำเนินการต่อ
            except OSError as e:
                # print(f"Error handling client {addr}: {e}")
                pass
            finally:
                conn.close() # ปิดการเชื่อมต่อหลังจากจัดการคำขอ (Modbus TCP เป็น stateless ต่อหนึ่ง Transaction)
                # print(f"Connection from {addr} closed.")
        except socket.timeout:
            pass # ไม่มี Client ใหม่กำลังรอ, ดำเนินการต่อ
        except OSError as e:
            # print(f"Server accept error: {e}")
            pass

    def close(self):
        if self.s:
            try:
                self.s.close()
                print("Modbus TCP Server socket closed.")
            except Exception as e:
                print(f"Error closing Modbus TCP socket: {e}")
            finally:
                self.s = None