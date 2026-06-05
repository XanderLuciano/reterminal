#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <NimBLEDevice.h>
#include <Wire.h>
#include "wifi_config.h"

#ifdef E1002_VARIANT
  #include <GxEPD2_7C.h>
#elif defined(E1001_VARIANT)
  #include <GxEPD2_BW.h>
#endif

#include "embedded_screens.h"

// ── Shared config ──
const int NUM_PAGES = 3;
const char* TEMPLATE_NAMES[] = {"newspaper", "weather", "maintenance"};
const uint64_t DEEP_SLEEP_SECONDS = 60;
const int ADVERTISE_TIMEOUT_S = 10;
const int HEALTH_INTERVAL_HOURS = 6;
const int SELECT_TIMEOUT_S = 30;
const bool ENABLE_BEEPS = true;

// EPD pins (same for both E1001 and E1002)
#define EPD_SCK 7
#define EPD_MOSI 9
#define EPD_CS 10
#define EPD_DC 11
#define EPD_RES 12
#define EPD_BUSY 13

// Buttons
#define BTN_LEFT  5
#define BTN_RIGHT 4
#define BTN_GREEN 3

// Buzzer
#define BUZZER_PIN 45

// LED (charging indicator)
#define LED_PIN 6       // active-low (LOW=ON), also used for charge status

// Battery
#define BATT_ENABLE 21
#define BATT_ADC    1

// Charger (SY6974B on I2C1)
#define CHARGER_I2C_SDA 39
#define CHARGER_I2C_SCL 40
#define CHARGER_ADDR    0x6B
#define CHARGER_REG0B   0x0B   // charger status register

// ── Variant-specific config ──
#ifdef E1002_VARIANT
  #define BLE_DEVICE_NAME "E1002-Dashboard"
  #define SERVICE_UUID     "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  #define TRIGGER_UUID     "b2c3d4e5-f6a7-8901-bcde-f12345678901"
  const char* DASHBOARD_BASE_URL = "http://YOUR_SERVER_IP:8088/dashboard.bin";
  const size_t FB_SIZE = (800UL * 480UL + 1) / 2;   // 4-bit nibble packed

  // Reduced page height to minimize _pixel_buffer BSS in DRAM.
  // writeImage()+refresh() bypasses the page system entirely.
  GxEPD2_7C<GxEPD2_730c_GDEP073E01, 48>
    display(GxEPD2_730c_GDEP073E01(EPD_CS, EPD_DC, EPD_RES, EPD_BUSY));
#elif defined(E1001_VARIANT)
  #define BLE_DEVICE_NAME "E1001-Dashboard"
  #define SERVICE_UUID     "c3d4e5f6-a7b8-9012-cdef-123456789012"
  #define TRIGGER_UUID     "d4e5f6a7-b8c9-0123-defa-234567890123"
  const char* DASHBOARD_BASE_URL = "http://YOUR_SERVER_IP:8088/dashboard-bw.bin";
  const size_t FB_SIZE = (800UL * 480UL + 7) / 8;   // 1-bit packed

  GxEPD2_BW<GxEPD2_750_GDEY075T7, GxEPD2_750_GDEY075T7::HEIGHT>
    display(GxEPD2_750_GDEY075T7(EPD_CS, EPD_DC, EPD_RES, EPD_BUSY));
#endif

SPIClass hspi(HSPI);
uint8_t* framebuf = nullptr;

RTC_DATA_ATTR uint32_t rtc_sleep_cycles = 0;
RTC_DATA_ATTR bool rtc_first_boot = true;
RTC_DATA_ATTR int rtc_active_page = 0;
RTC_DATA_ATTR char rtc_etags[3][64] = {{""}, {""}, {""}};
volatile bool bleTriggered = false;

class TriggerCallbacks : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic* pChar, NimBLEConnInfo& connInfo) override {
    bleTriggered = true;
  }
};

// ── Battery ──

