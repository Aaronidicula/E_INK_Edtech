// main_gooddisplay.cpp — E-Ink Google Calendar Display
// Layout: Red header | Left: mini-month grid + tasks | Right: 7-day agenda list

#include <Arduino.h>
#include <WiFi.h>
#include "credentials.h"
#include "epd_driver.h"
#include "gcal.h"
#include "driver/rtc_io.h"

#define REFRESH_MINUTES  15

// ── Buttons ──────────────────────────────────────────────────────────────────
// BTN_REFRESH wiring: GPIO32 → button → 3.3V, 10kΩ pulldown to GND
// Resting state: GPIO32 LOW (pulldown holds it)
// Pressed state: GPIO32 HIGH (3.3V through button)
// EXT1 wakes on ANY_HIGH — no ESP_PD_OPTION_ON needed, lower sleep current
#define BTN_REFRESH 32
#define BTN_READ    33

// ── Status LED ────────────────────────────────────────────────────────────────
// Active HIGH: LED ON = GPIO HIGH, LED OFF = GPIO LOW
// Wiring: GPIO2 → 10kΩ → LED anode → LED cathode → GND
#define PIN_LED      2
#define LED_ON()     digitalWrite(PIN_LED, HIGH)
#define LED_OFF()    digitalWrite(PIN_LED, LOW)

// Blink the LED n times at the given on/off period (ms), then leave LED off
static void ledBlink(int times, int onMs, int offMs) {
  for (int i = 0; i < times; i++) {
    LED_ON();  delay(onMs);
    LED_OFF(); delay(offMs);
  }
}

// Non-blocking blink tick — call repeatedly during long operations.
// Toggles the LED every intervalMs milliseconds.
static void ledBlinkTick(uint32_t intervalMs) {
  static uint32_t lastToggle = 0;
  static bool     ledState   = false;
  uint32_t now = millis();
  if (now - lastToggle >= intervalMs) {
    lastToggle = now;
    ledState = !ledState;
    digitalWrite(PIN_LED, ledState ? HIGH : LOW);  // active HIGH
  }
}

// ── Global state ─────────────────────────────────────────────────────────────
static CalEvent  gEvents[GCAL_MAX_EVENTS];
static CalEvent  gTasks[GCAL_MAX_EVENTS];
static int       gTaskCount  = 0;
static int       gEventCount = 0;
static char      gDateStr[32] = "Loading...";
static char      gTimeStr[12] = "";

// ── Calendar math helpers ─────────────────────────────────────────────────────
static int firstDayOfWeek(int year, int month) {
  struct tm t = {};
  t.tm_year = year - 1900;
  t.tm_mon  = month - 1;
  t.tm_mday = 1;
  mktime(&t);
  return t.tm_wday;  // 0=Sun .. 6=Sat
}

static int daysInMonth(int year, int month) {
  int days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  if (month == 2 && ((year%4==0 && year%100!=0) || year%400==0)) return 29;
  return days[month - 1];
}

// ── Layout constants ──────────────────────────────────────────────────────────
#define LEFT_W       340
#define RIGHT_X      342
#define RIGHT_W      (EPD_SOURCE - RIGHT_X - 10)

#define HEADER_H     64
#define FOOTER_Y     (EPD_GATE - 28)

#define GRID_X0      10
#define GRID_Y0      70
#define CELL_W       46
#define CELL_H       28
#define DAY_ROW_Y    (GRID_Y0 + CELL_H)

static int colX(int dow) { return GRID_X0 + dow * CELL_W + CELL_W / 2; }

