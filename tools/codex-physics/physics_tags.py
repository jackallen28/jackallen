"""Editorial selections made after reading each candidate, not chapter tags.
M=motion, F=fields, E=electricity, L=light/relativity, S=investigation.
Zero means no direct match in the supplied 2024 Unit 3/4 knowledge list.
"""
MAP={}
def add(prefix, selections):
    for n,tag in enumerate(selections.split(),1):MAP[f'{prefix}{n:02d}']=tag
add('PH-C01-Q','0 M5 0 M1 M1 M1 M1 M1 M1 M1 M1 M1 M1 M1 M1 M1 M5 M5 M5 M5 M5 M5 M5 M5 M5 M5 M5+M1 M5 M5 M5 M5 M5 M5 M5 M5 M2 M2 M2 M2 M2 M2 M2 M2 M2 M2 M2 M4 M4+M9')
add('PH-C02-Q','M7 M7 M6 M6 M6 M6+M7 M6+M7 M1 M8 M9 M8 M9 M9 M9 M8 M8+F9 M9 M8+M9 M9 M9 M9 M6+M9 M6+M9 M6+M9 M6+M9 M9 M6+M9 M6 M7 M6+M1 M7 M7 M7')
add('PH-C03-Q','L22 L20 L22 L20 M1 0 0 L20 L22 L21 L20 L20 L19 L20 L20 L21 L25 L25 L25 L25 L25 L25 L25 L23 L25 L25+L20 L25+L26 L23+L25 L25 L25 L25 L26 L26+L25 L26+L25 L26 L27 L27 L27 L27 L27 L27 L27 L27 L27 L27 L27 L27 L27 L27 L28 L28 L28 L28')
add('PH-C04-Q','F8 F8 F8 F8 F3 F10 F8 F3 F11+F8 M2 M2 F10 F11 F11 F11 F11 F3 F11 F11 F11 F11 F9 F9+F11 F9 F10 F11')
add('PH-C05-Q','F12 F6 F6 F6 F6 F6 F6 F2 0 F6 F6 F6 F6 F2 0 F6 F6 F6 F6 F6 F6 F1 F6 F1 F2 F3 F2 F6 F3 F3 F3 F6 F6 F6 F6')
add('PH-C06-Q','F2 0 F2 F4 F12 F4 F4 F4 F4 F4 F13 F12+F13 F13 F13 F13 F13 F4 F7 F7 F13 F7 F7 F7 F14 F14+F15 F14+F15 F14 F14 F7 F7 F7 F7 F7 F7 F7 F7 F16 F6+F7 F6+F7 F6+F7')
add('PH-C07-Q','E1 E2 E1 E1 E2 E2 E2 E2 E2 E2 E2 E2 E2 E2 E3 E2+E1 E2 E2 E2 E2 E2 E2 E2 E6 E5+E6 E6')
add('PH-C08-Q','E7 E7 E7 E7 E7 E7 E7 E8+E7 E8+E7 E8 E8')
add('PH-C09-Q','L2 0 0 0 L2 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 L4 L4 L3 L4 L4 0 0 0 0 0 0 0 L5 L5 L5 L5 0 0 0 0')
add('PH-C10-Q','0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 L2 L2 0 0 0 0 0 0 L1 0 0 L5 L5 L15 L6 L6 L5 0 L5 L5 L6 L6 0 L1')
add('PH-C11-Q','L7 L7 L7 L7 L8 L8 L8 L8 L8 L8+L14 L8 L8 L8 L8 L8 L9')
add('PH-C12-Q','0 F7 L15 L15 L15 0 L15 0 L7 L7 L6 L12 F6+L7 L18 L12 L12+L11 L12 L12 L12 L12+L7 L13 L13 L7 L17 L14 L17 L15 L17 L17 0 0 0 0 0 L5 L5 0 0')
add('PH-C13-Q','S2+S6 S2')
add('PH-R1-','0 0 0 M1 M1 M5 M5 M5 M5 M2 M2 M2 M2 M4 M4')
add('PH-R2-','M7 M7 M6+M7 M8 M9 M9 M9 M9 M6+M9')
add('PH-R3-','L22 L22 L22 L22 M1 L22 L25 L25 L25 L24 L26+L25 L27 L27')
add('PH-R4-','F11 F8 F11 F11 F8 F9 F9 F11 F11')
add('PH-R5-','F3 F3 F6 F6 F8')
add('PH-R6-','F4 F13 F7')
add('PH-R7-','E2 E1 E2 E6')
add('PH-R8-','E7 E8+E7')
add('PH-R9-','0 L4')
add('PH-R10-','0 0 0 L6 L6 L2 L14')
add('PH-R11-','L14 L7 F6 L8 L8 F6 L7 L8 L8')
add('PH-R12-','L17 L17 L12 L12 F6 L11+L12 L14 0')
add('PH-R13-','S2 S2 S3')
add('PH-RA1-','0 0 0 0 0 0 0 0 0 0')
PREFIX={'M':'physics-u3-aos1-kk','F':'physics-u3-aos2-kk','E':'physics-u3-aos3-kk','L':'physics-u4-aos1-kk','S':'physics-u4-aos2-kk'}
def ids(code):return [] if code=='0' else [PREFIX[x[0]]+f'{int(x[1:]):02d}' for x in code.split('+')]
