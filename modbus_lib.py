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
        self.de_re_pin.value(0) # Start in receive mode
        
        # Ensure UART is initialized with the correct pins
        self.uart = machine.UART(uart_id, baudrate=baudrate, tx=tx_pin, rx=rx_pin, timeout=100, timeout_char=10)
        self.slave_id = slave_id

    def _calculate_crc(self, data):
        """Calculates Modbus RTU CRC."""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if (crc & 0x0001):
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, 'little') # Little-endian for Modbus CRC

    def read_holding_registers(self, start_address, quantity):
        if not (1 <= quantity <= 125): # Max registers for FC03
            print("Error: Quantity must be between 1 and 125.")
            return None

        # Build ADU (Application Data Unit)
        # Slave ID (1 byte) + Function Code (1 byte) + Start Address (2 bytes) + Quantity (2 bytes)
        pdu = bytearray([
            self.slave_id,
            0x03, # Function Code: Read Holding Registers
            (start_address >> 8) & 0xFF, # Start Address High Byte
            start_address & 0xFF,       # Start Address Low Byte
            (quantity >> 8) & 0xFF,      # Quantity High Byte
            quantity & 0xFF            # Quantity Low Byte
        ])
        
        crc = self._calculate_crc(pdu)
        adu = pdu + crc # Add CRC to the end

        self.de_re_pin.value(1) # Enable transmit
        time.sleep_us(100) # Small delay for MAX485 to switch modes

        self.uart.write(adu) # Send the Modbus RTU request

        # Wait for transmission to complete (optional, but good practice)
        self.uart.flush() 

        time.sleep_us(100) # Small delay before switching to receive
        self.de_re_pin.value(0) # Enable receive

        # Read response
        # Expected response: Slave ID (1) + FC (1) + Byte Count (1) + Data (2*quantity) + CRC (2)
        # Min length: 1 + 1 + 1 + 2 = 5 bytes (for 1 register + CRC)
        # Max length: 1 + 1 + 1 + 2*125 + 2 = 255 bytes
        expected_len = 1 + 1 + 1 + (quantity * 2) + 2 # Slave ID, FC, Byte Count, Data, CRC

        response_buffer = bytearray(expected_len)
        bytes_read = 0
        start_time = time.ticks_ms()
        timeout_ms = self.uart.timeout + self.uart.timeout_char * expected_len # Use UART timeouts

        while bytes_read < expected_len and time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            if self.uart.any():
                # Read one byte at a time to manage buffer, or try to read all available
                byte = self.uart.read(1) 
                if byte:
                    response_buffer[bytes_read] = byte[0]
                    bytes_read += 1
            else:
                time.sleep_us(100) # Small sleep to yield CPU

        if bytes_read < 5: # Minimum response length for error or actual data
            # print(f"RTU response too short: {bytes_read} bytes. Raw: {response_buffer[:bytes_read].hex()}")
            return None # Not enough data for a valid response

        # Basic response validation
        if response_buffer[0] != self.slave_id:
            # print(f"RTU: Slave ID mismatch. Expected {self.slave_id}, Got {response_buffer[0]}")
            return None
        
        # Check for exception response (FC | 0x80)
        if (response_buffer[1] & 0x80) == 0x80:
            exception_code = response_buffer[2]
            # print(f"RTU Exception: Function Code {response_buffer[1] & 0x7F}, Exception Code {exception_code}")
            return None

        if response_buffer[1] != 0x03: # Check Function Code
            # print(f"RTU: Function Code mismatch. Expected 0x03, Got {response_buffer[1]}")
            return None

        response_byte_count = response_buffer[2]
        if response_byte_count != (quantity * 2):
            # print(f"RTU: Byte count mismatch. Expected {quantity * 2}, Got {response_byte_count}")
            return None
        
        # Validate CRC
        received_crc = int.from_bytes(response_buffer[bytes_read-2:bytes_read], 'little')
        calculated_crc = int.from_bytes(self._calculate_crc(response_buffer[0:bytes_read-2]), 'little')
        
        if received_crc != calculated_crc:
            # print(f"RTU: CRC mismatch. Received 0x{received_crc:04X}, Calculated 0x{calculated_crc:04X}")
            return None

        # Extract data (16-bit registers)
        registers = []
        for i in range(quantity):
            # Registers are 2 bytes each, big-endian
            register_value = struct.unpack('>H', response_buffer[3 + i*2 : 3 + i*2 + 2])[0]
            registers.append(register_value)
            
        return registers

