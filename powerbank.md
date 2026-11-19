# Powerbank

Author: Stefan Jipa

## Goal
a serious power bank, not an AliExpress toy: charges a phone (and anything USB-C) at full speed, lasts for years, the connector doesn't wear out.

## Requirements
- charges the S24+ at **Super Fast Charging 2.0 (45W)** = USB PD 3.0 **PPS** (~10V, up to 5A, 5A e-marked cable)
- **laptop** on the main USB-C port, PD up to **65W**
- ports: **3 USB-C + 2 USB-A**
- **pass-through**: a single charger on C1 charges the pack + a phone on another port at the same time
- **6 removable 18650 cells in series (6S1P)**. Insert them at different voltages, they equalize on their own (balancing), then you can take them out fully charged
- **solar**: no panel on the case. C1 accepts an external foldable solar panel (USB-C, 20-40W)
- **wireless**: ready-made magnetic **Qi2** module (coil + board + magnets) on one face
- **display**: percentage, voltage of each cell, W in/out, what each port is doing
- **MCU without WiFi/Bluetooth**
- built to last: real BMS, mechanically anchored connectors (THT legs), good parts. Budget: not a constraint
- **safety (Wave 0, 2026-11-19)**: autonomous hardware BMS protections via `BQ76952` (OV 4.25V, UV 2.75V, OCC 3A, OCD1 8A, OCD2 12A, SCD 20–30A via 1mΩ shunt) + 15A pack fuse; reverse-cell protection (CHG/DSG FETs open at boot, 20Ω/220nF RC on all `VCx` taps, MCU verifies all 6 cells before enabling FETs); thermal cutoffs on 4× 10kΩ NTCs (pack OTC/OTD autonomous on BQ76952, Qi2 > 50°C disables 12V buck, converter bank > 70°C throttles / > 85°C shuts down); VBUS `TVS2200` + back-to-back FETs per USB-C port; 2A `TPS25200` current limit per USB-A port; 100W total pack output cap (~6.5A at empty pack). Full details in [connections.md](connections.md).

## Cells
Decided 2026-11-19: **generic 18650 cells** (6S1P in Keystone 1042 holders; no cell-testing rig available, so the electronics and BMS handle generic 18650s safely within conservative limits). If cells change later, the electronics stay the same (still 6S):
| Cell | mAh | 6S | Notes |
|---|---|---|---|
| EVE 26V (current) | 2550 | ~55Wh | free, needs testing |
| Samsung 35E / LG MJ1 / Molicel M35A | 3500 | ~75Wh | 18650, same holders |
| 21700 (Samsung 50S, Molicel P45B) | 4500-5000 | 97-108Wh | 21700 holders; at 5000mAh you exceed 100Wh (airline limit) |

New cells only from reputable shops (nkon.nl); almost everything on AliExpress is fake.

## Architecture

```
USB-C1 (in/out, PPS, 65W, solar panel) ─ TVS ─ 2x FET ─ TPS25751S ─┐
                                                         BQ25756 ──┤ (bidirectional: forward = charge, reverse = output)
USB-C2 (out, PPS, 65W) ─ TVS ─ 2x FET ─ TPS25751S ─ BQ25756 (rev) ─┤
USB-C3 (out, PPS, 65W) ─ TVS ─ 2x FET ─ TPS25751S ─ BQ25756 (rev) ─┤
USB-A1/A2 ─ TPS25200 (2A limit) + TPS2514 ─ LM73605 5V/5A ─────────├─ PACK+ ─ 15A fuse ─ 2x FET (CHG/DSG) ─ removable 6S
Qi2 module (+ NTC near coil) ─ LMR36520 12V/2A ────────────────────┤               BQ76952: protection, balancing, current (1mΩ shunt)
LMR36506 3.3V ─ STM32G071 ─────────────────────────────────────────┘

STM32 ─ I2C1: 3x TPS25751S (target port, 0x20/0x21/0x22), BQ76952 (0x08) ─ SPI: display ─ buttons ─ EN: 5V buck, 12V buck
each PD controller ─ separate I2C (I2Cc) ─ its own BQ25756 (all have fixed address 0x6B)
```

