"""Builds the exports, BOM, board images and KiCad zip for one board.

Run from the hardware folder after tools/gen_schematic.py and tools/gen_pcb.py:
    python3 tools/make_outputs.py          # through-hole board (this folder)
    python3 tools/make_outputs.py smd      # mixed SMD + THT board (smd/)
"""
import csv
import glob
import os
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_pcb  # noqa: E402
from make_jlc import PARTS  # noqa: E402

VARIANT = sys.argv[1] if len(sys.argv) > 1 else 'tht'
HW = os.getcwd()
if VARIANT == 'smd':
    os.chdir('smd')
P = 'WaterValveController-SMD' if VARIANT == 'smd' else 'WaterValveController'
run = lambda *a: subprocess.run(a, check=True, capture_output=True)  # noqa: E731

if VARIANT == 'tht':
    # The schematic is the same for both boards, so only one copy of the drawings is kept
    run('kicad-cli', 'sch', 'export', 'pdf', '-o', f'{P}-schematic.pdf', f'{P}.kicad_sch')
    run('kicad-cli', 'sch', 'export', 'svg', '-o', '.svg-tmp', f'{P}.kicad_sch')
    os.replace(f'.svg-tmp/{P}.svg', f'{P}-schematic.svg')
    os.rmdir('.svg-tmp')
run('kicad-cli', 'sch', 'export', 'netlist', '-o', f'{P}.net', f'{P}.kicad_sch')

parts = __import__('json').load(open('.parts.json'))
groups = {}
for p in parts:
    if p['ref'].startswith('#') or not p['in_bom']:
        continue
    key = (p['value'], p['fp'], p['on_board'])
    groups.setdefault(key, []).append(p)


def refkey(r):
    m = re.match(r'([A-Z]+)(\d+)', r)
    return (m.group(1), int(m.group(2)))


GROUP_DESC = {
    '100nF': 'Ceramic 100 nF: decoupling (C2, C3, C6, C9, C10) and button filter (C7)',
    '10k': 'Pull-ups: flow signal (R1), button (R3), Q1 gate (R18); Q2 gate pull-down (R20)',
    '1k': 'Series resistors: flow signal (R2), remote channels (R7-R10), data from the ESP (R21)',
    '330': 'LED current limit, about 9 mA',
}
rows = []
for (value, fp, on_board), ps in groups.items():
    refs = sorted((p['ref'] for p in ps), key=refkey)
    descs = sorted({p['desc'] for p in ps})
    desc = '; '.join(descs) if len(descs) <= 2 else GROUP_DESC.get(value, '; '.join(descs))
    name = fp.split(':')[-1] if fp else ''
    # The receiver's entry in PARTS is its socket, listed on its own line below
    lcsc = '' if value == 'RX480E-4' else PARTS.get((value, name), ('', ''))[1]
    rows.append([', '.join(refs), len(refs), value, desc, name, 'PCB' if on_board else 'off-board (panel)', lcsc])
rows.sort(key=lambda r: refkey(r[0].split(',')[0]))
with open(f'{P}-BOM.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['References', 'Qty', 'Value', 'Description', 'Footprint', 'Where', 'JLCPCB / LCSC'])
    w.writerows(rows)
    w.writerow(['(A1)', 2, '15-pin female header 2.54 mm',
                'Sockets for the Nano. Solder the parts that sit under the Nano first', '', 'PCB', 'C2897378'])
    w.writerow(['(U2)', 1, '7-pin female header 2.54 mm', 'Socket for the RX480E-4 receiver module', '', 'PCB',
                PARTS[('RX480E-4', 'PinSocket_1x07_P2.54mm_Vertical')][1]])
    w.writerow(['(F1)', 1, '3 A ATO/ATC blade fuse', 'Standard automotive blade fuse for the F1 holder', '', 'PCB'])
    w.writerow(['(J4)', 1, 'JST-XH 4-pin housing + crimped lead', 'ESP32 link lead', '', 'off-board'])
    w.writerow(['(J5-J8)', 4, 'JST-XH 2-pin housing + crimped lead', 'Leads to the panel button and LEDs', '',
                'off-board'])
    w.writerow(['(U1)', 1, 'TO-220 heatsink', 'Only needed with an L7805; fits the marked area (18 x 19 mm)', '',
                'PCB'])
    w.writerow(['(H1-H4)', 4, 'M4 bolt + nut or standoff', 'Mounting', '', ''])

# Board images
os.makedirs(os.path.join(HW, 'images'), exist_ok=True)
prefix = os.path.join(HW, 'images', 'smd' if VARIANT == 'smd' else 'tht')
render_pcb.render(f'{P}.kicad_pcb', prefix, 12)
for svg in glob.glob(prefix + '-*.svg'):
    os.remove(svg)   # keep the PNGs only; the SVGs are large

with zipfile.ZipFile(f'{P}-KiCad.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    names = [f'{P}.kicad_pro', f'{P}.kicad_sch', f'{P}.kicad_pcb', f'{P}.kicad_dru', 'WaterValve.kicad_sym',
             'sym-lib-table']
    for name in names:
        z.write(name, f'{P}/{name}')
    # Both boards share the footprint library; the zip gets its own copy beside the project
    pretty = os.path.join(HW, 'WaterValve.pretty')
    for mod in sorted(glob.glob(os.path.join(pretty, '*.kicad_mod'))):
        z.write(mod, f'{P}/WaterValve.pretty/{os.path.basename(mod)}')
    z.writestr(f'{P}/fp-lib-table', '(fp_lib_table\n  (lib (name "WaterValve")(type "KiCad")'
               '(uri "${KIPRJMOD}/WaterValve.pretty")(options "")(descr "Board footprints"))\n)\n')
os.remove('.parts.json')
print('ok')
