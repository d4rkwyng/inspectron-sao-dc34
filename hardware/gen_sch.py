#!/usr/bin/env python3
"""Generate dc34-sao.kicad_sch — DC34 Meme TV SAO schematic.

Netlist-first generated schematic: symbols from KiCad's stock libraries,
every pin connected via a global label placed exactly on the pin anchor.
Validated with `kicad-cli sch erc`. Pin map source of truth: firmware/pins.md.
"""

import os
import re
import uuid

KICAD_SYM = os.path.expanduser(
    "~/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")
OUT = os.path.join(os.path.dirname(__file__), "dc34-sao.kicad_sch")

ROOT_UUID = "e5a0446e-0000-4000-8000-dc34sa000001"
PROJECT = "dc34-sao"

# --------------------------------------------------------------------------
# Symbol library extraction
# --------------------------------------------------------------------------

def extract_block(txt, name):
    i = txt.find(f'(symbol "{name}"')
    if i < 0:
        raise KeyError(name)
    depth = 0
    j = i
    while True:
        if txt[j] == '(':
            depth += 1
        elif txt[j] == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    return txt[i:j + 1]


_lib_cache = {}

def lib_text(lib):
    if lib not in _lib_cache:
        _lib_cache[lib] = open(f"{KICAD_SYM}/{lib}.kicad_sym").read()
    return _lib_cache[lib]


def get_symbol(lib, name):
    """Return symbol block with lib-prefixed name, for lib_symbols."""
    blk = extract_block(lib_text(lib), name)
    if '(extends' in blk:
        raise ValueError(f"{lib}:{name} is derived; use its parent directly")
    blk = blk.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
    return blk


def get_pins(lib, name):
    """[(number, name, x, y, angle_deg)] from symbol def (all units)."""
    blk = extract_block(lib_text(lib), name)
    out = []
    for m in re.finditer(
            r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)'
            r'[\s\S]*?\(name "((?:[^"\\]|\\.)*)"[\s\S]*?\(number "((?:[^"\\]|\\.)*)"',
            blk):
        x, y, ang, nm, num = m.groups()
        out.append((num, nm, float(x), float(y), int(ang)))
    return out


# --------------------------------------------------------------------------
# Component table: (ref, lib, symbol, value, footprint, lcsc, (x, y), netmap)
# netmap: pin number -> net name, or "NC"
# --------------------------------------------------------------------------

FP_R = "Resistor_SMD:R_0402_1005Metric"
FP_C = "Capacitor_SMD:C_0402_1005Metric"
FP_C_BIG = "Capacitor_SMD:C_0805_2012Metric"

