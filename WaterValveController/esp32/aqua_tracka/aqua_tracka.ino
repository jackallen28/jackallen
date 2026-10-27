/*
  Aqua Tracka - Wi-Fi dashboard for the Water Valve Controller
  =============================================================
  Waveshare ESP32-C3-Zero (any ESP32-C3 board works) next to the Arduino Nano.

  - Makes its own Wi-Fi network VAT_Aqua_Tracka (no password, see AP_PASSWORD)
    and serves the dashboard at http://192.168.4.1. Phones that show a
    "sign in to network" message open the dashboard from it.
  - Reads the Nano's status and settings lines on GPIO20 (from Nano D11) and
    sends the web page's commands to the Nano on GPIO21 (to Nano D12), 9600 baud.
  - The dashboard shows the water count, flow rate, limit and valve, and has
    calibration, all the settings, diagnostics, an event log and instructions.
  - The USB port prints a status line every 2 seconds (Serial Monitor, 115200).

  The web page itself is in web/index.html; tools/make_page.py packs it into
  web_page.h. Build: board "ESP32C3 Dev Module", USB CDC On Boot: Enabled.
  See README.md for flashing the ready-made .bin from a web browser.
*/

#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <esp_random.h>

#include "web_page.h"

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
const char *AP_NAME     = "VAT_Aqua_Tracka";
const char *AP_PASSWORD = "";          // "" = open network; or 8+ characters to need a password
const uint8_t AP_CHANNEL = 6;
const IPAddress AP_IP(192, 168, 4, 1);

// Lower transmit power keeps many small ESP32-C3 boards stable (some reset or
// drop the network at full power). Raise it if the phone loses the network
// a few metres away: WIFI_POWER_11dBm, WIFI_POWER_15dBm, WIFI_POWER_19_5dBm.
const wifi_power_t WIFI_POWER = WIFI_POWER_8_5dBm;

const int NANO_RX_PIN = 20;            // from Nano D11 (through the divider)
const int NANO_TX_PIN = 21;            // to Nano D12 (through 1 kOhm)
const long NANO_BAUD = 9600;

const char *ESP_VERSION = "1.0";

// ---------------------------------------------------------------------------
// Timing
// ---------------------------------------------------------------------------
const unsigned long LINK_LOST_MS      = 5000;    // no good line for this long = link lost
const unsigned long COMMAND_RETRY_MS  = 2500;    // no answer: send again
const uint8_t       COMMAND_TRIES     = 4;
const unsigned long COMMAND_EXPIRY_MS = 15000;   // a command waiting this long fails
const unsigned long HISTORY_STEP_MS   = 2000;    // one flow sample every 2 s
const unsigned long DEBUG_MS          = 2000;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
WebServer server(80);
DNSServer dns;
HardwareSerial &nano = Serial1;

char rxLine[300];
size_t rxLength = 0;
bool rxOverflow = false;

String statusLine;                     // the Nano's latest good lines, sent to the page as they are
String configLine;
unsigned long statusAt = 0;
unsigned long configAt = 0;
unsigned long lastByteAt = 0;
uint32_t bytesReceived = 0;
uint32_t goodLines = 0;
uint32_t badLines = 0;
long nanoUptime = -1;
bool linkUp = false;

// Commands from the page, sent one at a time; the Nano answers with
// "ack" (the command's number) and "ok" (the result) in its status line.
enum CommandState : uint8_t { CMD_QUEUED, CMD_SENT, CMD_DONE, CMD_REJECTED, CMD_BUSY, CMD_UNKNOWN, CMD_FAILED };

struct Command {
  uint16_t id;
  char body[96];
  CommandState state;
  uint8_t tries;
  unsigned long queuedAt;
  unsigned long sentAt;
};

const uint8_t QUEUE_SIZE = 12;
Command queue[QUEUE_SIZE];             // waiting, oldest first
uint8_t queueCount = 0;
struct Result { uint16_t id; CommandState state; };
Result results[16];                    // finished, newest last, for the page
uint8_t resultCount = 0;
uint16_t nextId = 1;
uint32_t commandsSent = 0;
uint32_t commandRetries = 0;
uint32_t commandsFailed = 0;