# --- Modbus TCP Server Implementation ---
class ModbusTCPServer:
    def __init__(self, ip, port, registers_data):
        self.ip = ip
        self.port = port
        self.registers = registers_data # Reference to the global holding_registers list
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow reusing the address
        self.s.bind((self.ip, self.port))
        self.s.listen(5)
        self.s.settimeout(0.1) # Set a timeout for accept to make it non-blocking
        print(f"Modbus TCP Server listening on {self.ip}:{self.port}")

    def _process_modbus_request(self, request_adu):
        # Transaction ID (2 bytes)
        # Protocol ID (2 bytes, 0x0000 for Modbus)
        # Length (2 bytes)
        # Unit ID (1 byte)
        # Function Code (1 byte)
        # Data ...

        if len(request_adu) < 8: # Minimum ADU length
            return None # Invalid request

        trans_id = int.from_bytes(request_adu[0:2], 'big')
        protocol_id = int.from_bytes(request_adu[2:4], 'big')
        length = int.from_bytes(request_adu[4:6], 'big')
        unit_id = request_adu[6]
        function_code = request_adu[7]

        response_pdu_data = b''
        exception_code = 0x00 # No exception

        if function_code == 0x03: # Read Holding Registers
            if len(request_adu) < 12: # Check for complete FC03 request
                exception_code = 0x01 # Illegal Function
            else:
                start_reg = int.from_bytes(request_adu[8:10], 'big')
                num_regs = int.from_bytes(request_adu[10:12], 'big')
                
                # print(f"TCP Req: Read Holding Registers Start={start_reg}, Num={num_regs}")

                if not (0 <= start_reg < len(self.registers) and 1 <= num_regs <= 125 and (start_reg + num_regs) <= len(self.registers)):
                    exception_code = 0x02 # Illegal Data Address
                else:
                    byte_count = num_regs * 2
                    response_pdu_data += byte_count.to_bytes(1, 'big')
                    for i in range(num_regs):
                        # Pack 16-bit unsigned short (H) in big-endian (>)
                        response_pdu_data += struct.pack('>H', self.registers[start_reg + i])
        else:
            exception_code = 0x01 # Illegal Function

        # Construct response ADU
        response_adu = bytearray()
        response_adu += trans_id.to_bytes(2, 'big')
        response_adu += protocol_id.to_bytes(2, 'big') # Always 0x0000 for standard Modbus TCP

        if exception_code != 0x00:
            # Exception response
            response_pdu = bytearray([
                unit_id,
                function_code | 0x80, # Set MSB for exception
                exception_code
            ])
        else:
            # Normal response
            response_pdu = bytearray([unit_id, function_code]) + response_pdu_data

        response_adu += len(response_pdu).to_bytes(2, 'big') # Length of PDU
        response_adu += response_pdu

        return response_adu

    def poll_for_clients(self):
        try:
            conn, addr = self.s.accept() # Accepts a new connection
            # print(f"Connection from {addr}")
            
            # Set a short timeout for the client socket to avoid blocking indefinitely
            conn.settimeout(0.01) 
            try:
                # Read entire Modbus TCP ADU (max 260 bytes, but can be smaller)
                # A full Modbus TCP ADU can be up to 260 bytes (MBAP Header 7 bytes + PDU 253 bytes)
                request_adu = conn.recv(260) 
                
                if request_adu:
                    response_adu = self._process_modbus_request(request_adu)
                    if response_adu:
                        conn.sendall(response_adu)
                # else:
                #     print(f"Client {addr} disconnected or sent no data.")

            except socket.timeout:
                pass # No data received within timeout, just continue
            except OSError as e:
                # print(f"Error handling client {addr}: {e}")
                pass
            finally:
                conn.close() # Close connection after handling request (Modbus TCP is stateless per transaction)
                # print(f"Connection from {addr} closed.")
        except socket.timeout:
            pass # No new client waiting, just continue
        except OSError as e:
            # print(f"Server accept error: {e}")
            pass