COMPONENTS = [
    # --- MCU ---
    ("U1", "MCU_RaspberryPi", "RP2040", "RP2040",
     "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm_ThermalVias",
     "C2040", (150, 130), {
        "1": "VDD", "10": "VDD", "22": "VDD", "33": "VDD", "42": "VDD",
        "49": "VDD",
        "2": "BADGE_SDA", "3": "BADGE_SCL",
        "4": "TFT_SCK", "5": "TFT_MOSI", "6": "TFT_DC",
        "7": "TFT_CS", "8": "TFT_RST", "9": "TFT_BL",
        "11": "NC", "12": "NC", "13": "NC", "14": "NC",
        "15": "BTN_CH_DOWN", "16": "BTN_CH_UP",
        "17": "BTN_MODE", "18": "NC",
        "19": "GND",              # TESTEN tied low
        "20": "XIN", "21": "XOUT",
        "23": "DVDD", "50": "DVDD",
        "24": "SWCLK", "25": "SWDIO", "26": "NC",   # RUN: internal ~50k pull-up (per Pico)
        "27": "LED_PWR", "28": "NC", "29": "NC", "30": "NC", "31": "NC",
        "32": "NC", "34": "NC", "35": "NC", "36": "NC",
        "37": "NC",
        "38": "SAO_GPIO1", "39": "SAO_GPIO2",
        "40": "NC", "41": "NC",
        "43": "VDD", "44": "VDD", "45": "DVDD",
        "46": "USB_DM", "47": "USB_DP", "48": "VDD",
        "51": "QSPI_SD3", "52": "QSPI_SCLK", "53": "QSPI_SD0",
        "54": "QSPI_SD2", "55": "QSPI_SD1", "56": "QSPI_SS",
        "57": "GND",
     }),
    # --- QSPI flash (W25Q128JVSIQ in 208mil SOIC-8; symbol = parent family) ---
    ("U2", "Memory_Flash", "W25Q32JVSS", "W25Q128JVSIQ",
     "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
     "C97521", (255, 70), {
        "1": "QSPI_SS", "2": "QSPI_SD1", "3": "QSPI_SD2", "4": "GND",
        "5": "QSPI_SD0", "6": "QSPI_SCLK", "7": "QSPI_SD3", "8": "VDD",
     }),
    # --- USB 5V -> 3.3V LDO (ME6211C33, 120mV dropout; symbol = pin-compatible family) ---
    ("U3", "Regulator_Linear", "AP2204K-1.5", "ME6211C33M5G-N",
     "Package_TO_SOT_SMD:SOT-23-5",
     "C82942", (55, 55), {
        "1": "VBUS", "2": "GND", "3": "VBUS", "4": "NC", "5": "V33U",
     }),
    # --- SAO header (male 2x3 on our board) ---
    ("J1", "Connector_Generic", "Conn_02x03_Odd_Even", "SAO_1.69bis",
     "Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical",
     "C65114", (40, 130), {
        "1": "VSAO", "2": "GND", "3": "BADGE_SDA", "4": "BADGE_SCL",
        "5": "SAO_GPIO1", "6": "SAO_GPIO2",
     }),
    # --- USB-C receptacle (USB2.0, 16 pin) ---
    ("J2", "Connector", "USB_C_Receptacle_USB2.0_16P", "TYPE-C-31-M-12",
     "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
     "C165948", (55, 225), {
        "A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND",
        "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
        "A5": "CC1", "B5": "CC2",
        "A6": "USB_C_DP", "B6": "USB_C_DP",
        "A7": "USB_C_DM", "B7": "USB_C_DM",
        "A8": "NC", "B8": "NC",
        "SH": "GND",
     }),
    # --- TFT: Newvisio N114-2413THBIG01-H13, 1.14" 135x240 ST7789V,
    #     13-pin solder-tab FPC (pinout from LCSC datasheet C2890618) ---
    ("J3", "Connector_Generic", "Conn_01x13", "N114-2413THBIG01-H13",
     "dc34-sao:TFT_FPC_13P_N114",
     "C2890618", (255, 150), {
        "1": "NC", "2": "NC", "3": "TFT_MOSI", "4": "TFT_SCK",
        "5": "TFT_DC", "6": "TFT_RST", "7": "TFT_CS", "8": "GND",
        "9": "NC", "10": "VDD", "11": "TFT_LEDK", "12": "TFT_LEDA",
        "13": "GND",
     }),
    # --- Power mux P-FET: badge 3.0V passes when USB absent ---
    ("Q1", "Transistor_FET", "TP0610T", "AO3401A",
     "Package_TO_SOT_SMD:SOT-23",
     "C15127", (85, 110), {
        "1": "VBUS", "2": "VDD", "3": "VSAO",
     }),
    # --- Backlight low-side NMOS (GP7 high = ON, PWM dimming) ---
    ("Q2", "Transistor_FET", "Q_NMOS_GSD", "AO3400A",
     "Package_TO_SOT_SMD:SOT-23",
     "C20917", (255, 200), {
        "1": "TFT_BL", "2": "GND", "3": "TFT_LEDK",
     }),
    # --- Schottky: LDO 3.3V -> VDD when on USB ---
    ("D1", "Device", "D_Schottky", "B5819W",
     "Diode_SMD:D_SOD-123",
     "C8598", (85, 55), {
        "1": "VDD", "2": "V33U",   # 1=K, 2=A
     }),
    # --- 12MHz crystal, 3225, with Pico-style loading ---
    ("Y1", "Device", "Crystal_GND24", "12MHz",
     "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
     "C9002", (110, 60), {
        "1": "XIN", "2": "GND", "3": "XTAL3", "4": "GND",
     }),
    # --- Buttons (active low to GND) ---
    ("SW1", "Switch", "SW_Push", "CH-",
     "dc34-sao:SW_TS-1187A", "C318884", (315, 60),
     {"1": "BTN_CH_DOWN", "2": "GND"}),
    ("SW2", "Switch", "SW_Push", "CH+",
     "dc34-sao:SW_TS-1187A", "C318884", (315, 80),
     {"1": "BTN_CH_UP", "2": "GND"}),
    ("SW3", "Switch", "SW_Push", "MODE",
     "dc34-sao:SW_TS-1187A", "C318884", (315, 100),
     {"1": "BTN_MODE", "2": "GND"}),
    ("SW4", "Switch", "SW_Push", "BOOT",
     "dc34-sao:SW_TS-1187A", "C318884", (315, 120),
     {"1": "BOOTSEL_SW", "2": "GND"}),
    # --- Resistors ---
    ("R1", "Device", "R", "1k", FP_R, "", (110, 85),
     {"1": "XOUT", "2": "XTAL3"}),
    ("R2", "Device", "R", "1k", FP_R, "", (315, 140),
     {"1": "QSPI_SS", "2": "BOOTSEL_SW"}),
    ("R3", "Device", "R", "1k", FP_R, "", (315, 160),
     {"1": "LED_PWR", "2": "LED_A"}),
    ("R5", "Device", "R", "100k", FP_R, "", (85, 85),
     {"1": "VBUS", "2": "GND"}),
    ("R6", "Device", "R", "1R", FP_R, "", (255, 225),
     {"1": "VDD", "2": "TFT_LEDA"}),
    ("R11", "Device", "R", "100k", FP_R, "", (285, 225),
     {"1": "TFT_BL", "2": "GND"}),
    ("R7", "Device", "R", "27R", FP_R, "", (110, 225),
     {"1": "USB_C_DP", "2": "USB_DP"}),
    ("R8", "Device", "R", "27R", FP_R, "", (110, 245),
     {"1": "USB_C_DM", "2": "USB_DM"}),
    ("R9", "Device", "R", "5.1k", FP_R, "", (110, 265),
     {"1": "CC1", "2": "GND"}),
    ("R10", "Device", "R", "5.1k", FP_R, "", (135, 265),
     {"1": "CC2", "2": "GND"}),
    # --- LEDs ---
    ("LED1", "Device", "LED", "green", "LED_SMD:LED_0603_1608Metric",
     "C72043", (345, 160), {"1": "GND", "2": "LED_A"}),
    # antenna-tip "signal" LEDs, driven by badge SAO GPIOs and/or GP26/27
    ("LED2", "Device", "LED", "red", "LED_SMD:LED_0402_1005Metric",
     "C130719", (345, 175), {"1": "GND", "2": "ANT_L"}),
    ("LED3", "Device", "LED", "red", "LED_SMD:LED_0402_1005Metric",
     "C130719", (345, 190), {"1": "GND", "2": "ANT_R"}),
    ("R12", "Device", "R", "470R", FP_R, "", (330, 175),
     {"1": "SAO_GPIO1", "2": "ANT_L"}),
    ("R13", "Device", "R", "470R", FP_R, "", (330, 190),
     {"1": "SAO_GPIO2", "2": "ANT_R"}),
    # --- Decoupling / bulk ---
    ("C1", "Device", "C", "33pF", FP_C, "C1562", (135, 60),
     {"1": "XIN", "2": "GND"}),
    ("C2", "Device", "C", "33pF", FP_C, "C1562", (135, 85),
     {"1": "XTAL3", "2": "GND"}),
    ("C3", "Device", "C", "100nF", FP_C, "", (190, 60), {"1": "VDD", "2": "GND"}),
    ("C4", "Device", "C", "100nF", FP_C, "", (205, 60), {"1": "VDD", "2": "GND"}),
    ("C5", "Device", "C", "100nF", FP_C, "", (220, 60), {"1": "VDD", "2": "GND"}),
    ("C6", "Device", "C", "100nF", FP_C, "", (190, 80), {"1": "VDD", "2": "GND"}),
    ("C7", "Device", "C", "100nF", FP_C, "", (205, 80), {"1": "VDD", "2": "GND"}),
    ("C8", "Device", "C", "100nF", FP_C, "", (220, 80), {"1": "VDD", "2": "GND"}),
    ("C9", "Device", "C", "100nF", FP_C, "", (190, 100), {"1": "VDD", "2": "GND"}),
    ("C10", "Device", "C", "100nF", FP_C, "", (205, 100), {"1": "VDD", "2": "GND"}),
    ("C11", "Device", "C", "100nF", FP_C, "", (220, 100), {"1": "VDD", "2": "GND"}),
    ("C12", "Device", "C", "100nF", FP_C, "", (190, 120), {"1": "DVDD", "2": "GND"}),
    ("C13", "Device", "C", "100nF", FP_C, "", (205, 120), {"1": "DVDD", "2": "GND"}),
    ("C14", "Device", "C", "1uF", FP_C, "", (220, 120), {"1": "DVDD", "2": "GND"}),
    ("C15", "Device", "C", "1uF", FP_C, "", (190, 140), {"1": "VDD", "2": "GND"}),
    ("C16", "Device", "C", "10uF", FP_C_BIG, "", (205, 140), {"1": "VDD", "2": "GND"}),
    ("C17", "Device", "C", "1uF", FP_C, "", (30, 55), {"1": "VBUS", "2": "GND"}),
    ("C18", "Device", "C", "1uF", FP_C, "", (30, 75), {"1": "V33U", "2": "GND"}),
    ("C19", "Device", "C", "10uF", FP_C_BIG, "", (30, 95), {"1": "VSAO", "2": "GND"}),
    ("C20", "Device", "C", "100nF", FP_C, "", (285, 150), {"1": "VDD", "2": "GND"}),
    ("C21", "Device", "C", "10uF", FP_C_BIG, "", (285, 170), {"1": "VDD", "2": "GND"}),
    # --- Test points ---
    ("TP1", "Connector", "TestPoint", "SWCLK",
     "TestPoint:TestPoint_Pad_1.5x1.5mm", "", (345, 200), {"1": "SWCLK"}),
    ("TP2", "Connector", "TestPoint", "SWDIO",
     "TestPoint:TestPoint_Pad_1.5x1.5mm", "", (360, 200), {"1": "SWDIO"}),
    ("TP3", "Connector", "TestPoint", "GND",
     "TestPoint:TestPoint_Pad_1.5x1.5mm", "", (375, 200), {"1": "GND"}),
    ("TP4", "Connector", "TestPoint", "VDD",
     "TestPoint:TestPoint_Pad_1.5x1.5mm", "", (390, 200), {"1": "VDD"}),
    # --- Power flags (nets sourced only through passives/connectors) ---
    ("#FLG01", "power", "PWR_FLAG", "PWR_FLAG", "", "", (30, 120), {"1": "VSAO"}),
    ("#FLG02", "power", "PWR_FLAG", "PWR_FLAG", "", "", (45, 120), {"1": "VBUS"}),
    ("#FLG03", "power", "PWR_FLAG", "PWR_FLAG", "", "", (60, 120), {"1": "VDD"}),
    ("#FLG04", "power", "PWR_FLAG", "PWR_FLAG", "", "", (75, 120), {"1": "GND"}),
]