// Event log: the Nano's events plus the ESP's own (codes from 100).
struct LogEntry { unsigned long at; uint8_t code; uint8_t source; long extra; };
const uint8_t LOG_SIZE = 40;
LogEntry eventLog[LOG_SIZE];
uint8_t logCount = 0;
uint8_t logHead = 0;                   // next slot to write
long lastEventNumber = -1;
const uint8_t EV_ESP_START = 100, EV_LINK_UP = 101, EV_LINK_LOST = 102;
const uint8_t SRC_ESP = 9;

// Flow history in L/min x 100.
const uint16_t HISTORY_SIZE = 150;     // 5 minutes
uint16_t history[HISTORY_SIZE];
uint16_t historyCount = 0;
uint16_t historyHead = 0;
unsigned long historyAt = 0;
float flowLpm = 0;
unsigned long debugAt = 0;

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
void addLog(uint8_t code, uint8_t source, long extra) {
  eventLog[logHead] = { millis(), code, source, extra };
  logHead = (logHead + 1) % LOG_SIZE;
  if (logCount < LOG_SIZE) logCount++;
}

void addResult(uint16_t id, CommandState state) {
  if (resultCount == sizeof(results) / sizeof(results[0])) {
    memmove(results, results + 1, sizeof(results) - sizeof(results[0]));
    resultCount--;
  }
  results[resultCount++] = { id, state };
}

// Value of "key":number in one of the Nano's lines.
bool jsonNumber(const char *line, const char *key, long &value) {
  char pattern[16];
  snprintf(pattern, sizeof(pattern), "\"%s\":", key);
  const char *at = strstr(line, pattern);
  if (at == NULL) return false;
  char *end;
  value = strtol(at + strlen(pattern), &end, 10);
  return end != at + strlen(pattern);
}

// The Nano's lines have no checksum, so a line is used only if it is exactly
// {"t":"<word>","key":integer,...} - a damaged character makes it fail.
bool isWellFormed(const char *line) {
  const char *p = line;
  if (strncmp(p, "{\"t\":\"", 6) != 0) return false;
  p += 6;
  if (!islower((unsigned char)*p)) return false;
  while (islower((unsigned char)*p)) p++;
  if (*p++ != '"') return false;
  int fields = 0;
  while (*p == ',') {
    p++;
    if (*p++ != '"') return false;
    if (!islower((unsigned char)*p)) return false;
    while (islower((unsigned char)*p) || isdigit((unsigned char)*p)) p++;
    if (*p++ != '"' || *p++ != ':') return false;
    if (*p == '-') p++;
    if (!isdigit((unsigned char)*p)) return false;
    while (isdigit((unsigned char)*p)) p++;
    fields++;
  }
  return *p == '}' && p[1] == '\0' && fields >= 5;
}

// ---------------------------------------------------------------------------
// Commands to the Nano
// ---------------------------------------------------------------------------
// Only commands the Nano knows, in a safe character set, are accepted.
bool isAllowedCommand(const char *body) {
  static const char *const names[] = { "M", "R", "CS", "CX", "CF", "P", "S", "D", "T", "Q" };
  size_t length = strlen(body);
  if (length == 0 || length >= sizeof(queue[0].body)) return false;
  for (const char *c = body; *c; c++) {
    if (!isalnum((unsigned char)*c) && *c != ',' && *c != '=' && *c != '-') return false;
  }
  const char *comma = strchr(body, ',');
  size_t nameLength = comma ? (size_t)(comma - body) : length;
  for (const char *name : names) {
    if (strlen(name) == nameLength && strncmp(body, name, nameLength) == 0) return true;
  }
  return false;
}

// Returns the command's number, or 0 if the queue is full.
uint16_t queueCommand(const char *body) {
  if (queueCount == QUEUE_SIZE) return 0;
  Command &c = queue[queueCount++];
  c.id = nextId;
  nextId = nextId >= 65000 ? 1 : nextId + 1;
  strlcpy(c.body, body, sizeof(c.body));
  c.state = CMD_QUEUED;
  c.tries = 0;
  c.queuedAt = millis();
  c.sentAt = 0;
  return c.id;
}