- **each USB-C has its own converter**: phone on C2 at 10V and laptop on C3 at 20V work at the same time
- **all 3 USB-C ports are 100% identical hardware**: `TPS25751SRSMR` + `BQ25756` (one hierarchical sheet instantiated 3×). `TPS25751S` offers standalone PPS source control **only for TI chargers** (BQ25756, BQ25792 etc., datasheet §9.2.2.1) and directly drives the 2 back-to-back VBUS N-MOSFETs via `GATE_VBUS` / `GATE_VSYS` (decided 2026-11-19: switched C1 from `TPS26750`, which lacks `GATE_VBUS`/`GATE_VSYS` and is only needed for >20V EPR)
- **C1**: `TPS25751S` (DRP, PD 3.0 + PPS, 65W) + `BQ25756` (bidirectional + autonomous MPPT for external USB-C solar panel)
- **C2/C3**: `TPS25751S` + `BQ25756`, output only (configured source-only so they never try to charge the pack if a charger is plugged in)
- **VBUS**: 2 back-to-back MOSFETs driven by the PD controller (GATE_VBUS / GATE_VSYS) + TVS2200 (recommended in the datasheet). No separate eFuse needed
- **pass-through**: BQ25756 doesn't know part of the current goes out to the ports, so "pack full" is decided by the MCU from the real current measured by BQ76952
- **USB-A**: fixed 5V from LM73605, each port with TPS25200 (current limit, short protection) + TPS2514 (BC1.2 / Apple signaling). 2A per port, no QC
- **Qi2**: ready-made module, powered from LMR36520 (adjustable, 12V/2A), enabled by the MCU. Final voltage depends on the module bought
- **3.3V**: LMR36506 straight from the pack (rated up to 65V)
- **reversed cell / empty slot**: a reversed cell in a series pack carries no current while the circuit is open. BQ76952 sees the wrong voltage, the MCU keeps the CHG/DSG FETs off and shows which slot is wrong. + resistors on the BQ76952 VC inputs (per datasheet), + case with clearly marked polarity

## Components (BOM v1)

JLC prices / stock checked on 2026-10-20 (price at qty 1-9). All are "extended" (~$3 fee per part type at JLC).

### Power
| What | Part | LCSC | Package | Stock | Price | Qty |
|---|---|---|---|---|---|---|
| converter C1/C2/C3 | **BQ25756RRVR** | C19272232 | VQFN-36 5x6 | 616 | $5.27 | 3 |
| PD C1/C2/C3 | **TPS25751SRSMR** | C22460852 | VQFN-32 4x4 | 336 | $2.30 | 3 |
| MOSFET (all: BQ25756, VBUS, BMS) | **TPN2R304PL** 40V 2.3mΩ | C5802634 | TSON-8 3x3 | 1917 | $0.87 | 20 |
| BQ25756 inductor | **TMPC1265HP-100MG-D** 10µH 15.5A 13mΩ | C305223 | 13.5x12.5 | 1801 | $0.70 | 3 |
| BQ25756 input shunt | 2mΩ 2512 (LR2512-23R002F4) | C154685 | 2512 | 28084 | $0.19 | 3 |
| BQ25756 battery shunt | 5mΩ 2512 (LR2512-23R005F4) | C154688 | 2512 | 22791 | $0.14 | 3 |
| VBUS TVS | **TVS2200DRVR** | C523793 | WSON-6 2x2 | 588 | $0.58 | 3 |
| 6S BMS | **BQ76952PFBR** | C2862742 | TQFP-48 | 14886 | $2.95 | 1 |
| BMS shunt | 1mΩ 2512 (WSL25121L000FEA18) | C149567 | 2512 | 12215 | $0.19 | 1 |
| pack fuse | **F1206HC15A0TM** 15A 35V | C310991 | 1206 | 8048 | $0.35 | 1 |
| 5V/5A buck (USB-A) | **LM73605RNPR** | C473342 | WQFN-30 4x6 | 9283 | $2.59 | 1 |
| USB-A current limit | **TPS25200DRVR** | C128401 | WSON-6 2x2 | 20010 | $0.42 | 2 |
| USB-A signaling | **TPS2514DBVR** | C49754 | SOT-23-6 | 335 | $1.01 | 2 |
| 12V/2A buck (Qi2) | **LMR36520ADDAR** | C2879422 | SO-8 PowerPAD | 7158 | $1.20 | 1 |
| 3.3V | **LMR36506RRPER** | C2870127 | VQFN-9 2x2 | 2080 | $1.56 | 1 |
| 5V buck inductor (2026-11-19) | **TMPC1004H-4R7MG-D** 4.7µH 17A Isat 15mΩ | C155155 | 11x10 | 670 | $0.44 | 1 |
| 12V buck inductor (2026-11-19) | **CDRH129RNP-330MC** 33µH 4.25A Isat 39mΩ | C278365 | 12x12 | 2070 | $0.87 | 1 |
| 3.3V buck inductor (2026-11-19) | **SWPA5040S150MT** 15µH 2.3A Isat 112mΩ | C44888 | 5x5 | 9258 | $0.08 | 1 |

MOSFETs: 4 per BQ25756 (x3) + 2 back-to-back on each VBUS (x3) + 2 CHG/DSG on the BMS = 20. One type everywhere = one JLC fee.
Inductors: BQ25756 uses 10µH (`TMPC1265HP-100MG-D`); buck inductors verified on JLC/LCSC 2026-11-19 (`LM73605` @ 500 kHz → 4.7 µH, `LMR36520` @ 400 kHz → 33 µH, `LMR36506` @ 1 MHz → 15 µH).

