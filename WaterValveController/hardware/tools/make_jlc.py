"""JLCPCB assembly files for one board, written to that board's JLCPCB folder next to the
gerber zip from tools/gen_pcb.py, in the layout of JLCPCB's sample BOM and of the CPL file from
its KiCad guide:

    <board>-BOM-JLCPCB.csv / .xlsx   Comment, Designator, Footprint, JLCPCB Part #
    <board>-CPL-JLCPCB.csv           Designator, Mid X, Mid Y, Rotation, Layer (mm, degrees)
    README.md                        what to upload, what JLCPCB places and what you solder

Run from the hardware folder after tools/gen_pcb.py:
    python3 tools/make_jlc.py          # through-hole board (this folder)
    python3 tools/make_jlc.py smd      # mixed SMD + THT board (smd/)
"""
import csv
import os
import re
import sys

import openpyxl
import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jlc_parts import NOT_PLACED, PARTS  # noqa: E402

VARIANT = sys.argv[1] if len(sys.argv) > 1 else 'tht'
BOARD_DIR = 'smd' if VARIANT == 'smd' else '.'
P = 'WaterValveController-SMD' if VARIANT == 'smd' else 'WaterValveController'
OUT = os.path.join(BOARD_DIR, 'JLCPCB')

# JLCPCB's reels hold some packages at a different angle from KiCad's footprints. These are the
# usual corrections, the same ones the KiCad JLCPCB plugins apply; check them in JLCPCB's preview.
ROTATION_OFFSET = [
    (r'^SOT-223', 180), (r'^SOT-23', 180), (r'^SOT-353', 180), (r'^QFN-', 270), (r'^LQFP-', 270),
    (r'^TQFP-', 270), (r'^SOP-(?!18_)', 270), (r'^TSSOP-', 270), (r'^DFN-', 270), (r'^SOIC-', 270),
    (r'^VSSOP-', 270), (r'^CP_EIA-', 180), (r'^CP_Elec_', 180), (r'^C_Elec_', 180),
]


def package(name):
    """Short package name for the BOM's Footprint column, as in JLCPCB's sample BOM (0805,
    SOT-23, SMC ...); through-hole parts keep KiCad's footprint name."""
    for pattern, repl in ((r'^(?:R|C|L|LED)_(\d{4})_\d{4}Metric', r'\1'),
                          (r'^D_(SMA|SMB|SMC|SOD-\d+)$', r'\1'),
                          (r'^(SOIC|SOP|TQFP|LQFP|QFN|TSSOP|MSOP)-(\d+)_.*', r'\1-\2')):
        m = re.match(pattern, name)
        if m:
            return m.expand(repl)
    return name


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
        cpl.append([ref, f'{pcbnew.ToMM(c.x):.4f}', f'{-pcbnew.ToMM(c.y):.4f}', f'{rot % 360:g}',
                    'bottom' if fp.IsFlipped() else 'top'])
    if unknown:
        raise SystemExit('no JLCPCB entry for: ' + ', '.join(unknown))

    rows = []
    for (comment, _k), (lcsc, refs, names) in groups.items():
        names = sorted(set(names))
        prefix = os.path.commonprefix(names)
        name = names[0] if len(names) == 1 else prefix[:prefix.rfind('_')]
        rows.append([comment, ','.join(refs), package(name), lcsc])
    rows.sort(key=lambda r: refkey(r[1].split(',')[0]))
    write_bom(os.path.join(OUT, f'{P}-BOM-JLCPCB'), rows)
    with open(os.path.join(OUT, f'{P}-CPL-JLCPCB.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
        w.writerows(cpl)
    write_readme(rows, smd, tht, missing)
    print(f'{OUT}: {len(rows)} BOM lines, {len(cpl)} placements ({smd} SMD, {tht} through-hole); '
          f'no part number for: {", ".join(missing) or "none"}')


def write_bom(path, rows):
    """The BOM as CSV and as an .xlsx laid out like JLCPCB's sample BOM (JLCPCB takes either)."""
    with open(path + '.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'JLCPCB Part #'])
        w.writerows(rows)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Sheet1'
    ws.append(['Comment', 'Designator', 'Footprint', 'JLCPCB Part #（optional）'])
    for r in rows:
        ws.append(r)
    for col, width in zip('ABCD', (46, 28, 40, 22)):
        ws.column_dimensions[col].width = width
    wb.properties.creator = 'make_jlc.py'
    wb.save(path + '.xlsx')


def write_readme(rows, smd, tht, missing):
    board = 'mixed SMD + through-hole' if VARIANT == 'smd' else 'through-hole'
    lines = [
        f'# JLCPCB order files: {board} board',
        '',
        'Upload these three files on jlcpcb.com:',
        '',
        f'1. **`{P}-gerbers.zip`**: the PCB itself (copper, solder mask, silkscreen, outline, drill files).',
        '   PCB options: 2 layers, 1.6 mm, 1 oz copper (the defaults), any colour, HASL or ENIG.',
        f'2. **`{P}-BOM-JLCPCB.csv`** (or the same list as `.xlsx`, laid out like JLCPCB\'s sample',
        '   BOM): the parts list (Comment, Designator, Footprint, JLCPCB Part #).',
        f'3. **`{P}-CPL-JLCPCB.csv`**: where each part goes (Designator, Mid X, Mid Y, Rotation,',
        '   Layer; millimetres and degrees).',
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
        '## Making these files again in KiCad',
        '',
        'Every part carries its number in an **LCSC Part #** field (on the schematic symbol and on',
        'the footprint). After changing the design in KiCad 8, 9 or 10, the free **Fabrication',
        'Toolkit** plugin (KiCad Plugin and Content Manager) makes the gerbers, `bom.csv` and',
        '`positions.csv` in this same format in one click, applying the same rotation corrections.',
        'Exclude A1 and the mounting holes from its BOM, as here.',
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