void finishCommand(CommandState state) {
  if (queueCount == 0) return;
  addResult(queue[0].id, state);
  if (state == CMD_FAILED) commandsFailed++;
  memmove(queue, queue + 1, (queueCount - 1) * sizeof(Command));
  queueCount--;
}

// Called straight after a line from the Nano has ended: the Nano listens in
// the quiet gap after each line (it can't send and receive at once).
void sendNextCommand() {
  unsigned long now = millis();
  while (queueCount > 0 && now - queue[0].queuedAt > COMMAND_EXPIRY_MS) finishCommand(CMD_FAILED);
  if (queueCount == 0) return;
  Command &c = queue[0];
  if (c.state == CMD_SENT && now - c.sentAt < COMMAND_RETRY_MS) return;
  if (c.tries >= COMMAND_TRIES) {
    finishCommand(CMD_FAILED);
    return;
  }
  char line[120];
  snprintf(line, sizeof(line), "%u,%s", c.id, c.body);
  uint8_t sum = 0;
  for (const char *p = line; *p; p++) sum ^= (uint8_t)*p;
  char packet[130];
  snprintf(packet, sizeof(packet), "$%s*%02X\n", line, sum);
  nano.print(packet);
  if (c.tries > 0) commandRetries++;
  c.tries++;
  c.state = CMD_SENT;
  c.sentAt = now;
  commandsSent++;
}

// ---------------------------------------------------------------------------
// Lines from the Nano
// ---------------------------------------------------------------------------
void onStatusLine(const char *line) {
  long up;
  if (jsonNumber(line, "up", up)) {
    if (up < nanoUptime) lastEventNumber = -1;   // the Nano restarted: its events start again at 1
    nanoUptime = up;
  }

  long ack, ok;
  if (queueCount > 0 && queue[0].state == CMD_SENT && jsonNumber(line, "ack", ack) && ack == queue[0].id &&
      jsonNumber(line, "ok", ok)) {
    static const CommandState byResult[] = { CMD_REJECTED, CMD_DONE, CMD_BUSY, CMD_UNKNOWN };
    finishCommand(ok >= 0 && ok <= 3 ? byResult[ok] : CMD_UNKNOWN);
  }

  long number, code, source, extra;
  if (jsonNumber(line, "ev", number) && number > 0 && number != lastEventNumber &&
      jsonNumber(line, "ec", code) && jsonNumber(line, "es", source) && jsonNumber(line, "ex", extra)) {
    lastEventNumber = number;
    addLog(code, source, extra);
  }

  long hz100, ppl100;
  if (jsonNumber(line, "hz", hz100) && jsonNumber(line, "ppl", ppl100) && ppl100 > 0) {
    flowLpm = hz100 * 60.0f / ppl100;
  }
}

void onLine(const char *line) {
  if (!isWellFormed(line)) {
    badLines++;
    return;
  }
  goodLines++;
  unsigned long now = millis();
  if (!linkUp) {
    linkUp = true;
    addLog(EV_LINK_UP, SRC_ESP, 0);
  }
  if (strncmp(line, "{\"t\":\"s\"", 8) == 0) {
    statusLine = line;
    statusAt = now;
    onStatusLine(line);
  } else if (strncmp(line, "{\"t\":\"cfg\"", 10) == 0) {
    configLine = line;
    configAt = now;
  }
}

void readNano() {
  while (nano.available()) {
    char c = nano.read();
    bytesReceived++;
    lastByteAt = millis();
    if (c == '\r') continue;
    if (c == '\n') {
      rxLine[rxLength] = '\0';
      if (rxOverflow) {
        badLines++;
      } else if (rxLength > 0) {
        onLine(rxLine);
      }
      rxLength = 0;
      rxOverflow = false;
      sendNextCommand();
    } else if (rxLength < sizeof(rxLine) - 1) {
      rxLine[rxLength++] = c;
    } else {
      rxOverflow = true;
    }
  }
}