// ── Render function ───────────────────────────────────────────────────────────
void renderCalendar(int bt, int bb) {

  auto R = [&](int x, int y, int w, int h, uint8_t c) {
    if (y < bb && y + h > bt) EPD_fillRect(x, y, w, h, c);
  };
  auto T = [&](int x, int y, const char* s, uint8_t c, int sc = 1) {
    if (y < bb && y + 8 * sc > bt) EPD_drawText(x, y, s, c, sc);
  };

  // ── 1. RED HEADER ──────────────────────────────────────────────────────────
  R(0, 0, EPD_SOURCE, HEADER_H, PIX_RED);

  char _dow[16]  = "";
  char _mon[16]  = "";
  int  todayDay  = 1, todayYear = 2024, todayMonth = 3;
  sscanf(gDateStr, "%s %s %d %d", _dow, _mon, &todayDay, &todayYear);

  const char* monNames[] = {
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
  };
  for (int m = 0; m < 12; m++) {
    if (strncmp(_mon, monNames[m], 3) == 0) { todayMonth = m + 1; break; }
  }

  {
    char header[32];
    snprintf(header, sizeof(header), "%s %d", _mon, todayYear);
    for (int i = 0; header[i]; i++)
      if (header[i] >= 'a' && header[i] <= 'z') header[i] -= 32;
    T(20, 14, header, PIX_WHITE, 3);
  }

  {
    char dowUpper[16];
    strncpy(dowUpper, _dow, sizeof(dowUpper) - 1);
    dowUpper[sizeof(dowUpper)-1] = 0;
    for (int i = 0; dowUpper[i]; i++)
      if (dowUpper[i] >= 'a' && dowUpper[i] <= 'z') dowUpper[i] -= 32;
    T(20, 42, dowUpper, PIX_WHITE, 1);
  }

  T(EPD_SOURCE - 160, 22, gTimeStr, PIX_WHITE, 2);
  R(0, HEADER_H, EPD_SOURCE, 2, PIX_BLACK);

  // ── 2. MINI MONTH GRID ─────────────────────────────────────────────────────
  R(GRID_X0, GRID_Y0, LEFT_W - 2 * GRID_X0, CELL_H, PIX_BLACK);
  const char* dowLabels[] = {"SU","MO","TU","WE","TH","FR","SA"};
  for (int d = 0; d < 7; d++) {
    T(colX(d) - 8, GRID_Y0 + 9, dowLabels[d], PIX_WHITE, 1);
  }

  int fdow   = firstDayOfWeek(todayYear, todayMonth);
  int dimLen = daysInMonth(todayYear, todayMonth);

  uint32_t eventDays = 0;
  for (int i = 0; i < gEventCount; i++) {
    int  eday = 0;
    char emon[8] = "";
    sscanf(gEvents[i].dateStr + 4, "%s %d", emon, &eday);
    char curAbbr[4] = { _mon[0], _mon[1], _mon[2], 0 };
    if (strncmp(emon, curAbbr, 3) == 0 && eday >= 1 && eday <= 31)
      eventDays |= (1u << eday);
  }

  for (int day = 1; day <= dimLen; day++) {
    int slot    = fdow + day - 1;
    int col     = slot % 7;
    int row     = slot / 7;
    int cellTop = DAY_ROW_Y + row * CELL_H;
    int cx      = colX(col);
    bool isToday = (day == todayDay);

    if (isToday)
      R(GRID_X0 + col * CELL_W, cellTop, CELL_W, CELL_H, PIX_RED);

    char dStr[4];
    snprintf(dStr, sizeof(dStr), "%d", day);
    int tx = cx - (strlen(dStr) == 1 ? 4 : 8);
    T(tx, cellTop + 9, dStr, isToday ? PIX_WHITE : PIX_BLACK, 1);

    if (!isToday && (eventDays & (1u << day)))
      R(cx - 1, cellTop + CELL_H - 5, 3, 3, PIX_RED);
  }

  // ── 3. TASKS SECTION ───────────────────────────────────────────────────────
  int usedRows = (fdow + dimLen - 1) / 7 + 1;
  int taskDivY = DAY_ROW_Y + usedRows * CELL_H + 6;

  R(GRID_X0, taskDivY, LEFT_W - 2 * GRID_X0, 1, PIX_BLACK);

  int tasksY = taskDivY + 6;
  R(GRID_X0, tasksY, LEFT_W - 2 * GRID_X0, 18, PIX_YELLOW);
  T(GRID_X0 + 4, tasksY + 4, "TASKS", PIX_BLACK, 1);

  int tItemY = tasksY + 24;
  for (int i = 0; i < gTaskCount && i < 4 && tItemY + 28 < FOOTER_Y; i++) {
    R(GRID_X0 + 2, tItemY,     10, 10, PIX_BLACK);
    R(GRID_X0 + 3, tItemY + 1,  8,  8, PIX_WHITE);

    char buf[28];
    strncpy(buf, gTasks[i].title, 27);
    buf[27] = 0;
    T(GRID_X0 + 16, tItemY,      buf,               PIX_BLACK, 1);
    T(GRID_X0 + 16, tItemY + 11, gTasks[i].dateStr, PIX_BLACK, 1);

    tItemY += 30;
    R(GRID_X0, tItemY - 3, LEFT_W - 2 * GRID_X0, 1, PIX_BLACK);
  }

  if (gTaskCount == 0)
    T(GRID_X0 + 4, tasksY + 26, "No tasks due", PIX_BLACK, 1);

  // ── 4. VERTICAL DIVIDER ────────────────────────────────────────────────────
  R(LEFT_W, HEADER_H + 2, 2, FOOTER_Y - HEADER_H - 2, PIX_BLACK);

  // ── 5. AGENDA PANEL ────────────────────────────────────────────────────────
  R(RIGHT_X, GRID_Y0, RIGHT_W, 20, PIX_BLACK);
  T(RIGHT_X + 8, GRID_Y0 + 5, "UPCOMING  7 DAYS", PIX_WHITE, 1);

  if (gEventCount == 0) {
    T(RIGHT_X + 20, GRID_Y0 + 40, "No upcoming events", PIX_BLACK, 2);
  } else {
    int evY        = GRID_Y0 + 26;
    const int EV_H = 58;
    char curAbbr[4] = { _mon[0], _mon[1], _mon[2], 0 };

    for (int i = 0; i < gEventCount && evY + EV_H < FOOTER_Y; i++) {
      int  eday = 0;
      char emon[8] = "";
      sscanf(gEvents[i].dateStr + 4, "%s %d", emon, &eday);
      bool isToday = (strncmp(emon, curAbbr, 3) == 0 && eday == todayDay);

      R(RIGHT_X, evY, 4, EV_H - 4, isToday ? PIX_RED : PIX_BLACK);

      int labelX = RIGHT_X + 12;
      if (isToday)
        T(labelX, evY + 2, "TODAY", PIX_RED, 1);
      else
        T(labelX, evY + 2, gEvents[i].dateStr, PIX_BLACK, 1);

      char titleBuf[36];
      int  maxChars = (RIGHT_W - 20) / 16;
      if (maxChars > 35) maxChars = 35;
      strncpy(titleBuf, gEvents[i].title, maxChars);
      titleBuf[maxChars] = 0;
      T(labelX, evY + 14, titleBuf, PIX_BLACK, 2);

      T(labelX, evY + 38, gEvents[i].timeStr, PIX_BLACK, 1);

      evY += EV_H;
      R(RIGHT_X, evY - 2, RIGHT_W, 1, PIX_BLACK);
    }
  }

  // ── 6. YELLOW FOOTER ───────────────────────────────────────────────────────
  R(0, FOOTER_Y, EPD_SOURCE, EPD_GATE - FOOTER_Y, PIX_YELLOW);
  char footer[48];
  snprintf(footer, sizeof(footer), "Updated: %s", gTimeStr);
  T(16, FOOTER_Y + 9, footer, PIX_BLACK, 1);
  T(EPD_SOURCE - 160, FOOTER_Y + 9, "Next: 15 min", PIX_BLACK, 1);
}

