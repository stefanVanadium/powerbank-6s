# Powerbank 6S — Architecture, Safety & Connections

Single reference for schematic capture (`powerbank.kicad_sch`). All pin numbers, addresses, and passive values are verified against the PDFs in `datasheets/` (2026-11-19).

---

## 1. Safety Requirements (Wave 0 — 6S Li-ion, > 5 A)

Because this board handles a **6S removable Li-ion pack (15.0–25.2 V, > 50 Wh)** and up to **~6.5 A pack / 5 A per USB-C port**, the following protections are hard requirements, not optional notes:

1. **Primary hardware protection (autonomous, no MCU required):**
   - `BQ76952` runs in autonomous protection mode and directly drives the high-side back-to-back `CHG`/`DSG` N-MOSFETs (`TPN2R304PL`).
   - Hardware comparators enabled: **COV** (4.25 V/cell), **CUV** (2.75 V/cell), **OCC** (3.0 A), **OCD1** (8.0 A, ~100 ms), **OCD2** (12.0 A, ~10 ms), **SCD** (20–30 A, < 100 µs via 1 mΩ shunt).
   - Pack-level **15 A / 35 V fast SMD fuse** (`F1206HC15A0TM`) in series between `PACK_RAW+` and the `CHG`/`DSG` FETs as last-resort fault clearing.
2. **Reversed cell / missing cell protection:**
   - Cells are in series (`6S1P`): with `CHG`/`DSG` FETs OFF at startup, a reversed cell carries zero discharge current.
   - Every `VCx` tap has a **20 Ω** series resistor (`R_C`) + **220 nF** filter cap (`C_C`) per `BQ76952` datasheet Fig. 16-2 to limit fault current into the sense pins.
   - Firmware reads all 6 cell voltages before enabling `CHG`/`DSG`; any cell out of range (`< 2.5 V` or `> 4.25 V` or negative delta) keeps FETs OFF and highlights the offending slot on the TFT.
3. **Thermal protection (4× 10 kΩ NTC 103AT):**
   - `NTC_PACK1` (`BQ76952 TS1`, pin 21) & `NTC_PACK2` (`BQ76952 TS3`, pin 23): autonomous **OTC/OTD** (> 45 °C charge cutoff, > 60 °C discharge cutoff) and **UTC/UTD** (< 0 °C charge cutoff).
   - `NTC_QI2` (MCU ADC): near the Qi2 coil/cells — MCU disables `EN_12V` above 50 °C.
   - `NTC_PWR` (MCU ADC): near the BQ25756 converter bank — MCU throttles total PD power budget above 70 °C and shuts down ports above 85 °C.
   - Each `BQ25756` `TS` pin (pin 8) gets either a local 10 kΩ NTC or a fixed 10 kΩ resistor divider from `REGN` so Reverse Mode `BHOT`/`BCOLD` window is always valid.
4. **Port & bus isolation:**
   - Each USB-C port has `TVS2200` on `VBUS` + 2× back-to-back `TPN2R304PL` MOSFETs controlled by its PD controller (`GATE_VBUS`/`GATE_VSYS`).
   - Each USB-A port has `TPS25200` current-limit/short-circuit switch set to **2.0 A**.
   - **Total pack power budget**: MCU enforces **~100 W max** combined output across all ports (~6.5 A at 15 V empty pack, below typical 18650 7.65 A continuous rating).

---

## 2. Hierarchical Sheet Structure

Root sheet `powerbank.kicad_sch` instantiates 5 sub-sheets (with `usb_c_port.kicad_sch` reused 3×):

| Sheet file | Instances | Contents |
|---|---|---|
| `powerbank.kicad_sch` | 1 (root) | Top-level block diagram, inter-sheet power/signal buses, global power flags, mounting holes |
| `bms_6s.kicad_sch` | 1 | 6× Keystone 1042 holders, `BQ76952`, 1 mΩ Kelvin shunt, 15 A fuse, 2× `TPN2R304PL` (CHG/DSG), `VC` RC filters, `TS1`/`TS3` NTCs |
| `usb_c_port.kicad_sch` | **3** (`C1`, `C2`, `C3`) | `TYPE-C-31-M-17`, `TVS2200`, 2× `TPN2R304PL` (VBUS path), `TPS25751S`, `BQ25756`, 4× `TPN2R304PL`, `TMPC1265HP-100MG-D` (10 µH), 2 mΩ + 5 mΩ Kelvin shunts, local `I2Cc` bus. `ADCIN1`/`ADCIN2` address resistors passed in or set per instance. |
| `buck_5v_usba.kicad_sch` | 1 | `LM73605` (5 V / 5 A, 500 kHz, 4.7 µH), 2× `TPS25200` (2 A limit), 2× `TPS2514`, 2× `Type-A-AF90`. Also exports `5V_VCONN` to `PP5V` of all 3 PD controllers. |
| `buck_12v_qi2.kicad_sch` | 1 | `LMR36520` (12 V / 2 A, 400 kHz, 33 µH), Qi2 connector (2-pin header / wire pads), `NTC_QI2` connector |
| `mcu_ui.kicad_sch` | 1 | `LMR36506` (3.3 V / 0.6 A, 1 MHz, 15 µH), `STM32G071CBT6`, SWD header, 2× `TS-1088` buttons, TFT 1.54" ST7789 SPI connector (FPC TBD after panel arrives), `NTC_PWR`, status LEDs |