int readBatteryPercent() {
  pinMode(BATT_ENABLE, OUTPUT);
  digitalWrite(BATT_ENABLE, HIGH);
  delay(50);
  int raw = analogRead(BATT_ADC);
  delay(10);
  raw += analogRead(BATT_ADC);
  raw /= 2;
  digitalWrite(BATT_ENABLE, LOW);
  float voltage = (float)raw / 4095.0 * 3.1 * 2.0;
  if (voltage >= 4.15) return 100;
  if (voltage >= 3.96) return 90;
  if (voltage >= 3.91) return 80;
  if (voltage >= 3.85) return 70;
  if (voltage >= 3.80) return 60;
  if (voltage >= 3.75) return 50;
  if (voltage >= 3.68) return 40;
  if (voltage >= 3.58) return 30;
  if (voltage >= 3.49) return 20;
  if (voltage >= 3.41) return 10;
  if (voltage >= 3.30) return 5;
  return 0;
}

// ── Charger LED ──

enum ChargeState { CHG_NONE, CHG_ACTIVE, CHG_DONE };

ChargeState readChargeState() {
  Wire1.beginTransmission(CHARGER_ADDR);
  Wire1.write(CHARGER_REG0B);
  if (Wire1.endTransmission(false) != 0) {
    return CHG_NONE;  // charger not responding = no USB power
  }
  Wire1.requestFrom((uint8_t)CHARGER_ADDR, (uint8_t)1);
  if (!Wire1.available()) return CHG_NONE;

  uint8_t reg = Wire1.read();
  bool vbus = reg & 0x20;          // bit 5: VBUS present
  uint8_t stat = (reg >> 6) & 0x03; // bits 7-6: 00=idle, 01=precharge, 10=fast, 11=done

  if (!vbus) return CHG_NONE;
  if (stat == 0x03) return CHG_DONE;
  return CHG_ACTIVE;
}

void indicateCharge(ChargeState state) {
  pinMode(LED_PIN, OUTPUT);
  switch (state) {
    case CHG_DONE:
      digitalWrite(LED_PIN, LOW);   // solid on = fully charged
      break;
    case CHG_ACTIVE:
      // Triple pulse = charging
      for (int i = 0; i < 3; i++) {
        digitalWrite(LED_PIN, LOW);  delay(80);
        digitalWrite(LED_PIN, HIGH); delay(200);
      }
      break;
    case CHG_NONE:
    default:
      digitalWrite(LED_PIN, HIGH);  // off
      break;
  }
}

// ── Buzzer ──

void beepBoot() {
  if (!ENABLE_BEEPS) return;
  tone(BUZZER_PIN, 2600, 80); delay(120);
}

void beepError() {
  if (!ENABLE_BEEPS) return;
  tone(BUZZER_PIN, 1800, 100); delay(160);
  tone(BUZZER_PIN, 1800, 100); delay(140);
}

void beepPage(int page) {
  if (!ENABLE_BEEPS) return;
  int count = page + 1;
  for (int i = 0; i < count; i++) {
    tone(BUZZER_PIN, 2200, 40);
    delay(80);
  }
  delay(120);
}

void beepConfirm() {
  if (!ENABLE_BEEPS) return;
  tone(BUZZER_PIN, 1800, 60); delay(100);
  tone(BUZZER_PIN, 2200, 60); delay(100);
  tone(BUZZER_PIN, 2600, 60);
}

// ── WiFi & Fetch ──

bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(500);
  return WiFi.status() == WL_CONNECTED;
}

