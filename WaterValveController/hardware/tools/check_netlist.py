import sys, xml.etree.ElementTree as ET
t = ET.parse(sys.argv[1]).getroot()
nets = {}
for n in t.find('nets'):
    nodes = sorted((x.get('ref'), x.get('pin')) for x in n.findall('node') if not x.get('ref').startswith('#'))
    nets[n.get('name')] = nodes
comps = [c.get('ref') for c in t.find('components')]
print('components in netlist:', len(comps), ' '.join(sorted(comps)))
E = {
 '+12V': ['J2.1','F1.2','D1.1','C1.1','C2.1','U1.1','K1.4'],
 'GND': ['J1.2','D1.2','C1.2','C2.2','U1.2','C3.2','C4.2','J4.3','C5.2','C6.2','C7.2','SW1.2','D3.1','D4.1','D5.1',
         'A1.4','A1.29','C11.2','U2.1','C8.2','C9.2','R13.2','R14.2','R15.2','R16.2','J3.3','C10.2','J2.2',
         'R12.2','J5.3','K1.3','SV1.2','D2.2','FS1.3'],
 '+5V': ['U1.3','C3.1','C4.1','J4.1','R1.1','C6.1','R3.1','A1.27','C11.1','R17.1','J3.1','C10.1','J5.1',
         'K1.1','FS1.1'],
 'RF_5V': ['R17.2','C8.1','C9.1','U2.2'],
 'FUSE_IN': ['J1.1','F1.1'],
 'FLOW_IN': ['J4.2','R1.2','R2.1','FS1.2'],
 'FLOW': ['R2.2','C5.1','A1.5'],
 'BTN': ['R3.2','C7.1','SW1.1','A1.7'],
 'LED25': ['A1.8','R4.1'], 'LED50': ['A1.9','R5.1'], 'LED100': ['A1.10','R6.1'],
 'R4-D3': ['R4.2','D3.2'], 'R5-D4': ['R5.2','D4.2'], 'R6-D5': ['R6.2','D5.2'],
 'RELAY': ['A1.11','J3.2','K1.2'],
 'TX_5V': ['A1.14','R11.1'],
 'ESP_DATA': ['R11.2','R12.1','J5.2'],
 'RX_D0': ['U2.3','R7.1'], 'RX_D1': ['U2.4','R8.1'], 'RX_D2': ['U2.5','R9.1'], 'RX_D3': ['U2.6','R10.1'],
 'RF1': ['A1.19','R7.2','R13.1'], 'RF2': ['A1.20','R8.2','R14.1'],
 'RF3': ['A1.21','R9.2','R15.1'], 'RF4': ['A1.22','R10.2','R16.1'],
 'VALVE+': ['K1.5','SV1.1','D2.1'],
}
want = {k: sorted(tuple(x.split('.')) for x in v) for k, v in E.items()}
got = {k: v for k, v in nets.items()}
bad = 0
matched = set()
for name, nodes in want.items():
    hit = [k for k, v in got.items() if v == nodes]
    if hit:
        matched.add(hit[0]); print(f'OK   {name:9s} -> {hit[0]} ({len(nodes)} pins)')
    else:
        bad += 1
        best = max(got.items(), key=lambda kv: len(set(kv[1]) & set(nodes)))
        print(f'FAIL {name}: expected {nodes}\n      closest {best[0]}: {best[1]}')
for k, v in got.items():
    if k not in matched and len(v) > 1:
        bad += 1; print('UNEXPECTED NET', k, v)
singles = [(k, v) for k, v in got.items() if len(v) == 1]
print('single-pin nets (should be only no-connects):', len(singles))
for k, v in singles: print('   ', k, v)
print('RESULT', 'PASS' if bad == 0 else f'{bad} problems')
