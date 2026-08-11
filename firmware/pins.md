# DC34 Meme TV SAO — RP2040 pin map (single source of truth)

The schematic (hardware/gen_sch.py) and firmware (code.py) MUST both match
this table. GPIOs are chosen so each function sits on the QFN bank that
physically faces its target on the board.

| RP2040 GPIO | QFN pin | Net         | Function                              |
|-------------|---------|-------------|----------------------------------------|
| GP0         | 2       | BADGE_SDA   | I2C0 SDA — badge SAO bus (stretch)      |
| GP1         | 3       | BADGE_SCL   | I2C0 SCL — badge SAO bus (stretch)      |
| GP2         | 4       | TFT_SCK     | SPI0 SCK (hardware SPI0 ✓)              |
| GP3         | 5       | TFT_MOSI    | SPI0 TX (hardware SPI0 ✓)               |
| GP4         | 6       | TFT_DC      | ST7789 data/command                     |
| GP5         | 7       | TFT_CS      | ST7789 chip select                      |
| GP6         | 8       | TFT_RST     | ST7789 reset                            |
| GP7         | 9       | TFT_BL      | Backlight PWM, ACTIVE HIGH (low-side NMOS Q2) |
| GP12        | 15      | BTN_CH_DOWN | Tactile, active-low to GND              |
| GP13        | 16      | BTN_CH_UP   | Tactile, active-low to GND              |
| GP14        | 17      | BTN_MODE    | Tactile, active-low to GND              |
| GP16        | 27      | LED_PWR     | Power/status LED, active high           |
| GP26        | 38      | SAO_GPIO1   | SAO pin 5 + LEFT antenna LED (via 470R) |
| GP27        | 39      | SAO_GPIO2   | SAO pin 6 + RIGHT antenna LED (via 470R)|

BOOT button (SW4) is on QSPI_SS via 1k (R2) — hold at power-up for UF2
bootloader. Not a runtime GPIO.

RUN (pin 26) is left floating: the RP2040 has an internal ~50k pull-up on
RUN (the Pi Pico ships the same way). Reset = power cycle.

Dev rig: Raspberry Pi Pico + Waveshare Pico-LCD-1.14 hat. The hat uses its
own GP numbers (SPI GP10/11, DC/CS GP8/9, buttons GP15/17/3) — the
`DEV_RIG = True` block in `code.py` (set by `rigdeploy.py`) remaps them;
the firmware logic itself runs unmodified on rig and production board.

SAO header J1 (male 2x3 on our board's BACK, SAO 1.69bis), viewed from the
FRONT of the SAO:
```
top row:     GPIO2  SCL  GND
bottom row:  GPIO1  SDA  3.0V     <- 3.0V = pin 1
```
Matches the DC34 badge right-edge port drawing (spec sheet). The SAO is
designed to wear on the RIGHT badge port: max 21mm of board extends inboard
(left) of the header per the spec's tall-component line.

TFT panel: Newvisio N114-2413THBIG01-H13 (LCSC C2890618), 13-pin 0.7mm
solder-tab FPC, folded under the panel; pin 1 = TOP pad of the column (verified against the N114 mech drawing: landscape-tail-right + fold-under puts panel pin 1 at the top; silk "1" marks it)

Badge interactivity: antenna-tip LEDs hang on SAO GPIO1/GPIO2 — any badge
that pulses its SAO GPIOs (DC32-style demos) lights the antennas with no
firmware involvement. Firmware also serves a badge.team-style descriptor
("LIFE" magic) as an emulated EEPROM on I2C 0x50, and reacts to any badge
I2C contact with an antenna blip + TV-static burst.
