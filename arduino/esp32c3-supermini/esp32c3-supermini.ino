#include <WiFi.h>
#include <ModbusIP_ESP8266.h>
#include <ModbusRTU.h>

// ======= CONFIG =======
#define SSID "wifi-ice"
#define PASSWORD "06062523"

// GPIO กำหนดขาเชื่อม MAX485
#define RXD2 21      // DI ของ MAX485 (RX)
#define TXD2 20      // RO ของ MAX485 (TX)
#define REDE 10      // DE และ RE ควบคุมทิศทาง (GPIO10)
#define LED_STATUS 8 // GPIO8 แสดงสถานะ WiFi (active low)

#define SLAVE_ID 1 // RTU Slave ID
#define RTU_START_REG 1
#define RTU_REG_COUNT 100
#define TCP_START_REG 100

ModbusRTU mbRTU;
ModbusIP mbTCP;

unsigned long lastReconnectAttempt = 0;
unsigned long lastRead = 0;

uint16_t rtuBuffer[RTU_REG_COUNT]; // buffer เก็บค่าจาก RTU

void connectWiFi()
{
  if (WiFi.status() != WL_CONNECTED)
  {
    Serial.println("WiFi not connected, trying to reconnect...");
    WiFi.begin(SSID, PASSWORD);
  }
}

void updateLEDStatus()
{
  static unsigned long lastToggle = 0;
  static bool ledState = false;

  if (WiFi.status() != WL_CONNECTED)
  {
    if (millis() - lastToggle > 300)
    {
      ledState = !ledState;
      digitalWrite(LED_STATUS, ledState);
      lastToggle = millis();
    }
  }
  else
  {
    digitalWrite(LED_STATUS, LOW); // active LOW = ON ติดค้าง
  }
}

void setup()
{
  Serial.begin(115200);
  Serial.println("Booting...");

  pinMode(LED_STATUS, OUTPUT);
  digitalWrite(LED_STATUS, HIGH); // ปิด LED เริ่มต้น

  WiFi.begin(SSID, PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
    updateLEDStatus();
  }

  Serial.println("\nWiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  Serial1.begin(9600, SERIAL_8N1, RXD2, TXD2);
  mbRTU.begin(&Serial1, REDE);
  mbRTU.master();

  mbTCP.server();

  // เตรียม register TCP ช่วง 100-199 (100 ตัว)
  for (int i = 0; i < RTU_REG_COUNT; i++)
  {
    mbTCP.addHreg(TCP_START_REG + i, 0);
  }

  Serial.println("Modbus TCP & RTU bridge initialized");
}

void loop()
{
  updateLEDStatus();

  if (millis() - lastReconnectAttempt > 30000)
  {
    lastReconnectAttempt = millis();
    connectWiFi();
  }

  // อ่านค่าทุก 10 วินาที
  if (millis() - lastRead > 10000)
  {
    lastRead = millis();

    // pullHreg อ่าน holding register จาก RTU slave
    if (mbRTU.readHreg(SLAVE_ID, RTU_START_REG, rtuBuffer, RTU_REG_COUNT))
    {
      // Serial.print("Read RTU registers, updating TCP registers IP: ");
      // Serial.println(WiFi.localIP());
      String msg = "Read RTU ID ";
      msg += String(SLAVE_ID);
      msg += " registers " + String(RTU_START_REG) + " - " + String(RTU_START_REG + RTU_REG_COUNT - 1);
      msg += " To TCP IP: " + WiFi.localIP().toString();
      msg += " registers " + String(TCP_START_REG) + " - " + String(TCP_START_REG + RTU_REG_COUNT - 1);

      Serial.println(msg);
      // update ค่า register TCP ตามข้อมูลที่อ่านได้
      for (int i = 0; i < RTU_REG_COUNT; i++)
      {
        mbTCP.Hreg(TCP_START_REG + i, rtuBuffer[i]);
      }
    }
    else
    {
      Serial.println("Failed to read RTU registers");
    }
  }

  mbRTU.task();
  mbTCP.task();

  delay(10);
}
