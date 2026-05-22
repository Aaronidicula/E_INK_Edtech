// gcal.cpp — Google Calendar via Service Account JWT (RS256)
// ESP32 mbedtls is built-in — no extra lib needed for crypto
// Only external dependency: ArduinoJson v7
// This file is identical to the Good Display version; it has no panel-specific code.

#include "gcal.h"
#include "credentials.h"
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <mbedtls/pk.h>
#include <mbedtls/md.h>
#include <mbedtls/base64.h>
#include <mbedtls/entropy.h>
#include <mbedtls/ctr_drbg.h>

#include <time.h>

static char  _accessToken[512] = {0};
static time_t _tokenExpiry = 0;

// ── Base64url ─────────────────────────────────────────────────────────────
static String b64url(const uint8_t* data, size_t len) {
  size_t outLen = 4 * ((len + 2) / 3) + 2;
  uint8_t* buf = (uint8_t*)malloc(outLen);
  size_t written = 0;
  mbedtls_base64_encode(buf, outLen, &written, data, len);
  buf[written] = 0;
  String s((char*)buf);
  free(buf);
  s.replace("+", "-");
  s.replace("/", "_");
  while (s.endsWith("=")) s.remove(s.length() - 1);
  return s;
}

static String b64urlStr(const char* str) {
  return b64url((const uint8_t*)str, strlen(str));
}

// ── Time helpers ──────────────────────────────────────────────────────────
static void unixToISO(time_t t, char* buf, int len) {
  struct tm* tm = gmtime(&t);
  strftime(buf, len, "%Y-%m-%dT%H:%M:%SZ", tm);
}

static void parseTimeStr(const char* iso, char* out, int outLen, bool* allDay) {
  if (strlen(iso) <= 10) {
    *allDay = true;
    strncpy(out, "All day", outLen);
    return;
  }
  *allDay = false;
  int hour = 0, minute = 0;
  sscanf(iso + 11, "%d:%d", &hour, &minute);
  const char* ampm = hour < 12 ? "AM" : "PM";
  if (hour == 0) hour = 12;
  else if (hour > 12) hour -= 12;
  snprintf(out, outLen, "%d:%02d %s", hour, minute, ampm);
}

static void parseDateStr(const char* iso, char* out, int outLen) {
  int y = 0, m = 0, d = 0;
  sscanf(iso, "%d-%d-%d", &y, &m, &d);
  struct tm t = {};
  t.tm_year = y - 1900; t.tm_mon = m - 1; t.tm_mday = d;
  mktime(&t);
  strftime(out, outLen, "%a %b %d", &t);
}

// ── JWT builder ───────────────────────────────────────────────────────────
static String buildJWT(time_t now) {
  const char* header = "{\"alg\":\"RS256\",\"typ\":\"JWT\"}";

  char payload[640];
  snprintf(payload, sizeof(payload),
    "{\"iss\":\"%s\","
    "\"scope\":\"https://www.googleapis.com/auth/calendar.readonly"
                " https://www.googleapis.com/auth/tasks.readonly\","
    "\"aud\":\"https://oauth2.googleapis.com/token\","
    "\"exp\":%lu,"
    "\"iat\":%lu}",
    GCAL_SERVICE_ACCOUNT_EMAIL,
    (unsigned long)(now + 3600),
    (unsigned long)now
  );

  String sigInput = b64urlStr(header) + "." + b64urlStr(payload);

  mbedtls_pk_context pk;
  mbedtls_pk_init(&pk);

  const char* key = GCAL_PRIVATE_KEY;
  int ret = mbedtls_pk_parse_key(&pk, (const uint8_t*)key, strlen(key) + 1, nullptr, 0);
  if (ret != 0) {
    char errBuf[64];
    mbedtls_strerror(ret, errBuf, sizeof(errBuf));
    Serial.printf("JWT: pk_parse_key failed: %s\n", errBuf);
    mbedtls_pk_free(&pk);
    return "";
  }

  uint8_t hash[32];
  mbedtls_md(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),
             (const uint8_t*)sigInput.c_str(), sigInput.length(), hash);

  mbedtls_entropy_context  entropy;
  mbedtls_ctr_drbg_context ctr_drbg;
  mbedtls_entropy_init(&entropy);
  mbedtls_ctr_drbg_init(&ctr_drbg);
  mbedtls_ctr_drbg_seed(&ctr_drbg, mbedtls_entropy_func, &entropy, nullptr, 0);

  uint8_t sig[256];
  size_t  sigLen = 0;
  ret = mbedtls_pk_sign(&pk, MBEDTLS_MD_SHA256, hash, 32, sig, &sigLen,
                        mbedtls_ctr_drbg_random, &ctr_drbg);

  mbedtls_ctr_drbg_free(&ctr_drbg);
  mbedtls_entropy_free(&entropy);
  mbedtls_pk_free(&pk);

  if (ret != 0) {
    Serial.printf("JWT: sign failed: -0x%04X\n", -ret);
    return "";
  }

  return sigInput + "." + b64url(sig, sigLen);
}

// ── Token fetch ───────────────────────────────────────────────────────────
static bool fetchToken() {
  time_t now = time(nullptr);
  if (_accessToken[0] && now < _tokenExpiry - 60) return true;

  Serial.println("GCal: fetching access token...");
  String jwt = buildJWT(now);
  if (jwt.isEmpty()) return false;

  String body = "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=";
  body += jwt;

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, "https://oauth2.googleapis.com/token");
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");
  int code = http.POST(body);

  String resp = http.getString();
  http.end();

  if (code != 200) {
    Serial.printf("GCal: token HTTP %d: %s\n", code, resp.substring(0, 200).c_str());
    return false;
  }

  JsonDocument doc;
  deserializeJson(doc, resp);
  const char* token = doc["access_token"];
  if (!token) { Serial.println("GCal: no token in response"); return false; }

  strncpy(_accessToken, token, sizeof(_accessToken) - 1);
  _tokenExpiry = now + (long)doc["expires_in"];
  Serial.println("GCal: token OK");
  return true;
}