> **Critical design note on `PP5V` (VCONN):** Both `TPS25751S` and `TPS26750` require **5 V on `PP5V` (pins 28, 29)** to power `PP_CABLE` (VCONN) for **5 A e-marked cables** (required for S24+ 45 W PPS). Therefore `5V_RAIL` from `LM73605` feeds `PP5V` on all 3 USB-C sheets, and the MCU keeps `EN_5V` HIGH whenever any USB-C or USB-A port is active.

---

## 3. Power Tree

```
6S Cells (15.0–25.2 V)
  └─ PACK_RAW+ ── F1 (15 A) ── Q_CHG + Q_DSG (2x TPN2R304PL, BQ76952) ── PACK+
                                                                           ├─► USB-C1 BQ25756 (bidirectional, 65 W / solar MPPT)
                                                                           ├─► USB-C2 BQ25756 (reverse-only, 65 W)
                                                                           ├─► USB-C3 BQ25756 (reverse-only, 65 W)
                                                                           ├─► LM73605  ── 5V_RAIL (5 A, EN_5V)
                                                                           │                ├─► USB-A1 TPS25200 (2 A) + TPS2514
                                                                           │                ├─► USB-A2 TPS25200 (2 A) + TPS2514
                                                                           │                └─► PP5V (VCONN) on PD C1, C2, C3
                                                                           ├─► LMR36520 ── 12V_QI2 (2 A, EN_12V) ──► Qi2 TX module
                                                                           └─► LMR36506 ── 3V3 (0.6 A, EN tied to PACK+) ──► STM32, TFT, PD VIN_3V3
```

### Buck Inductors (verified JLC/LCSC 2026-11-19)

| Rail | IC | f_SW | Inductance | Min I_sat (DS) | Chosen Part | LCSC | Specs |
|---|---|---|---|---|---|---|---|
| 5 V / 5 A | `LM73605RNPR` | 500 kHz (`RT = 78.7 kΩ`) | 4.7 µH | ≥ 8.35 A | **TMPC1004H-4R7MG-D** | `C155155` | 4.7 µH, 17 A Isat, 10 A Irms, 15 mΩ, 11×10 mm |
| 12 V / 2 A | `LMR36520ADDAR` | 400 kHz (fixed) | 33 µH | ≥ 3.6 A | **CDRH129RNP-330MC** | `C278365` | 33 µH, 4.25 A Isat, 4 A Irms, 39.3 mΩ, 12×12 mm |
| 3.3 V / 0.6 A | `LMR36506RRPER` | 1000 kHz (`RT` set) | 15 µH | ≥ 1.11 A | **SWPA5040S150MT** | `C44888` | 15 µH, 2.3 A Isat, 2 A Irms, 112 mΩ, 5×5 mm |

---

## 4. I2C Bus Map & Addresses

### Shared MCU Bus — `I2C1` (3.3 V, 400 kHz, 4.7 kΩ pull-ups to `3V3`)

| Device | 7-bit Addr | Strap / Config | IRQ to MCU |
|---|---|---|---|
| `BQ76952` (BMS) | `0x08` | Fixed default (`0x10` W / `0x11` R) | `BMS_ALERT` (pin 25, OD active-low) |
| `PD_C1` (USB-C1) | `0x20` | `ADCIN1 = 7` (`LDO_3V3`), `ADCIN2 = 0` (`GND`) — SafeMode | `PD_C1_IRQ` (pin 10, OD active-low) |
| `PD_C2` (USB-C2) | `0x21` | `ADCIN1 = 0` (`GND`), `ADCIN2 = 0` (`GND`) — SafeMode | `PD_C2_IRQ` (pin 10, OD active-low) |
| `PD_C3` (USB-C3) | `0x22` | `ADCIN1 = 6` (`0.806×LDO_3V3`), `ADCIN2 = 0` (`GND`) — SafeMode | `PD_C3_IRQ` (pin 10, OD active-low) |

