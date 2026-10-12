"""JLCPCB assembly files for one board, written to that board's JLCPCB folder next to the
gerber zip from tools/gen_pcb.py:

    <board>-BOM-JLCPCB.csv   Comment, Designator, Footprint, JLCPCB Part #
    <board>-CPL-JLCPCB.csv   Designator, Mid X, Mid Y, Layer, Rotation (mm, degrees)
    README.md                what to upload, what JLCPCB places and what you solder yourself

Run from the hardware folder after tools/gen_pcb.py:
    python3 tools/make_jlc.py          # through-hole board (this folder)
    python3 tools/make_jlc.py smd      # mixed SMD + THT board (smd/)
"""
import csv
import os
import re
import sys

import pcbnew

VARIANT = sys.argv[1] if len(sys.argv) > 1 else 'tht'
BOARD_DIR = 'smd' if VARIANT == 'smd' else '.'
P = 'WaterValveController-SMD' if VARIANT == 'smd' else 'WaterValveController'
OUT = os.path.join(BOARD_DIR, 'JLCPCB')

# (value, footprint) -> (comment for JLCPCB, LCSC/JLCPCB part number). An empty part number
# means none was confirmed: pick one in JLCPCB's BOM step, or leave the part off and solder it.
PARTS = {
    # ---- parts on both boards ----
    ('470uF 25V', 'CP_Radial_D10.0mm_P5.00mm'): ('470uF 25V electrolytic, 10 x 12.5 mm', 'C368591'),
    ('100uF 16V', 'CP_Radial_D6.3mm_P2.50mm'): ('100uF 16V electrolytic, 6.3 x 11 mm', 'C911212'),
    ('47uF 16V', 'CP_Radial_D5.0mm_P2.00mm'): ('47uF 16V electrolytic, 5 x 11 mm', 'C134586'),
    ('3A blade (ATO)', 'Fuseholder_Blade_ATO_Keystone_3557-2'): ('Keystone 3557-2 ATO blade fuse holder',
                                                                 'C352820'),
    ('12V DC IN', 'TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal'):
        ('Screw terminal 2P 5.08 mm (KF128L-5.08-2P)', 'C474940'),
    ('MAIN SWITCH', 'TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal'):
        ('Screw terminal 3P 5.08 mm (KF128L-5.08-3P)', 'C474941'),
    ('VALVE / FLOW', 'TerminalBlock_Phoenix_MKDS-1,5-4-5.08_1x04_P5.08mm_Horizontal'):
        ('Screw terminal 4P 5.08 mm (DB128L-5.08-4P)', 'C2827883'),
    ('ESP32', 'JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical'): ('JST XH 4-pin header B4B-XH-A', 'C144395'),
    ('BUTTON', 'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'): ('JST XH 2-pin header B2B-XH-A', 'C158012'),
    ('LED 25L', 'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'): ('JST XH 2-pin header B2B-XH-A', 'C158012'),
    ('LED 50L', 'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'): ('JST XH 2-pin header B2B-XH-A', 'C158012'),
    ('LED 100L', 'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'): ('JST XH 2-pin header B2B-XH-A', 'C158012'),
    ('R-78E5.0-1.0 or L7805', 'TO-220-3_Vertical'): ('RECOM R-78E5.0-1.0 5 V switching regulator',
                                                    'C3033024'),
    ('RX480E-4', 'PinSocket_1x07_P2.54mm_Vertical'): ('7-pin female header 2.54 mm (receiver socket)',
                                                      'C6684533'),
    # ---- mixed SMD + THT board ----
    ('100nF', 'C_0805_2012Metric_Pad1.18x1.45mm_HandSolder'): ('100nF 50V X7R 0805', 'C49678'),
    ('10nF', 'C_0805_2012Metric_Pad1.18x1.45mm_HandSolder'): ('10nF 50V X7R 0805', 'C1710'),
    ('S3M', 'D_SMC'): ('S3M 3A 1000V diode', 'C388240'),
    ('IRFR5305', 'TO-252-2'): ('IRFR5305 P-MOSFET', 'C2624'),
    ('2N7002', 'SOT-23'): ('2N7002 N-MOSFET', 'C8545'),
    ('10k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('10k 1% 0805', 'C17414'),
    ('1k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('1k 1% 0805', 'C17513'),
    ('100k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('100k 1% 0805', 'C149504'),
    ('330', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('330R 1% 0805', 'C17630'),
    ('100', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('100R 1% 0805', 'C17408'),
    ('1.8k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('1.8k 1% 0805', 'C17398'),
    ('3.3k', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('3.3k 1% 0805', 'C114531'),
    ('10R', 'R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'): ('10R 1% 0805', 'C17415'),
    # ---- through-hole board ----
    ('100nF', 'C_Disc_D5.0mm_W2.5mm_P5.00mm'): ('100nF 50V X7R ceramic, 5.08 mm lead spacing', 'C84772'),
    ('10nF', 'C_Disc_D5.0mm_W2.5mm_P5.00mm'): ('10nF 50V X7R ceramic, 5.08 mm lead spacing', ''),
    ('1N5408', 'D_DO-201AD_P5.08mm_Vertical_KathodeUp'): ('1N5408 3A 1000V diode', 'C2460'),
    ('IRF9540N', 'TO-220-3_Vertical'): ('IRF9540NPBF P-MOSFET', 'C2575'),
    ('2N7000', 'TO-92_Inline_Wide'): ('2N7000 N-MOSFET', 'C232838'),
    ('10k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('10k 1% 1/4W metal film', 'C57436'),
    ('1k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('1k 1% 1/4W metal film', 'C57435'),
    ('1k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'): ('1k 1% 1/4W metal film', 'C57435'),
    ('100k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'): ('100k 1% 1/4W metal film', 'C58597'),
    ('330', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('330R 1% 1/4W metal film', 'C58608'),
    ('100', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('100R 1% 1/4W metal film', 'C57438'),
    ('10R', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical'): ('10R 1% 1/4W metal film', 'C57437'),
    ('1.8k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'): ('1.8k 1% 1/4W metal film', ''),
    ('3.3k', 'R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal'): ('3.3k 1% 1/4W metal film', ''),
}

# Left off the JLCPCB order: A1 is two 15-pin sockets under one reference (JLCPCB places one part
# per reference), H1-H4 are bare mounting holes
NOT_PLACED = {'A1': 'two 15-pin 2.54 mm female headers for the Nano (LCSC C2897378), solder them yourself'}

# JLCPCB's reel orientation differs from KiCad's footprint orientation for some packages
ROTATION_OFFSET = [(r'^SOT-23', 180)]


def refkey(r):
    m = re.match(r'([A-Z]+)(\d+)', r)
    return (m.group(1), int(m.group(2)))


def mid(fp):
    """Centre of the part. KiCad's SMD footprints have their origin at the centre already; a
    through-hole footprint's origin is pin 1, so the middle of its pads is used instead."""
    if fp.GetAttributes() & pcbnew.FP_SMD:
        return fp.GetPosition()
    bb = None
    for pad in fp.Pads():
        pb = pad.GetBoundingBox()
        if bb is None:
            bb = pcbnew.BOX2I(pb.GetOrigin(), pb.GetSize())
        else:
            bb.Merge(pb)
    return bb.GetCenter()


def main():
    board = pcbnew.LoadBoard(os.path.join(BOARD_DIR, P + '.kicad_pcb'))
    os.makedirs(OUT, exist_ok=True)
    groups, cpl, missing, unknown = {}, [], [], []
    smd = tht = 0
    for fp in sorted(board.GetFootprints(), key=lambda f: refkey(f.GetReference())):
        ref = fp.GetReference()
        if ref.startswith('H') or ref in NOT_PLACED:
            continue
        name = fp.GetFPID().GetLibItemName().wx_str()
        key = (fp.GetValue(), name)
        if key not in PARTS:
            unknown.append(f'{ref} {key}')
            continue
        comment, lcsc = PARTS[key]
        # one BOM line per part, even where it is fitted with two footprints (upright and flat)
        groups.setdefault((comment, lcsc or ref), (lcsc, [], []))
        groups[(comment, lcsc or ref)][1].append(ref)
        groups[(comment, lcsc or ref)][2].append(name)
        if not lcsc:
            missing.append(ref)
        if fp.GetAttributes() & pcbnew.FP_SMD:
            smd += 1
        else:
            tht += 1
        rot = fp.GetOrientationDegrees()
        for pattern, offset in ROTATION_OFFSET:
            if re.search(pattern, name):
                rot += offset
        c = mid(fp)
        # KiCad's position files and gerbers both use Y up, so Y is negated here as well
        cpl.append([ref, f'{pcbnew.ToMM(c.x):.4f}mm', f'{-pcbnew.ToMM(c.y):.4f}mm',
                    'Bottom' if fp.IsFlipped() else 'Top', f'{rot % 360:g}'])
    if unknown:
        raise SystemExit('no JLCPCB entry for: ' + ', '.join(unknown))

    rows = []
    for (comment, _k), (lcsc, refs, names) in groups.items():
        names = sorted(set(names))
        prefix = os.path.commonprefix(names)
        name = names[0] if len(names) == 1 else prefix[:prefix.rfind('_')]
        rows.append([comment, ','.join(refs), name, lcsc])
    rows.sort(key=lambda r: refkey(r[1].split(',')[0]))
    with open(os.path.join(OUT, f'{P}-BOM-JLCPCB.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'JLCPCB Part #'])
        w.writerows(rows)
    with open(os.path.join(OUT, f'{P}-CPL-JLCPCB.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        w.writerows(cpl)
    write_readme(rows, smd, tht, missing)
    print(f'{OUT}: {len(rows)} BOM lines, {len(cpl)} placements ({smd} SMD, {tht} through-hole); '
          f'no part number for: {", ".join(missing) or "none"}')


def write_readme(rows, smd, tht, missing):
    board = 'mixed SMD + through-hole' if VARIANT == 'smd' else 'through-hole'
    lines = [
        f'# JLCPCB order files: {board} board',
        '',
        'Upload these three files on jlcpcb.com:',
        '',
        f'1. **`{P}-gerbers.zip`**: the PCB itself (copper, solder mask, silkscreen, outline, drill files).',
        '   PCB options: 2 layers, 1.6 mm, 1 oz copper (the defaults), any colour, HASL or ENIG.',
        f'2. **`{P}-BOM-JLCPCB.csv`**: the parts list (Comment, Designator, Footprint, JLCPCB Part #).',
        f'3. **`{P}-CPL-JLCPCB.csv`**: where each part goes (Designator, Mid X, Mid Y, Layer, Rotation).',
        '',
        'Turn on **PCB Assembly**, assemble the **top side**, then upload the BOM and CPL files when asked.',
        f'All {smd + tht} parts are on the top side: {smd} SMD and {tht} through-hole.',
    ]
    if VARIANT == 'smd':
        lines += [
            '',
            'JLCPCB machine-places the SMD parts. The through-hole parts (terminals, JST headers, fuse',
            'holder, regulator, electrolytic capacitors, receiver socket) are soldered by hand or wave',
            'soldering at an extra cost per joint, shown on the order page. To keep the cost down, untick',
            'them in the BOM step and solder them yourself: they are all large and easy to solder.',
        ]
    else:
        lines += [
            '',
            'Almost every part on this board is through-hole, and JLCPCB charges extra per through-hole',
            'solder joint. For a board assembled by JLCPCB, the mixed SMD + THT board in `smd/JLCPCB/`',
            'is usually much cheaper. You can also order this board bare (gerbers only) and solder it.',
        ]
    lines += [
        '',
        '## Check in the placement preview',
        '',
        'JLCPCB shows each part on the board before you order. Rotate any part that does not sit',
        'on its pads, and check these in particular:',
        '',
    ]
    if VARIANT == 'smd':
        lines += [
            '- **D1 and D2 (S3M):** the cathode band goes on pad 1, at the closed end of the',
            '  silkscreen outline. A reversed D1 or D2 shorts the 12 V supply and blows the fuse.',
            '- **Q1 (IRFR5305, DPAK):** the large tab goes on the large pad, towards the top edge.',
            '- **Q2 (2N7002, SOT-23):** one pin on one side, two on the other, matching the pads.',
            '  The CPL already adds JLCPCB\'s usual 180° correction for SOT-23.',
        ]
    else:
        lines += [
            '- **D1 and D2 (1N5408):** the band (cathode) goes to the pad marked **K**. A reversed D1',
            '  or D2 shorts the 12 V supply and blows the fuse.',
            '- **Q1 (IRF9540N) and U1 (TO-220):** pin 1 on the square pad, metal tab towards the',
            '  outline\'s tab line.',
            '- **Q2 (2N7000):** the flat face matches the flat side of the outline.',
        ]
    lines += [
        '- **C1, C4, C8:** the + lead goes to the square pad (+ mark).',
        '',
        '## Not on the JLCPCB order',
        '',
    ]
    for ref, note in NOT_PLACED.items():
        lines.append(f'- **{ref}:** {note}.')
    lines += [
        '- **F1 fuse:** the holder is fitted; push in a 3 A ATO/ATC blade fuse.',
        '- **Off-board parts:** valve, flow sensor, rocker switch, panel button and LEDs, their JST',
        '  housings and crimped leads, and the M4 bolts (see the main BOM in the board folder).',
    ]
    if missing:
        lines += [
            '',
            '## Parts without a part number',
            '',
            'No JLCPCB part number was confirmed for: ' + ', '.join(missing) + '. In the BOM step,',
            'search JLCPCB\'s library for the value in the Comment column (any part with the same',
            'value and lead spacing fits), or untick them and solder them yourself.',
        ]
    lines += [
        '',
        '## Part numbers',
        '',
        '| Designator | Part | JLCPCB / LCSC |',
        '|---|---|---|',
    ]
    for comment, refs, _name, lcsc in rows:
        lines.append(f'| {refs.replace(",", ", ")} | {comment} | {lcsc or "(choose)"} |')
    lines += [
        '',
        'U2 is a gold-plated Samtec socket, the only 7-pin one found in JLCPCB\'s library; any 7-pin',
        '2.54 mm female header does the same job if you would rather fit a cheaper one yourself.',
        'Stock changes daily: if a part is out of stock, JLCPCB\'s BOM step offers alternatives.',
        '',
    ]
    with open(os.path.join(OUT, 'README.md'), 'w') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    main()
