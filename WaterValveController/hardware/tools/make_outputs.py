"""Builds the exports, BOM and import zip from the generated KiCad project.

Run from the hardware folder after tools/gen_schematic.py:
    python3 tools/gen_schematic.py . && python3 tools/make_outputs.py
"""
import csv
import json
import os
import subprocess
import zipfile

P = 'WaterValveController'
run = lambda *a: subprocess.run(a, check=True, capture_output=True)

run('kicad-cli', 'sch', 'export', 'pdf', '-o', f'{P}-schematic.pdf', f'{P}.kicad_sch')
run('kicad-cli', 'sch', 'export', 'svg', '-o', '.svg-tmp', f'{P}.kicad_sch')
os.replace(f'.svg-tmp/{P}.svg', f'{P}-schematic.svg')
os.rmdir('.svg-tmp')
run('kicad-cli', 'sch', 'export', 'netlist', '-o', f'{P}.net', f'{P}.kicad_sch')

parts = json.load(open('.parts.json'))
groups = {}
for p in parts:
    if p['ref'].startswith('#') or not p['in_bom']:
        continue
    key = (p['value'], p['fp'], p['on_board'])
    groups.setdefault(key, []).append(p)


def refkey(r):
    import re
    m = re.match(r'([A-Z]+)(\d+)', r)
    return (m.group(1), int(m.group(2)))


GROUP_DESC = {
    '100nF': 'Ceramic or MKT 100 nF: decoupling (C2, C3, C6, C9, C11) and button filter (C7)',
    '10k': 'Pull-ups: flow signal (R1), button (R3)',
    '1k': 'Series resistors: flow signal (R2), remote channels (R7-R10)',
    '100uF 16V': 'Electrolytic: 5 V rail at U1 (C4), relay header (C10)',
    '330': 'LED current limit, about 9 mA',
}
rows = []
for (value, fp, on_board), ps in groups.items():
    refs = sorted((p['ref'] for p in ps), key=refkey)
    descs = sorted({p['desc'] for p in ps})
    desc = descs[0] if len(descs) == 1 else GROUP_DESC.get(value, '; '.join(descs))
    rows.append([', '.join(refs), len(refs), value, desc,
                 fp.split(':')[-1] if fp else '', 'PCB' if on_board else 'off-board (at the valve)'])
rows.sort(key=lambda r: refkey(r[0].split(',')[0]))
with open(f'{P}-BOM.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['References', 'Qty', 'Value', 'Description', 'Footprint', 'Where'])
    w.writerows(rows)
    w.writerow(['(A1)', 2, '15-pin female header 2.54 mm', 'Sockets so the Nano can be unplugged', '', 'PCB'])
    w.writerow(['(U1)', 1, 'TO-220 heatsink', 'Only needed with an L7805', '', 'PCB'])

with zipfile.ZipFile(f'{P}-KiCad.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for name in (f'{P}.kicad_pro', f'{P}.kicad_sch', 'WaterValve.kicad_sym', 'sym-lib-table'):
        z.write(name, f'{P}/{name}')
os.remove('.parts.json')
print('ok')