> **Boot patch loading:** No external EEPROM is populated on `I2Cc`. At boot, each PD controller sees no EEPROM at `0x50` and waits on `I2Ct` for the `STM32G071` to push its patch bundle (PBMs / Host Interface, TPS25751 §8.4.1 / TPS26750 §7.4.1).

### Private PD-to-Charger Buses — `I2Cc` (3× independent, 4.7 kΩ pull-ups to each PD's `LDO_3V3`)

- `PD_C1` (`I2Cc_SCL` pin 16 / `I2Cc_SDA` pin 15) → `BQ25756_C1` (`0x6B`)
- `PD_C2` (`I2Cc_SCL` pin 16 / `I2Cc_SDA` pin 15) → `BQ25756_C2` (`0x6B`)
- `PD_C3` (`I2Cc_SCL` pin 16 / `I2Cc_SDA` pin 15) → `BQ25756_C3` (`0x6B`)
- **Important:** `I2Cc_IRQ` (pin 17 on each PD) connects to its `BQ25756` `INT` (pin 3) with a 10 kΩ pull-up to `LDO_3V3` (**never tie `I2Cc_IRQ` to GND**).

---

## 5. BQ76952 6S Cell Tap Wiring (Critical)

Per `BQ76952.pdf` Table 16-3 (p. 75) & §10.1.2 (p. 36), **`VC1`, `VC2`, and `VC16` must always connect to real cells**:

| Cell | Positive Tap | Negative Tap | Series Filter |
|---|---|---|---|
| Cell 1 (bottom) | `VC1` (pin 15) | `VC0` (pin 16 → `VSS` via RC) | `R_C = 20 Ω`, `C_C = 220 nF` |
| Cell 2 | `VC2` (pin 14) | `VC1` (pin 15) | `R_C = 20 Ω`, `C_C = 220 nF` |
| Cell 3 | `VC3` (pin 13) | `VC2` (pin 14) | `R_C = 20 Ω`, `C_C = 220 nF` |
| Cell 4 | `VC4` (pin 12) | `VC3` (pin 13) | `R_C = 20 Ω`, `C_C = 220 nF` |
| Cell 5 | `VC5` (pin 11) | `VC4` (pin 12) | `R_C = 20 Ω`, `C_C = 220 nF` |
| *(unused)* | `VC6..VC14` (pins 10..2) | **Shorted directly to `VC5` (pin 11)** | Disable in `VCell Mode` register (`0x801F`) |
| **Cell 6 (top)** | **`VC16` (pin 48)** | **`VC15` (pin 1 → Cell 5+)** | `R_C = 20 Ω`, `C_C = 220 nF` |

- `BAT` (pin 47) connects to `PACK_RAW+` through 100 Ω + 1 µF filter (per Fig. 16-2).
- `CP1` (pin 46): 0.47 µF to `BAT` (pin 47).
- `REG18` (pin 24): 2.2 µF to `VSS` (internal only).
- `SRP` (pin 18) / `SRN` (pin 20): 100 Ω series + 100 nF differential across the 1 mΩ Kelvin shunt (`WSL25121L000FEA18`).
- `TS2` (pin 22): leave floating (or use for button wakeup from SHUTDOWN).

---

## 6. STM32G071CBT6 (LQFP-48) Pinout Assignment