// ── WiFi (with LED blink tick during connection wait) ─────────────────────────
bool connectWifi() {
  Serial.printf("WiFi: connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries++ < 30) {
    // ~500ms per iteration split into 10×50ms ticks so LED blinks smoothly
    for (int t = 0; t < 10; t++) {
      ledBlinkTick(250);  // 2 Hz blink during WiFi wait
      delay(50);
    }
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi: FAILED");
    return false;
  }

  Serial.printf("WiFi: connected, IP=%s\n", WiFi.localIP().toString().c_str());
  return true;
}

// ── Main ──────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== E-Ink Calendar ===");

  // ── LED init ───────────────────────────────────────────────────────────────
  pinMode(PIN_LED, OUTPUT);
  LED_OFF();

  // ── Button init ────────────────────────────────────────────────────────────
  // BTN_REFRESH is INPUT only — no pinMode pullup needed, external 10kΩ to GND
  // handles the resting state. pinMode here only for BTN_READ which is awake-only.
  pinMode(BTN_READ, INPUT_PULLUP);

  // ── Wake reason — declared once, used throughout ───────────────────────────
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  bool wokeFromButton = (wakeup_reason == ESP_SLEEP_WAKEUP_EXT1);
  bool wokeFromTimer  = (wakeup_reason == ESP_SLEEP_WAKEUP_TIMER);
  bool coldBoot       = (wakeup_reason == ESP_SLEEP_WAKEUP_UNDEFINED);

  Serial.print("Wake reason: "); Serial.println(wakeup_reason);

  // ── EXT1 button debounce ───────────────────────────────────────────────────
  // Button wired to 3.3V — pressed = HIGH, released = LOW (pulled down by 10kΩ)
  // Wait for pin to return LOW (released) before continuing, otherwise the chip
  // may re-enter sleep while pin is still HIGH and immediately wake again.
  if (wokeFromButton) {
    Serial.println("EXT1 wakeup — waiting for button release...");
    uint32_t t0 = millis();
    while (digitalRead(BTN_REFRESH) == HIGH) {  // wait for release (HIGH → LOW)
      if (millis() - t0 > 3000) {
        Serial.println("Warning: button held > 3s, proceeding anyway");
        break;
      }
      delay(10);
    }
    delay(50);  // settle after release
    Serial.println("Button released — debounce OK");
  }

  bool refreshPressed = digitalRead(BTN_REFRESH) == HIGH;  // HIGH = pressed
  bool readPressed    = digitalRead(BTN_READ)    == LOW;   // LOW  = pressed (pullup)

  if (readPressed)                        Serial.println("Read button pressed");
  if (wokeFromButton || refreshPressed)   Serial.println("Manual refresh triggered");
  else if (wokeFromTimer)                 Serial.println("Timer refresh");
  else if (coldBoot)                      Serial.println("Cold boot");

  // ── Sync start: 2 quick blinks then solid ON ──────────────────────────────
  ledBlink(2, 100, 100);
  LED_ON();
  Serial.println("LED: sync started");

  // ── Display init ───────────────────────────────────────────────────────────
  EPD_init();

  // ── WiFi (LED blinks during connection) ────────────────────────────────────
  if (!connectWifi()) {
    gEventCount = 0;
    strncpy(gDateStr, "WiFi failed", sizeof(gDateStr));
    LED_OFF();
    ledBlink(3, 300, 200);  // 3 slow blinks = error
    EPD_flush(renderCalendar);
    EPD_sleep();
    goto SLEEP;
  }

  // ── Google Calendar init — LED solid ON during token fetch ─────────────────
  LED_ON();
  if (!gcal_init()) {
    strncpy(gDateStr, "Auth failed", sizeof(gDateStr));
    LED_OFF();
    ledBlink(3, 300, 200);  // 3 slow blinks = error
    EPD_flush(renderCalendar);
    EPD_sleep();
    WiFi.disconnect(true);
    goto SLEEP;
  }

  // ── Fetch data — LED solid ON ──────────────────────────────────────────────
  gcal_getNow(gDateStr, sizeof(gDateStr), gTimeStr, sizeof(gTimeStr));
  gEventCount = gcal_getEvents(gEvents, GCAL_MAX_EVENTS);
  gTaskCount  = gcal_getTasks(gTasks,  GCAL_MAX_EVENTS);

  // ── Render ─────────────────────────────────────────────────────────────────
  EPD_flush(renderCalendar);
  EPD_sleep();

  WiFi.disconnect(true);

  // ── Sync complete: one long flash then OFF ─────────────────────────────────
  LED_OFF();
  ledBlink(1, 500, 0);  // single 500ms flash = done
  LED_OFF();
  Serial.println("LED: sync complete");