// Returns: 1 = fetched & rendered, 0 = unchanged (304), -1 = error
int fetchPage(int page, int batteryPct) {
  framebuf = nullptr;
  framebuf = (uint8_t*)ps_malloc(FB_SIZE);
  if (!framebuf) return -1;

  char url[256];
  snprintf(url, sizeof(url), "%s?template=%s&battery=%d",
           DASHBOARD_BASE_URL, TEMPLATE_NAMES[page], batteryPct);

  HTTPClient http; http.begin(url); http.setTimeout(30000);

  // Conditional fetch — skip re-render if content hasn't changed
  if (strlen(rtc_etags[page]) > 0) {
    http.addHeader("If-None-Match", rtc_etags[page]);
  }

  int code = http.GET();

  if (code == 304) {
    http.end();
    framebuf = nullptr;
    return 0;  // unchanged
  }

  if (code != 200) { http.end(); return -1; }

  // Store new ETag for next conditional fetch
  if (http.hasHeader("ETag")) {
    String etag = http.header("ETag");
    strncpy(rtc_etags[page], etag.c_str(), 63);
    rtc_etags[page][63] = 0;
  } else {
    rtc_etags[page][0] = 0;  // no ETag → always fetch
  }

  WiFiClient* stream = http.getStreamPtr();
  size_t total = 0; unsigned long start = millis();
  while (total < FB_SIZE && stream->connected() && millis() - start < 30000) {
    if (stream->available()) {
      size_t n = stream->available();
      if (total + n > FB_SIZE) n = FB_SIZE - total;
      total += stream->readBytes(framebuf + total, n);
    }
    delay(1);
  }
  http.end();
  if (total != FB_SIZE) return -1;
  return 1;
}

void showPage(int page) {
  if (!framebuf) return;
  display.init(0);  // re-init after deep sleep (controller loses power)
  display.setFullWindow();
#ifdef E1002_VARIANT
  // Use writeNative for nibble-packed 4-bit Spectra 6 data.
  // writeImage() treats data as 1-bit monochrome and scrambles colors.
  // _convert_to_native() handles GxEPD2 logical → panel native remapping.
  display.epd2.writeNative(framebuf, nullptr, 0, 0, 800, 480);
  display.epd2.refresh(false);
  display.epd2.powerOff();
#elif defined(E1001_VARIANT)
  // Write bit-packed framebuf directly to controller — bypasses Adafruit_GFX paging
  display.epd2.writeImage(framebuf, 0, 0, 800, 480);
  display.epd2.refresh(false);
  display.epd2.powerOff();
#endif
  rtc_active_page = page;
  framebuf = nullptr;
  beepConfirm();
}

// ── Screen helpers (use writeImage to avoid GxEPD2_7C paged-text bugs) ──

void showEmbeddedBitmap(const uint8_t* bitmap, size_t len) {
  display.init(0);
  display.setFullWindow();
#ifdef E1002_VARIANT
  (void)len;  // size is fixed for E1002 (192000 bytes)
  // writeNative for nibble-packed 4-bit data — same format as server framebuf
  display.epd2.writeNative(bitmap, nullptr, 0, 0, 800, 480);  // no pgm — ESP32 flash is memory-mapped
  display.epd2.refresh(false);
  display.epd2.powerOff();
#elif defined(E1001_VARIANT)
  // Bypass Adafruit_GFX drawBitmap — write directly to controller for cleaner output
  (void)len;
  display.epd2.writeImage(bitmap, 0, 0, 800, 480, false, false, false);
  display.epd2.refresh(false);  // false = full refresh, not partial
  display.epd2.powerOff();
#endif
}

void showError(bool isWifiError) {
#ifdef E1002_VARIANT
  showEmbeddedBitmap(
    isWifiError ? error_wifi_e1002 : error_fetch_e1002,
    isWifiError ? error_wifi_e1002_len : error_fetch_e1002_len
  );
#elif defined(E1001_VARIANT)
  showEmbeddedBitmap(
    isWifiError ? error_wifi_e1001_bw : error_fetch_e1001_bw,
    isWifiError ? error_wifi_e1001_bw_len : error_fetch_e1001_bw_len
  );
#endif

  beepError();
  delay(500);
  // Wait for button press before going back to sleep
  while (digitalRead(BTN_LEFT) == HIGH &&
         digitalRead(BTN_RIGHT) == HIGH &&
         digitalRead(BTN_GREEN) == HIGH) {
    delay(50);
  }
  delay(200);  // debounce
}