### Control
| What | Part | LCSC | Package | Stock | Price | Qty |
|---|---|---|---|---|---|---|
| MCU | **STM32G071CBT6** | C432212 | LQFP-48 | 721 | $2.44 | 1 |
| display | **TFT IPS 1.54" 240x240, ST7789, SPI** | — AliExpress | FPC | | ~$4 | 1 |
| button | **TS-1088** (side) | C720477 | SMD | | ~$0.05 | 2 |

**Display**: buy the panel first and make the FPC footprint from its actual pinout (varies between sellers), same as mp3_player.

### Mechanical
| What | Part | LCSC | Stock | Price | Qty | Notes |
|---|---|---|---|---|---|---|
| USB-C | **TYPE-C-31-M-17** (6 pins, power only) | C283540 | 18366 | $0.20 | 3 | 5A, 20V, 4 THT shell legs. No USB data (not needed) |
| USB-A | **Type-A-AF90** (THT) | C53207796 | 178 | $0.12 | 2 | rated 1.5A per contact in the datasheet, like almost all of them; limited to 2A by TPS25200 |
| cell holder | **Keystone 1042** (18650, SMD) | C5249310 | 397 | $4.88 | 6 | expensive but solid |
| Qi2 | 15W TX module with magnets | — AliExpress | | ~$10-15 | 1 | to choose: input voltage, size |
| NTC | 10k 0402 | JLC basic | | | 4 | pack, Qi2, C1, converter area |

## Who solders what

Rule: JLC places only what can't be hand-soldered (QFN/DFN/WSON, pad underneath). Everything else at home, ordered from LCSC in the same cart.

### JLC (assembly) — ~13 extended types (~$39 in fees)
BQ25756, TPS26750, TPS25751, TPN2R304PL, TMPC1265 (inductor), TVS2200, LM73605, TPS25200, LMR36520 (pad underneath), LMR36506, the 2mΩ/5mΩ/1mΩ shunts (next to the ICs, reflowed), + passives from the **basic** list.

### Me (iron + flux)
| Part | Package | Difficulty |
|---|---|---|
| STM32G071 | LQFP-48 0.5mm | medium (drag soldering + flux + wick) |
| BQ76952 | TQFP-48 0.5mm | medium |
| TPS2514 | SOT-23-6 | easy |
| 15A fuse | 1206 | easy |
| USB-C x3 | SMD 6 pins + THT | easy (6 pins, wide pitch) |
| USB-A x2 | THT | easy |
| 18650 holders x6 | large SMD | easy, but needs a powerful iron (lots of copper) |
| buttons | SMD | easy |
| display | FPC | medium |
| Qi2 module | wires / connector | easy |

Order: JLC does the reflow, then at home STM32 + BQ76952 (fine pitch), then the rest. Cell holders last.

## Cost estimate (2026-10-20, to re-check when ordering)

Parts per board (qty 1-9): **~$96**
- ICs: ~$39 (3x BQ25756 15.8, TPS26750 3.0, 2x TPS25751 4.6, BQ76952 3.0, LM73605 2.6, STM32 2.4, TPS2514 2.0, TVS 1.7, LMR36506 1.6, LMR36520 1.2, TPS25200 0.8)
- MOSFETs: ~$17 (20 pcs)
- cell holders: ~$29
- inductors, shunts, fuse, connectors: ~$6
- passives: ~$5

Prototype (5 PCBs 4 layers, 2 assembled, leaded parts soldered at home):
| What | ~$ |
|---|---|
| 4-layer PCB x5 (thick outer copper: extra cost) | 25 |
| PCBA setup + stencil | 10 |
| extended fees (~13 x $3) | 39 |
| parts for 2 boards (JLC + LCSC) | 192 |
| shipping to RO | 15 |
| VAT 21% | 59 |
| **total** | **~340 (~1550 lei)** |

Extra (per unit): display ~20 lei, Qi2 module ~50-70 lei, case (3D print), cells (EVE free / new ~25-40 lei each).
If JLC requires "Standard" assembly for the 0.4mm-pitch QFNs (TPS26750/TPS25751) → +~$17.