| Pin | MCU Pin | Net Name | Direction / Alt | Function |
|---|---|---|---|---|
| 4 | `VBAT` | `3V3` | Power | Tie to `3V3` |
| 5 | `VREF+` | `3V3_ANA` | Power | Ferrite bead / 10 Ω + 100 nF + 1 µF |
| 6 | `VDD/VDDA` | `3V3` | Power | 100 nF + 4.7 µF decoupling |
| 7 | `VSS/VSSA` | `GND` | Power | Ground |
| 10 | `PF2-NRST` | `MCU_NRST` | In | 100 nF to GND, SWD header |
| 11 | `PA0` | `ADC_NTC_QI2` | `ADC_IN0` | Qi2 coil NTC (10 kΩ divider to `3V3_ANA`) |
| 12 | `PA1` | `ADC_NTC_PWR` | `ADC_IN1` | Converter area NTC (10 kΩ divider to `3V3_ANA`) |
| 13 | `PA2` | `ADC_NTC_C1` | `ADC_IN2` | USB-C1 connector NTC (10 kΩ divider to `3V3_ANA`) |
| 14 | `PA3` | `TFT_BLK` | Out (TIM2_CH4 PWM) | Display backlight PWM |
| 15 | `PA4` | `TFT_CS` | Out | ST7789 SPI chip select |
| 16 | `PA5` | `TFT_SCK` | `SPI1_SCK` (AF0) | ST7789 SPI clock |
| 17 | `PA6` | `TFT_DC` | Out | ST7789 Data/Command |
| 18 | `PA7` | `TFT_MOSI` | `SPI1_MOSI` (AF0) | ST7789 SPI data |
| 19 | `PB0` | `TFT_RST` | Out | ST7789 hardware reset |
| 20 | `PB1` | `EN_5V` | Out | Enable `LM73605` (100 kΩ pull-down) |
| 21 | `PB2` | `EN_12V` | Out | Enable `LMR36520` Qi2 buck (100 kΩ pull-down) |
| 22 | `PB10` | `USBA1_EN` | Out | Enable `TPS25200` USB-A1 |
| 23 | `PB11` | `USBA2_EN` | Out | Enable `TPS25200` USB-A2 |
| 24 | `PB12` | `USBA1_FLT` | In (pull-up) | Fault flag from `TPS25200` USB-A1 |
| 25 | `PB13` | `USBA2_FLT` | In (pull-up) | Fault flag from `TPS25200` USB-A2 |
| 26 | `PB14` | `BMS_DFETOFF` | Out | Hardware DSG FET inhibit to `BQ76952` pin 30 |
| 27 | `PB15` | `BMS_CFETOFF` | Out | Hardware CHG FET inhibit to `BQ76952` pin 29 |
| 28 | `PA8` | `BMS_RST_SHUT` | Out | Reset/Shutdown pulse to `BQ76952` pin 33 |
| 29 | `PA9` | `PD_C1_IRQ` | In (EXTI, pull-up) | `I2Ct_IRQ` from `PD_C1` |
| 32 | `PA10` | `PD_C2_IRQ` | In (EXTI, pull-up) | `I2Ct_IRQ` from `PD_C2` |
| 33 | `PA11` | `PD_C3_IRQ` | In (EXTI, pull-up) | `I2Ct_IRQ` from `PD_C3` |
| 34 | `PA12` | `BMS_ALERT` | In (EXTI, pull-up) | `ALERT` from `BQ76952` pin 25 |
| 35 | `PA13` | `SWDIO` | `SWDIO` | Debug / Flash header |
| 36 | `PA14-BOOT0` | `SWCLK` | `SWCLK` | Debug / Flash header (10 kΩ pull-down for normal boot) |
| 42 | `PB3` | `BTN_1` | In (EXTI, pull-up) | Side button 1 (active-low to GND) |
| 43 | `PB4` | `BTN_2` | In (EXTI, pull-up) | Side button 2 (active-low to GND) |
| 45 | `PB6` | `I2C1_SCL` | `I2C1_SCL` (AF6) | Shared I2C bus (4.7 kΩ pull-up to `3V3`) |
| 46 | `PB7` | `I2C1_SDA` | `I2C1_SDA` (AF6) | Shared I2C bus (4.7 kΩ pull-up to `3V3`) |
| 47 | `PB8` | `LED_STATUS` | Out | Optional status/heartbeat LED |
| 48 | `PB9` | `PG_5V` | In (pull-up) | `PGOOD` from `LM73605` |

---

## 7. Test Pads

Place 1.0 mm SMD test pads (or 1.5 mm for power rails) on:
- **Power:** `PACK_RAW+`, `PACK+`, `VBUS_C1`, `VBUS_C2`, `VBUS_C3`, `5V_RAIL`, `12V_QI2`, `3V3`, multiple `GND` loops
- **Control / Debug:** `I2C1_SCL`, `I2C1_SDA`, `I2Cc_C1_SCL/SDA`, `I2Cc_C2_SCL/SDA`, `I2Cc_C3_SCL/SDA`, `BMS_ALERT`, `SWD` (4-pin 1.27 mm or 2.54 mm header: `3V3`, `SWDIO`, `SWCLK`, `GND`, `NRST`)
- **USB-C CC:** `C1_CC1/CC2`, `C2_CC1/CC2`, `C3_CC1/CC2`