SLEEP:
  Serial.println("Entering deep sleep...");

  // Ensure LED is off before sleeping
  LED_OFF();

  // ── Configure GPIO32 as RTC input with pulldown BEFORE sleep ──────────────
  // Button wired to 3.3V: pin rests LOW (external 10kΩ to GND),
  // button press drives it HIGH → EXT1 ANY_HIGH fires.
  // No ESP_PD_OPTION_ON needed for ANY_HIGH — saves ~100µA in sleep.
  rtc_gpio_init(GPIO_NUM_32);
  rtc_gpio_set_direction(GPIO_NUM_32, RTC_GPIO_MODE_INPUT_ONLY);
  rtc_gpio_pullup_dis(GPIO_NUM_32);    // disable internal pullup
  rtc_gpio_pulldown_en(GPIO_NUM_32);   // enable internal pulldown (belt + braces
                                       // alongside the external 10kΩ)

  // Wake when GPIO32 goes HIGH (button connects it to 3.3V)
  esp_sleep_enable_ext1_wakeup((1ULL << BTN_REFRESH), ESP_EXT1_WAKEUP_ANY_HIGH);

  // Wake on 15-minute timer
  esp_sleep_enable_timer_wakeup((uint64_t)REFRESH_MINUTES * 60ULL * 1000000ULL);

  Serial.println("Good night.");
  Serial.flush();
  esp_deep_sleep_start();
}

void loop() {
  // Never reached — deep sleep causes a full reboot on each wake cycle
}