void showSplash() {
#ifdef E1002_VARIANT
  showEmbeddedBitmap(splash_e1002, splash_e1002_len);
#elif defined(E1001_VARIANT)
  showEmbeddedBitmap(splash_e1001_bw, splash_e1001_bw_len);
#endif
  beepBoot();
}

// ── Button selection ──

int selectPage(int currentPage) {
  int selected = currentPage;
  beepPage(selected);

  unsigned long start = millis();
  while (millis() - start < SELECT_TIMEOUT_S * 1000UL) {
    if (digitalRead(BTN_LEFT) == LOW) {
      delay(20);
      if (digitalRead(BTN_LEFT) == LOW) {
        selected = (selected - 1 + NUM_PAGES) % NUM_PAGES;
        beepPage(selected);
        while (digitalRead(BTN_LEFT) == LOW) delay(10);
        start = millis();
      }
    }
    if (digitalRead(BTN_RIGHT) == LOW) {
      delay(20);
      if (digitalRead(BTN_RIGHT) == LOW) {
        selected = (selected + 1) % NUM_PAGES;
        beepPage(selected);
        while (digitalRead(BTN_RIGHT) == LOW) delay(10);
        start = millis();
      }
    }
    if (digitalRead(BTN_GREEN) == LOW) {
      delay(20);
      if (digitalRead(BTN_GREEN) == LOW) {
        beepConfirm();
        while (digitalRead(BTN_GREEN) == LOW) delay(10);
        return selected;
      }
    }
    delay(30);
  }
  return -1;
}

// ── BLE ──

void startBLE() {
  NimBLEDevice::init(BLE_DEVICE_NAME);
  NimBLEDevice::setPower(ESP_PWR_LVL_P9);
  NimBLEServer* pServer = NimBLEDevice::createServer();
  NimBLEService* pService = pServer->createService(SERVICE_UUID);
  NimBLECharacteristic* pTrigger = pService->createCharacteristic(TRIGGER_UUID, NIMBLE_PROPERTY::WRITE);
  pTrigger->setCallbacks(new TriggerCallbacks());
  pService->start();
  NimBLEAdvertising* pAdv = NimBLEDevice::getAdvertising();
  pAdv->addServiceUUID(SERVICE_UUID);
  pAdv->setMinInterval(32);
  pAdv->setMaxInterval(64);
  NimBLEAdvertisementData scanResp;
  scanResp.setName(BLE_DEVICE_NAME);
  pAdv->setScanResponseData(scanResp);
  pAdv->start();
}

// ── Core flow ──

void refreshAndShow(int page) {
  if (!connectWiFi()) {
    showError(true);
    return;
  }
  // Check charge state: if on USB, battery voltage is unreliable
  // -1 = actively charging, -2 = fully charged, >=0 = battery percentage
  ChargeState chg = readChargeState();
  int battery;
  if (chg == CHG_ACTIVE) battery = -1;
  else if (chg == CHG_DONE) battery = -2;
  else battery = readBatteryPercent();
  int result = fetchPage(page, battery);
  WiFi.disconnect(true);

  if (result < 0) {
    showError(false);
    return;
  }
  if (result == 0) {
    // Content unchanged — skip display refresh, save battery
    framebuf = nullptr;
    return;
  }
  showPage(page);
  rtc_sleep_cycles = 0;
}

void goDeepSleep() {
  Serial0.flush();
  esp_sleep_enable_timer_wakeup(DEEP_SLEEP_SECONDS * 1000000ULL);
  esp_sleep_enable_ext1_wakeup(
    (1ULL << BTN_LEFT) | (1ULL << BTN_RIGHT) | (1ULL << BTN_GREEN),
    ESP_EXT1_WAKEUP_ANY_LOW
  );
  esp_deep_sleep_start();
}