void checkLink() {
  unsigned long now = millis();
  if (linkUp && now - statusAt > LINK_LOST_MS) {
    linkUp = false;
    addLog(EV_LINK_LOST, SRC_ESP, 0);
  }
  if (!linkUp) {
    flowLpm = 0;
    while (queueCount > 0 && now - queue[0].queuedAt > COMMAND_EXPIRY_MS) finishCommand(CMD_FAILED);
  }
}

void updateHistory() {
  unsigned long now = millis();
  if (now - historyAt < HISTORY_STEP_MS) return;
  historyAt = now;
  float value = flowLpm * 100;
  history[historyHead] = value < 0 ? 0 : value > 65000 ? 65000 : (uint16_t)(value + 0.5f);
  historyHead = (historyHead + 1) % HISTORY_SIZE;
  if (historyCount < HISTORY_SIZE) historyCount++;
}

// "ok", "none" (nothing received yet), "garbled" (bytes but no good lines) or "lost".
const char *linkState() {
  if (linkUp) return "ok";
  if (goodLines > 0) return "lost";
  if (bytesReceived > 0) return "garbled";
  return "none";
}

// ---------------------------------------------------------------------------
// Web server
// ---------------------------------------------------------------------------
void sendJson(int code, const String &json) {
  server.sendHeader("Cache-Control", "no-store");
  server.send(code, "application/json", json);
}

void handlePage() {
  server.sendHeader("Content-Encoding", "gzip");
  server.sendHeader("Cache-Control", "no-cache");
  server.send_P(200, "text/html", (const char *)WEB_PAGE_GZ, WEB_PAGE_GZ_LENGTH);
}

void handleStatus() {
  unsigned long now = millis();
  String json;
  json.reserve(3000);
  json += "{\"now\":";
  json += now;
  json += ",\"ap\":\"";
  json += AP_NAME;
  json += "\",\"esp\":\"";
  json += ESP_VERSION;
  json += "\",\"clients\":";
  json += (int)WiFi.softAPgetStationNum();
  json += ",\"link\":{\"state\":\"";
  json += linkState();
  json += "\",\"age\":";
  json += statusAt ? (long)(now - statusAt) : -1;
  json += ",\"byteAge\":";
  json += lastByteAt ? (long)(now - lastByteAt) : -1;
  json += ",\"good\":";
  json += goodLines;
  json += ",\"bad\":";
  json += badLines;
  json += ",\"bytes\":";
  json += bytesReceived;
  json += ",\"sent\":";
  json += commandsSent;
  json += ",\"retries\":";
  json += commandRetries;
  json += ",\"failed\":";
  json += commandsFailed;
  json += ",\"queued\":";
  json += queueCount;
  json += "},\"s\":";
  json += statusLine.length() ? statusLine : String("null");
  json += ",\"cfg\":";
  json += configLine.length() ? configLine : String("null");
  json += ",\"cfgAge\":";
  json += configAt ? (long)(now - configAt) : -1;

  json += ",\"ev\":[";
  for (uint8_t i = 0; i < logCount; i++) {
    const LogEntry &e = eventLog[(logHead + LOG_SIZE - logCount + i) % LOG_SIZE];
    if (i) json += ',';
    json += '[';
    json += (long)(now - e.at);
    json += ',';
    json += (int)e.code;
    json += ',';
    json += (int)e.source;
    json += ',';
    json += e.extra;
    json += ']';
  }
  json += "],\"hist\":[";
  for (uint16_t i = 0; i < historyCount; i++) {
    if (i) json += ',';
    json += (unsigned int)history[(historyHead + HISTORY_SIZE - historyCount + i) % HISTORY_SIZE];
  }
  json += "],\"cmds\":[";
  bool first = true;
  for (uint8_t i = 0; i < resultCount; i++) {
    if (!first) json += ',';
    first = false;
    json += '[';
    json += (unsigned int)results[i].id;
    json += ',';
    json += (int)results[i].state;
    json += ']';
  }
  for (uint8_t i = 0; i < queueCount; i++) {
    if (!first) json += ',';
    first = false;
    json += '[';
    json += (unsigned int)queue[i].id;
    json += ',';
    json += (int)queue[i].state;
    json += ']';
  }
  json += "]}";
  sendJson(200, json);
}