# --------------------------------------------------------------------------
# Emit
# --------------------------------------------------------------------------

def u():
    return str(uuid.uuid4())


def esc(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')


def prop(name, value, x, y, hide=False):
    h = "(hide yes)" if hide else ""
    return (f'    (property "{name}" "{esc(value)}" (at {x:.4f} {y:.4f} 0) '
            f'(effects (font (size 1.27 1.27)) {h}))')


def main():
    lib_syms = {}
    body = []
    labels = []       # (net, x, y, angle)
    noconnects = []
    anchors = {}      # (x,y) -> (ref, net) for collision check

    for ref, lib, sym, value, fp, lcsc, (ox, oy), netmap in COMPONENTS:
        # snap origins to the 1.27mm grid so pin anchors land on-grid
        ox = round(round(ox / 1.27) * 1.27, 4)
        oy = round(round(oy / 1.27) * 1.27, 4)
        key = f"{lib}:{sym}"
        if key not in lib_syms:
            lib_syms[key] = get_symbol(lib, sym)
        pins = get_pins(lib, sym)
        pin_nums = {p[0] for p in pins}
        missing = pin_nums - set(netmap)
        extra = set(netmap) - pin_nums
        assert not missing, f"{ref}: unmapped pins {sorted(missing)}"
        assert not extra, f"{ref}: bogus pins {sorted(extra)}"

        lines = [f'  (symbol (lib_id "{key}") (at {ox} {oy} 0) (unit 1)']
        lines.append('    (exclude_from_sim no) (in_bom yes) (on_board yes) '
                     f'(dnp no) (uuid "{u()}")')
        lines.append(prop("Reference", ref, ox, oy - 2.54))
        lines.append(prop("Value", value, ox, oy + 2.54))
        lines.append(prop("Footprint", fp, ox, oy, hide=True))
        lines.append(prop("Datasheet", "", ox, oy, hide=True))
        if lcsc:
            lines.append(prop("LCSC", lcsc, ox, oy, hide=True))
        for num in sorted(pin_nums):
            lines.append(f'    (pin "{num}" (uuid "{u()}"))')
        lines.append(f'    (instances (project "{PROJECT}" '
                     f'(path "/{ROOT_UUID}" (reference "{ref}") (unit 1))))')
        lines.append('  )')
        body.append("\n".join(lines))

        seen_pts = set()
        for num, _name, px, py, ang in pins:
            ax = round(ox + px, 4)
            ay = round(oy - py, 4)
            net = netmap[num]
            pt = (ax, ay)
            if pt in seen_pts:
                continue  # stacked pins share one label
            seen_pts.add(pt)
            if pt in anchors:
                raise SystemExit(
                    f"PIN COLLISION at {pt}: {ref}/{net} vs {anchors[pt]}")
            anchors[pt] = (ref, net)
            if net == "NC":
                noconnects.append(pt)
            else:
                out_ang = (ang + 180) % 360
                labels.append((net, ax, ay, out_ang))

    label_txt = []
    for net, x, y, ang in labels:
        justify = "left" if ang in (0, 90) else "right"
        label_txt.append(
            f'  (global_label "{net}" (shape bidirectional) (at {x} {y} {ang}) '
            f'(fields_autoplaced yes) (effects (font (size 1.27 1.27)) '
            f'(justify {justify})) (uuid "{u()}"))')
    nc_txt = [f'  (no_connect (at {x} {y}) (uuid "{u()}"))'
              for x, y in noconnects]

    doc = []
    doc.append('(kicad_sch (version 20250114) (generator "gen_sch") '
               f'(generator_version "1.0") (uuid "{ROOT_UUID}") (paper "A3")')
    doc.append('  (title_block (title "DC34 Meme TV SAO") (date "2026-07-16") '
               '(rev "A") (company "d4rkwyng"))')
    doc.append('  (lib_symbols')
    for blk in lib_syms.values():
        doc.append("    " + blk.replace("\n", "\n    "))
    doc.append('  )')
    doc.extend(nc_txt)
    doc.extend(label_txt)
    doc.extend(body)
    doc.append(f'  (sheet_instances (path "/" (page "1")))')
    doc.append('  (embedded_fonts no)')
    doc.append(')')

    with open(OUT, "w") as f:
        f.write("\n".join(doc) + "\n")
    nets = sorted({l[0] for l in labels})
    print(f"Wrote {OUT}")
    print(f"{len(COMPONENTS)} components, {len(labels)} labels, "
          f"{len(nc_txt)} no-connects, {len(nets)} nets")
    print("Nets:", ", ".join(nets))


if __name__ == "__main__":
    main()
