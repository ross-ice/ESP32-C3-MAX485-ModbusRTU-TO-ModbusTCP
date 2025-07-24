#include <WiFi.h>
#include <ModbusRTU.h>
#include <ModbusIP_ESP8266.h> // ใช้กับ ESP32 ได้ด้วย

// ---------- Wi-Fi Config ----------
const char* ssid = "your-ssid";
const char* password = "your-password";

// ---------- Modbus RTU (ผ่าน MAX485) ----------
ModbusRTU mbRTU;
HardwareSerial& modbusSerial = Serial1; // ใช้ UART1 บน ESP32-C3

#define MAX485_DE_RE 10 // ควบคุม DE/RE ของ MAX485 (GPIO10 หรือแล้วแต่บอร์ด)

// ---------- Modbus TCP ----------
ModbusIP mbTCP;

// ---------- Data Buffer ----------
uint16_t holdingRegister = 0;

// ---------- Setup ----------
void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("🔌 Starting Modbus Gateway...");

  // ---------- Wi-Fi ----------
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\n✅ Wi-Fi connected: " + WiFi.localIP().toString());

  // ---------- MAX485 UART Init ----------
  pinMode(MAX485_DE_RE, OUTPUT);
  digitalWrite(MAX485_DE_RE, LOW); // เริ่มในโหมดรับ

  modbusSerial.begin(9600, SERIAL_8N1, 4, 5); // RX=GPIO4, TX=GPIO5
  mbRTU.begin(&modbusSerial);
  mbRTU.setBaudrate(9600);
  mbRTU.setTransceiverMode(USART_RS485_HALF_DUPLEX);
  mbRTU.setDE(MAX485_DE_RE);

  // ตั้งค่า master และตั้ง polling target
  mbRTU.master();
  mbRTU.addHreg(1, 0); // RTU Slave ID = 1, register address = 0

  // ---------- Modbus TCP ----------
  mbTCP.server(); // เริ่ม TCP server
  mbTCP.addHreg(0); // เพิ่ม register สำหรับ Client TCP
}

// ---------- Loop ----------
void loop() {
  mbRTU.task();
  mbTCP.task();

  // อ่าน Holding Register จาก RTU slave ทุก 1 วินาที
  static uint32_t lastRead = 0;
  if (millis() - lastRead > 1000) {
    lastRead = millis();

    if (mbRTU.readHreg(1, 0, &holdingRegister, 1)) {
      Serial.print("📥 RTU Read: "); Serial.println(holdingRegister);
      mbTCP.Hreg(0, holdingRegister); // ส่งต่อไปยัง Modbus TCP register
    } else {
      Serial.println("⚠️ RTU Read failed");
    }
  }
}