// POST /api/cmd with c=<command>, e.g. c=M,1. Answers {"id":n}; the result
// appears in /api/status "cmds" as [id, state].
void handleCommand() {
  String body = server.arg("c");
  if (!isAllowedCommand(body.c_str())) {
    sendJson(400, "{\"err\":\"bad command\"}");
    return;
  }
  uint16_t id = queueCommand(body.c_str());
  if (id == 0) {
    sendJson(503, "{\"err\":\"busy\"}");
    return;
  }
  sendJson(200, String("{\"id\":") + (unsigned int)id + "}");
}

// Phones check a web address to see if a network has internet. Sending them
// to the dashboard makes them offer "sign in to network", which opens it.
void handleCaptive() {
  server.sendHeader("Location", String("http://") + AP_IP.toString() + "/", true);
  server.send(302, "text/plain", "");
}

// ---------------------------------------------------------------------------
// Setup and loop
// ---------------------------------------------------------------------------
bool startWifi() {
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(AP_IP, AP_IP, IPAddress(255, 255, 255, 0));
  bool started = WiFi.softAP(AP_NAME, strlen(AP_PASSWORD) >= 8 ? AP_PASSWORD : NULL, AP_CHANNEL);
  WiFi.setTxPower(WIFI_POWER);
  return started;
}

void setup() {
  Serial.begin(115200);
  nano.setRxBufferSize(1024);
  nano.begin(NANO_BAUD, SERIAL_8N1, NANO_RX_PIN, NANO_TX_PIN);
  nextId = 1 + esp_random() % 60000;   // so a restarted ESP doesn't repeat the Nano's last number

  bool wifiOk = startWifi();
  dns.setErrorReplyCode(DNSReplyCode::NoError);
  dns.start(53, "*", AP_IP);

  server.on("/", HTTP_GET, handlePage);
  server.on("/index.html", HTTP_GET, handlePage);
  server.on("/api/status", HTTP_GET, handleStatus);
  server.on("/api/cmd", HTTP_POST, handleCommand);
  server.onNotFound(handleCaptive);
  server.begin();

  addLog(EV_ESP_START, SRC_ESP, wifiOk ? 1 : 0);
  Serial.printf("\nAqua Tracka %s: Wi-Fi %s %s, page http://%s\n", ESP_VERSION, AP_NAME,
                wifiOk ? "started" : "FAILED (press RESET)", AP_IP.toString().c_str());
}

void printDebug() {
  unsigned long now = millis();
  if (now - debugAt < DEBUG_MS) return;
  debugAt = now;
  Serial.printf("Wi-Fi %s, page http://%s, %d phone(s) | Nano link: ", AP_NAME, AP_IP.toString().c_str(),
                WiFi.softAPgetStationNum());
  const char *state = linkState();
  if (strcmp(state, "ok") == 0) {
    Serial.printf("OK, %lu lines (%lu bad), %.2f L/min | %s\n", (unsigned long)goodLines, (unsigned long)badLines,
                  flowLpm, statusLine.c_str());
  } else if (strcmp(state, "lost") == 0) {
    Serial.printf("LOST (no good line for %lu s)\n", (now - statusAt) / 1000);
  } else if (strcmp(state, "garbled") == 0) {
    Serial.printf("bytes arrive but no good lines (%lu bytes): check the Nano sketch and the divider\n",
                  (unsigned long)bytesReceived);
  } else {
    Serial.println("NO DATA: nothing on GPIO20 yet (Nano D11 -> divider -> GPIO20, shared GND)");
  }
}

void loop() {
  dns.processNextRequest();
  server.handleClient();
  readNano();
  checkLink();
  updateHistory();
  printDebug();
}
