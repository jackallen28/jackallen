// CircuitPath kit check: uses every library the projects need, so a board
// that compiles this has everything a student will use. The Pi compiles it
// for every board after installing or updating the Arduino tools (which
// also fills the build cache, so students' first compiles are quick).

#include <Wire.h>
#include <SPI.h>
#include <Adafruit_NeoPixel.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>
#include <TM1637Display.h>
#include <Keypad.h>
#include <MFRC522.h>
#include <LedControl.h>

#if defined(ESP32)
#include <ESP32Servo.h>
#include <WiFi.h>
#include <WebServer.h>
#include <esp_now.h>
WebServer server(80);
#elif defined(ESP8266)
#include <Servo.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <espnow.h>
ESP8266WebServer server(80);
#else
#include <Servo.h>
#include <LiquidCrystal_I2C.h> // Keypad Safe (Uno / Mega)
LiquidCrystal_I2C lcd(0x27, 16, 2);
#endif

Adafruit_NeoPixel pixels(12, 2, NEO_GRB + NEO_KHZ800);
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
DHT dht(3, DHT11);
TM1637Display digits(4, 5);
MFRC522 rfid(10, 9);
LedControl matrix(7, 6, 8, 1);
Servo servo;

const byte ROWS = 4;
const byte COLS = 4;
char keys[ROWS][COLS] = {
  {'1', '2', '3', 'A'},
  {'4', '5', '6', 'B'},
  {'7', '8', '9', 'C'},
  {'*', '0', '#', 'D'},
};
byte rowPins[ROWS] = {0, 1, 2, 3};
byte colPins[COLS] = {4, 5, 6, 7};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

void setup() {
  Serial.begin(115200);
  pixels.begin();
  pixels.setPixelColor(0, pixels.Color(0, 150, 150));
  pixels.show();
  if (oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    oled.clearDisplay();
    oled.setTextColor(SSD1306_WHITE);
    oled.println(F("Hello!"));
    oled.display();
  }
  dht.begin();
  digits.setBrightness(7);
  digits.showNumberDec(42);
  SPI.begin();
  rfid.PCD_Init();
  matrix.shutdown(0, false);
  matrix.setLed(0, 1, 1, true);
  servo.attach(9);
  servo.write(90);
#if defined(ESP32) || defined(ESP8266)
  WiFi.mode(WIFI_STA);
  esp_now_init();
  server.on("/", []() { server.send(200, "text/plain", "Hello!"); });
  server.begin();
#else
  lcd.init();
  lcd.backlight();
  lcd.print("Hello!");
#endif
}

void loop() {
  char key = keypad.getKey();
  if (key) Serial.println(key);
  float t = dht.readTemperature();
  if (!isnan(t)) Serial.println(t);
  if (rfid.PICC_IsNewCardPresent()) Serial.println(F("card"));
#if defined(ESP32) || defined(ESP8266)
  server.handleClient();
#endif
  delay(10);
}