## Design notes
- **currents**: pack 15-25.2V. All ports at max (3x 65W + 2x 10W + Qi2) is far beyond what the pack can do. The MCU allocates power: ~100W total budget from the pack (~6.5A at empty pack, below the cells' 7.65A). Wide traces, Kelvin shunts
- **heat**: Qi2 loses ~30%, the cells sit next to the coil → NTC, MCU disables wireless when hot
- **EasyEDA footprints** for the VQFNs (BQ25756, TPS26750/TPS25751) get checked against the datasheet land pattern during schematic
- **connectors**: USB-C with THT shell legs, the case takes the load, not the solder
- **display**: clearly shows what each port is doing (C1 input/output) and which slot has a problem
- **PD configuration**: TPS26750/TPS25751 are configured with TI's GUI (Application Customization Tool), then the image is loaded at boot (EEPROM on I2Cc or from the MCU)
- test pads: VBUS C1-C3, PACK+, 5V, 12V, 3V3, I2C (each bus), CC1/CC2 on each port

## Status (2026-11-19)

Done:
- [x] project cleaned up, new KiCad skeleton, repo renamed `powerbank-6s`
- [x] requirements + v1 architecture + Safety Wave 0
- [x] full BOM chosen (incl. buck inductors verified on JLC 2026-11-19), cost estimated
- [x] checked TPS25751 + TPS55289: **doesn't work** (standalone PPS source only with TI chargers) → C2/C3 moved to BQ25756
- [x] KiCad libraries (`lib/`, 18 parts with symbol + footprint + 3D) + 17 datasheets in `datasheets/`
- [x] `connections.md` written: Safety Wave 0, hierarchical sheet map, power tree, I2C map, BQ76952 6S VC16 tap map, STM32G071 LQFP-48 pinout, test pads
- [x] EasyEDA footprint audit completed + fixed `TPN2R304PL`, `BQ25756`, `LM73605` EP, `TPS25751S` EP paste, `USB-C` pad length
- [x] C1 switched from `TPS26750` → `TPS25751S` (all 3 USB-C ports identical, native `GATE_VBUS`/`GATE_VSYS`)
- [x] 3 buck inductors (`C155155`, `C278365`, `C44888`) imported into `lib/`
- [x] hierarchical schematic v1 generated (`powerbank.kicad_sch` + 5 sub-sheets, 241 components, 0 ERC errors, 0 duplicate refs) — ready for review

Next:
- [ ] review schematic in KiCad (`powerbank.kicad_pro`)
- [ ] buy the display + Qi2 module (when ready), replace generic SPI/Qi2 headers with exact FPC footprint / connector
- [ ] PCB layout (4 layers) & DRC

## Schematic
powerbank.kicad_sch

## Software
code.md

## Tests

### Cell sorting (before anything else)
Tools: 4-wire AC 1kHz internal resistance tester (**YR1035+**) + charger-analyzer (**Opus BT-C3100** / **SkyRC MC3000**) or electronic load (**Atorch DL24**).
1. inspection: no dents, leaks, rust; wrap intact (in a metal holder a torn wrap = short). Torn wrap → rewrap (PVC heat-shrink + insulator ring on +)
2. charge to 4.2V, let rest 1h
3. **internal resistance**: compare across cells and with the datasheet. One at ~2x the others → reject
4. **capacity**: discharge at 0.5A down to 2.75V, record mAh. Under ~2000mAh (80%) → reject
5. recharge to 4.2V, leave **2 weeks**, measure voltage again. Dropped noticeably more than the others (>~0.05V) → self-discharge, reject
6. pick 6 cells with the closest capacities (±5%) + 1-2 spares; write mAh and mΩ on each

## Resources
- datasheets: `datasheets/`
- EVE ICR18650/26V cells (datasheet, download manually from a browser): https://www.nkon.nl/amfile/file/download/file/269/product/4448
- Keystone 1042 (datasheet, download manually): https://www.keyelco.com
- Samsung, super fast charging S24: https://www.samsung.com/uk/support/mobile-devices/how-to-use-super-fast-charging-on-galaxy-s24-ultra-s24-plus-and-s24/
- TI BQ25756: https://ti.com/product/BQ25756 (app note BQ25756 EVM + TPS26750 EVM for USB-C EPR)
- TI TPS25751: https://ti.com/product/TPS25751 (sect. 9.2.2.1: PPS source only with TI chargers)
- JLC parts: https://jlcpcb.com/parts
- repo: https://github.com/stefanVanadium/powerbank-6s

### History
v0 (March 2026): 2S2P with BQ25713 + CYPD3177 + TPS61088 + IP2721/HUSB238 + BQ27441 + HY2120. Dropped: IP2721/HUSB238 are PD sinks (can't do output), TPS61088 is boost-only (can't make 5V from 2S), BQ27441 is single-cell, BQ25713 had no MCU to configure it, parallel cells can't be removable.

## KiCad libraries
- `lib/powerbank.kicad_sym` + `lib/powerbank.pretty` + `lib/powerbank.3dshapes`, registered in the project's `sym-lib-table` / `fp-lib-table`
- generated with `easyeda2kicad` from LCSC codes. New part: `easyeda2kicad --full --lcsc_id Cxxxx --output $PWD/lib/powerbank --project-relative`
- Keystone 1042: datasheet to download manually (LCSC doesn't have it)
