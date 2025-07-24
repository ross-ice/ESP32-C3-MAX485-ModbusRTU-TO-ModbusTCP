import network, socket, struct, time
from machine import UART, Pin

# 🔧 Wi-Fi config
SSID = 'wifi-ice'
PASSWORD = '06062523'

# 🟢 LED แสดงสถานะ (GPIO8)
status_led = Pin(8, Pin.OUT)

# 📡 สร้างและเชื่อมต่อ Wi-Fi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def connect_wifi():
    if not wlan.isconnected():
        print("📶 Connecting Wi-Fi...")
        wlan.connect(SSID, PASSWORD)
        for i in range(20):
            if wlan.isconnected():
                break
            status_led.value(i % 2)  # กระพริบ
            time.sleep(1)
        status_led.value(0)

def update_led():
    if wlan.isconnected():
        status_led.value(0)  # ติดค้าง
    else:
        status_led.value(1)
        time.sleep(0.3)
        status_led.value(0)
        time.sleep(0.3)

# 🛠️ เรียกเชื่อมต่อ Wi-Fi
connect_wifi()
print("✅ Wi-Fi IP:", wlan.ifconfig()[0] if wlan.isconnected() else "❌ No connection")

# ⚙️ RS-485 / Modbus RTU config
uart = UART(1, baudrate=9600, tx=20, rx=21)
de = Pin(7, Pin.OUT)
de.value(0)

# 🔄 CRC16 สำหรับ Modbus RTU
def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc

# 📥 อ่านค่าจาก Modbus RTU slave
def modbus_read_holding(slave_id, start_addr, quantity, retries=3):
    func = 0x03
    req = struct.pack('>BBHH', slave_id, func, start_addr, quantity)
    req += struct.pack('<H', crc16(req))

    for attempt in range(retries):
        try:
            uart.read()  # flush buffer
            de.value(1)
            uart.write(req)
            time.sleep(0.01)
            de.value(0)

            time.sleep(0.1)
            resp = uart.read()
            if resp and len(resp) >= 5:
                # ✅ ตรวจสอบ CRC
                data, crc_received = resp[:-2], resp[-2:]
                crc_calc = struct.pack('<H', crc16(data))
                if crc_received == crc_calc:
                    return resp
                else:
                    print("⚠️ CRC mismatch")
            else:
                print(f"⚠️ Empty or short RTU response (try {attempt+1})")
        except Exception as e:
            print(f"❌ RTU error: {e}")
        time.sleep(0.1)

    print("⛔️ RTU retry failed")
    return None

# 🌐 Modbus TCP server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('', 502))
server.listen(1)
server.settimeout(1)  # ⏳ ป้องกัน loop ค้าง
print("🧭 TCP server started on port 502")

# 🔁 Loop: handle TCP request
while True:
    if not wlan.isconnected():
        print("🔄 Wi-Fi lost, reconnecting...")
        connect_wifi()
    update_led()

    try:
        client, addr = server.accept()
        print("🔌 TCP client:", addr)
        client.settimeout(3)

        req = client.recv(1024)
        if not req or len(req) < 12:
            client.close()
            continue

        trans_id = req[0:2]
        proto_id = req[2:4]
        length = req[4:6]
        unit_id = req[6]
        func_code = req[7]

        # ✅ รองรับเฉพาะ function code 0x03
        if func_code != 0x03:
            error_code = func_code | 0x80
            tcp_resp = trans_id + b'\x00\x00\x00\x03' + bytes([unit_id, error_code, 0x01])  # ILLEGAL FUNCTION
            client.send(tcp_resp)
            client.close()
            continue

        start = struct.unpack('>H', req[8:10])[0]
        qty = struct.unpack('>H', req[10:12])[0]

        rtu_resp = modbus_read_holding(unit_id, start, qty)
        if rtu_resp:
            # ลบ slave id (ตัวแรกของ rtu_resp)
            tcp_payload = bytes([unit_id]) + rtu_resp[1:-2]  # ไม่เอา CRC 2 bytes
            length_bytes = struct.pack('>H', len(tcp_payload))
            tcp_resp = trans_id + b'\x00\x00' + length_bytes + tcp_payload
            client.send(tcp_resp)
            print("✅ TCP response sent")
        else:
            error_code = func_code | 0x80
            tcp_resp = trans_id + b'\x00\x00\x00\x03' + bytes([unit_id, error_code, 0x0B])  # GATEWAY TARGET DEVICE FAILED TO RESPOND
            client.send(tcp_resp)

        client.close()

    except socket.timeout:
        pass  # ปล่อยให้ loop ทำงานต่อ
    except Exception as e:
        print("⚠️ TCP error:", e)
        time.sleep(1)
