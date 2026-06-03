#pragma once
// ── WiFi ──────────────────────────────────────────────────────────────────────
#define WIFI_SSID   "Your_WiFi_SSID"
#define WIFI_PASS   "Your_WiFi_Password"

// ── Google Service Account ────────────────────────────────────────────────────
// 1. Go to console.cloud.google.com → Create project
// 2. Enable Google Calendar API
// 3. IAM & Admin → Service Accounts → Create → Add key (JSON)
// 4. Copy client_email and private_key from the downloaded JSON

#define GCAL_SERVICE_ACCOUNT_EMAIL  "your-service-account@your-project.iam.gserviceaccount.com"

// Paste the full private key including -----BEGIN/END----- lines
// Use \n for line breaks
#define GCAL_PRIVATE_KEY \
"-----BEGIN PRIVATE KEY-----\n" \
"YOUR_PRIVATE_KEY_HERE\n" \
"-----END PRIVATE KEY-----\n"

// ── Google Calendar ───────────────────────────────────────────────────────────
// Share your calendar with the service account email (give it "See all event details")
// Calendar ID is usually your Gmail address, or find it in calendar settings

#define GCAL_CALENDAR_ID  "your-email@gmail.com"

// Additional calendars — find their IDs in Google Calendar settings
// Go to calendar → Settings → "Integrate calendar" → Calendar ID
// Leave empty string "" to disable

#define GCAL_CALENDAR_ID_2      ""   // optional second calendar
#define GCAL_CALENDAR_ID_3      ""   // optional third calendar

// ── Timezone ──────────────────────────────────────────────────────────────────
// UTC offset in seconds for your local time display
// India (IST) = +5:30 = 19800
// UK  (GMT)   = 0
// US East     = -18000 (EST) or -14400 (EDT)

#define GCAL_UTC_OFFSET_SECONDS  19800   // IST +5:30