// Light-sleep loop: keeps LED visible while on USB power.
// On battery → deep sleep; on USB → light sleep with 5s refresh.
void enterUSBAwareSleep() {
  ChargeState chg = readChargeState();

  if (chg == CHG_NONE) {
    // No USB power — deep sleep, LED off
    digitalWrite(LED_PIN, HIGH);  // active-low off
    goDeepSleep();
    return;
  }

  // USB connected — light sleep loop, LED stays active
  indicateCharge(chg);

  while (true) {
    esp_sleep_enable_timer_wakeup(5 * 1000000ULL);  // 5s refresh
    uint64_t btnMask = (1ULL << BTN_LEFT) | (1ULL << BTN_RIGHT) | (1ULL << BTN_GREEN);
    esp_sleep_enable_ext1_wakeup(btnMask, ESP_EXT1_WAKEUP_ANY_LOW);

    esp_light_sleep_start();

    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();

    if (cause == ESP_SLEEP_WAKEUP_EXT1) {
      // Button pressed during light sleep — handle it like normal button wake
      delay(50);  // debounce
      int chosen = selectPage(rtc_active_page);
      if (chosen >= 0) refreshAndShow(chosen);
    }

    // Re-read charge state (may have changed: USB plug/unplug, charge complete)
    chg = readChargeState();
    if (chg == CHG_NONE) {
      // USB disconnected — switch to deep sleep
      digitalWrite(LED_PIN, HIGH);  // LED off
      goDeepSleep();
      return;
    }

    indicateCharge(chg);
    // Loop: stay in light sleep while USB connected
  }
}

void setup() {
  Serial0.begin(115200); delay(100);

  // Init charger I2C and check charging status for LED indicator
  Wire1.begin(CHARGER_I2C_SDA, CHARGER_I2C_SCL);
  ChargeState chg = readChargeState();
  indicateCharge(chg);  // flash/blink/solid LED based on charge state

  pinMode(EPD_RES, OUTPUT); pinMode(EPD_DC, OUTPUT); pinMode(EPD_CS, OUTPUT);
  hspi.begin(EPD_SCK, -1, EPD_MOSI, -1);
#ifdef E1002_VARIANT
  // E1002 Spectra 6 panel is sensitive to SPI clock — 200 kHz is reliable.
  // 2 MHz causes data corruption / blank screen on many units.
  // See: https://forum.seeedstudio.com/t/295136
  display.epd2.selectSPI(hspi, SPISettings(200000, MSBFIRST, SPI_MODE0));
#elif defined(E1001_VARIANT)
  display.epd2.selectSPI(hspi, SPISettings(2000000, MSBFIRST, SPI_MODE0));
#endif

  pinMode(BTN_LEFT, INPUT_PULLUP);
  pinMode(BTN_RIGHT, INPUT_PULLUP);
  pinMode(BTN_GREEN, INPUT_PULLUP);

  esp_sleep_wakeup_cause_t wakeCause = esp_sleep_get_wakeup_cause();
  bool btnWake = (wakeCause == ESP_SLEEP_WAKEUP_EXT1);

  if (rtc_first_boot) {
    rtc_first_boot = false; rtc_sleep_cycles = 0;
    showSplash();
    delay(500);
    refreshAndShow(0);
    enterUSBAwareSleep();
    return;
  }

  rtc_sleep_cycles++;

  if (btnWake) {
    int chosen = selectPage(rtc_active_page);
    if (chosen >= 0) refreshAndShow(chosen);
    enterUSBAwareSleep();
    return;
  }

  uint32_t healthCycles = (HEALTH_INTERVAL_HOURS * 3600) / DEEP_SLEEP_SECONDS;
  if (rtc_sleep_cycles >= healthCycles) {
    refreshAndShow(rtc_active_page);
    enterUSBAwareSleep();
    return;
  }

  bleTriggered = false;
  startBLE();
  unsigned long adStart = millis();
  while (!bleTriggered && (millis() - adStart) < ADVERTISE_TIMEOUT_S * 1000UL) delay(50);
  NimBLEDevice::deinit(true);
  delay(200);

  if (bleTriggered) refreshAndShow(rtc_active_page);
  enterUSBAwareSleep();
}

void loop() {}