// ── Public API ────────────────────────────────────────────────────────────
bool gcal_init() {
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  Serial.print("GCal: NTP sync");
  time_t now = 0;
  for (int i = 0; i < 40 && now < 1000000000L; i++) {
    delay(500); Serial.print("."); now = time(nullptr);
  }
  Serial.println();
  if (now < 1000000000L) { Serial.println("GCal: NTP failed"); return false; }
  Serial.printf("GCal: time = %lu\n", (unsigned long)now);
  return fetchToken();
}

static int fetchCalendar(const char* calId, CalEvent* events, int offset, int maxEvents) {
  if (!calId || strlen(calId) == 0) return 0;

  time_t now = time(nullptr);
  char tMin[32], tMax[32];
  unixToISO(now, tMin, sizeof(tMin));
  unixToISO(now + 7 * 24 * 3600, tMax, sizeof(tMax));

  String tMinEnc = String(tMin); tMinEnc.replace(":", "%3A");
  String tMaxEnc = String(tMax); tMaxEnc.replace(":", "%3A");

  char url[600];
  snprintf(url, sizeof(url),
    "https://www.googleapis.com/calendar/v3/calendars/%s/events"
    "?timeMin=%s&timeMax=%s&singleEvents=true&orderBy=startTime&maxResults=%d",
    calId, tMinEnc.c_str(), tMaxEnc.c_str(), maxEvents - offset);
  Serial.printf("GCal: fetching %s\n", calId);

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, url);
  http.addHeader("Authorization", String("Bearer ") + _accessToken);
  int code = http.GET();

  if (code != 200) {
    Serial.printf("GCal: HTTP %d for %s\n", code, calId);
    http.end();
    return 0;
  }

  String body = http.getString();
  http.end();

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) { Serial.printf("GCal: JSON error: %s\n", err.c_str()); return 0; }

  int count = 0;
  for (JsonObject item : doc["items"].as<JsonArray>()) {
    if (offset + count >= maxEvents) break;
    CalEvent& ev = events[offset + count];
    strncpy(ev.title, item["summary"] | "(No title)", sizeof(ev.title) - 1);
    ev.title[sizeof(ev.title) - 1] = 0;

    const char* dtStart = item["start"]["dateTime"] | "";
    const char* dStart  = item["start"]["date"] | "";
    const char* src = strlen(dtStart) > 0 ? dtStart : dStart;
    parseTimeStr(src, ev.timeStr, sizeof(ev.timeStr), &ev.isAllDay);
    parseDateStr(src, ev.dateStr, sizeof(ev.dateStr));
    count++;
  }
  Serial.printf("GCal: got %d events from %s\n", count, calId);
  return count;
}

int gcal_getEvents(CalEvent* events, int maxEvents) {
  if (!fetchToken()) return 0;
  int total = 0;
  total += fetchCalendar(GCAL_CALENDAR_ID,   events, total, maxEvents);
  total += fetchCalendar(GCAL_CALENDAR_ID_2, events, total, maxEvents);
  total += fetchCalendar(GCAL_CALENDAR_ID_3, events, total, maxEvents);
  Serial.printf("GCal: total %d events\n", total);
  return total;
}

int gcal_getTasks(CalEvent* events, int maxEvents) {
  if (!fetchToken()) return 0;

  const char* url =
    "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks"
    "?showCompleted=false&showHidden=false&maxResults=10";

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, url);
  http.addHeader("Authorization", String("Bearer ") + _accessToken);
  int code = http.GET();

  if (code != 200) {
    Serial.printf("GCal: tasks HTTP %d\n", code);
    Serial.println(http.getString().substring(0, 200));
    http.end();
    return 0;
  }

  String respBody = http.getString();
  http.end();

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, respBody);
  if (err) { Serial.printf("GCal: tasks JSON error: %s\n", err.c_str()); return 0; }

  int count = 0;
  for (JsonObject item : doc["items"].as<JsonArray>()) {
    if (count >= maxEvents) break;
    const char* status = item["status"] | "needsAction";
    if (strcmp(status, "completed") == 0) continue;

    CalEvent& ev = events[count];
    strncpy(ev.title, item["title"] | "(No title)", sizeof(ev.title) - 1);
    ev.title[sizeof(ev.title) - 1] = 0;

    const char* due = item["due"] | "";
    ev.isAllDay = true;
    strncpy(ev.timeStr, "Task", sizeof(ev.timeStr) - 1);
    if (strlen(due) > 0)
      parseDateStr(due, ev.dateStr, sizeof(ev.dateStr));
    else
      strncpy(ev.dateStr, "No date", sizeof(ev.dateStr) - 1);
    count++;
  }

  Serial.printf("GCal: got %d tasks\n", count);
  return count;
}

void gcal_getNow(char* dateBuf, int dateLen, char* timeBuf, int timeLen) {
  time_t now = time(nullptr) + GCAL_UTC_OFFSET_SECONDS;
  struct tm* t = gmtime(&now);
  strftime(dateBuf, dateLen, "%A  %B %d %Y", t);
  strftime(timeBuf, timeLen, "%I:%M %p", t);
}
