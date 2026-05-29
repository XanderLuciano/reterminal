# HARDWARE.md — reTerminal E10xx IO Reference

Complete hardware peripheral map for the reTerminal E1001 and E1002. Both devices share identical pinouts; only the display panel differs.

## Pin Map

### Display (SPI2 / HSPI)

| Function | GPIO | Notes |
|---|---|---|
| SCK | 7 | HSPI clock, 2MHz |
| MOSI | 9 | HSPI data out |
| CS | 10 | Chip select |
| DC | 11 | Data/command |
| RESET | 12 | Display reset (active low) |
| BUSY | 13 | Display busy flag (active low) |

**E1001:** GDEY075T7 panel, UC8179 controller, 800×480 BW
**E1002:** GDEP073E01 panel, UC8179 controller, 800×480 Spectra 6 color

### Buttons

| Button | GPIO | Active | Notes |
|---|---|---|---|
| Green (confirm) | 3 | LOW (INPUT_PULLUP) | Also wakes from deep sleep |
| Right (next) | 4 | LOW (INPUT_PULLUP) | Also wakes from deep sleep |
| Left (prev) | 5 | LOW (INPUT_PULLUP) | Also wakes from deep sleep |

All three buttons are configured as `ESP_EXT1_WAKEUP_ANY_LOW` — pressing any button wakes the ESP32 from deep sleep.

### Buzzer

| Function | GPIO | Notes |
|---|---|---|
| Buzzer | 45 | PWM via LEDC channel 0, ~2.2kHz tone |

Driven via `tone(pin, frequency, duration)`. Beep patterns:
- Page indicator: 1 beep = page 0, 2 beeps = page 1, 3 beeps = page 2
- Confirm: ascending triple (1.8kHz → 2.2kHz → 2.6kHz)

### LED

| Function | GPIO | Active | Notes |
|---|---|---|---|
| Status LED | 6 | LOW (inverted) | Green LED, shared with software control |

LED behavior:
- **Triple pulse** (80ms on, 200ms off ×3): USB power connected, battery charging
- **Solid on**: Fully charged (USB connected)
- **Off**: Running on battery

### Battery Management (BMS)

#### Battery Voltage

| Function | GPIO | Notes |
|---|---|---|
| Voltage ADC | 1 | 12-bit, 12dB attenuation (~0-3.1V range) |
| Divider enable | 21 | HIGH to enable voltage divider for reading |

The battery connects through a 2:1 voltage divider. GPIO21 must be pulled HIGH to enable the divider (saves power when not reading). Actual voltage = ADC reading × 3.1V / 4095 × 2.0.

**Calibration curve (voltage → %):**

| Voltage | % | Voltage | % |
|---|---|---|---|
| ≥4.15V | 100% | ≥3.68V | 40% |
| ≥3.96V | 90% | ≥3.58V | 30% |
| ≥3.91V | 80% | ≥3.49V | 20% |
| ≥3.85V | 70% | ≥3.41V | 10% |
| ≥3.80V | 60% | ≥3.30V | 5% |
| ≥3.75V | 50% | <3.27V | 0% |

Battery capacity: **2000mAh** Li-Po.

#### Charger IC — Silergy SY6974B

| Parameter | Value |
|---|---|
| Bus | I2C1 |
| SDA | GPIO39 |
| SCL | GPIO40 |
| Address | 0x6B |
| Max charge current | 1000mA (0.5C) |
| Max charge voltage | 4.208V |

**Status register (REG0B at 0x0B):**

| Bit | Name | Description |
|---|---|---|
| 7-6 | CHRG_STAT | 00=idle, 01=precharge, 10=fast charge, 11=done |
| 5 | VBUS_STAT | 1=VBUS present (USB power connected) |
| 4 | THERM | Thermal regulation active |
| 3 | VSYS | VSYS regulation active |

To read: `Wire1` write 0x0B, request 1 byte.

### I2C Bus 0

| Function | GPIO | Notes |
|---|---|---|
| SDA | 19 | |
| SCL | 20 | |

Connected peripherals on I2C0:

| Device | Address | Description |
|---|---|---|
| SHT40 | 0x44 | Temperature + humidity sensor (Sensirion) |
| PCF8563 | 0x51 | Real-time clock (NXP) |

### UARTs

| UART | TX | RX | Notes |
|---|---|---|---|
| UART0 | GPIO43 | GPIO44 | Connected to CH341 USB-serial (debug console) |
| UART1 | GPIO17 | GPIO18 | Available, not used |

**Important:** `Serial` = USB Serial/JTAG (GPIO19/20) — NOT connected on E10xx. Always use `Serial0` for debug output.

### MicroSD

| Function | GPIO | Notes |
|---|---|---|
| CS | 2 | SPI0/1 interface |
| SCK | 14 | |
| MOSI | 15 | |
| MISO | 16 | |

Not used by current firmware. Available for data logging or image storage.

### GPIO Expansion Header

8-pin header on the back of the device:

| Pin | GPIO | Notes |
|---|---|---|
| 1 | 3.3V | Power output |
| 2 | GND | Ground |
| 3 | GPIO8 | |
| 4 | GPIO38 | Also connected to onboard RGB LED |
| 5 | GPIO42 | |
| 6 | GPIO41 | |
| 7 | GPIO47 | |
| 8 | GPIO48 | |

## Power Architecture

```
USB-C (5V)
  │
  ├─→ SY6974B charger IC (I2C1 @ 0x6B)
  │     ├─→ 2000mAh Li-Po battery
  │     └─→ STAT → GPIO6 LED (software-controlled)
  │
  └─→ 3.3V regulator → ESP32-S3 + peripherals
                         │
                         ├─→ GPIO21 → battery voltage divider enable
                         └─→ GPIO1 (ADC) ← battery voltage (÷2)
```

## Deep Sleep

| Wake source | Trigger |
|---|---|
| Timer | Every 60 seconds (DEEP_SLEEP_SECONDS) |
| Button press | Any button (GPIO3/4/5, EXT1 ANY_LOW) |

During deep sleep:
- ESP32-S3 core and most peripherals powered down
- RTC memory preserved (sleep cycle counter, active page, first-boot flag)
- PSRAM lost — framebuffer must be re-allocated after each wake
- Display retains last image (e-ink is persistent)
- Current draw: ~50µA

## ESP32-S3 Chip

| Parameter | Value |
|---|---|
| Chip | ESP32-S3R8 (QFN56) |
| CPU | Dual-core Xtensa LX7 @ 240MHz |
| SRAM | 512KB |
| PSRAM | 8MB (octal SPI) |
| Flash | 32MB (quad SPI) |
| Wi-Fi | 802.11b/g/n |
| Bluetooth | BLE 5.0 |
