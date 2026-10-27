"""Packs the dashboard into the firmware.

    python3 tools/make_page.py

Reads web/index.html and the logo (web/logo.svg), puts the logo into the page with the
water drop in blue and the lettering in the page's text colour, and writes:

    web_page.h            the page gzipped, as a C array for the ESP32 (WEB_PAGE_GZ)
    web/preview.html      the same page with web/demo.js added: open it in any browser to
                          try the dashboard without the hardware (a simulated controller)
"""
import gzip
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(HERE, 'web')


def logo_svg():
    svg = open(os.path.join(WEB, 'logo.svg'), encoding='utf-8').read()
    paths = re.findall(r'<path\b[^>]*/>', svg)
    out = []
    for i, p in enumerate(paths):
        d = re.search(r'\bd="([^"]*)"', p).group(1)
        # 1 decimal place is far finer than the logo is ever shown
        d = re.sub(r'-?\d+\.\d+', lambda m: f'{float(m.group()):.1f}'.rstrip('0').rstrip('.'), d)
        d = re.sub(r'\s+', ' ', d).strip()
        t = re.search(r'transform="([^"]*)"', p)
        t = t.group(1) if t else ''
        t = re.sub(r'-?\d+\.\d+', lambda m: f'{float(m.group()):.1f}'.rstrip('0').rstrip('.'), t)
        # the first path is the water drop
        fill = 'url(#dropg)' if i == 0 else 'currentColor'
        out.append(f'<path d="{d}" fill="{fill}"' + (f' transform="{t}"' if t else '') + '/>')
    # crop the 2060 x 763 canvas to the artwork (measured: x 96-1987, y 52-677)
    return ('<svg class="logo" viewBox="90 46 1904 638" role="img" aria-label="Aqua Tracka by VAT Watering" '
            'xmlns="http://www.w3.org/2000/svg">' + ''.join(out) + '</svg>')


def main():
    page = open(os.path.join(WEB, 'index.html'), encoding='utf-8').read()
    page = page.replace('<!--LOGO-->', logo_svg())
    data = gzip.compress(page.encode('utf-8'), 9, mtime=0)

    lines = ['// Made by tools/make_page.py from web/index.html - edit those, not this file.',
             '#pragma once',
             '#include <Arduino.h>',
             '',
             f'const size_t WEB_PAGE_GZ_LENGTH = {len(data)};',
             'const uint8_t WEB_PAGE_GZ[] PROGMEM = {']
    for i in range(0, len(data), 24):
        lines.append('  ' + ','.join(str(b) for b in data[i:i + 24]) + ',')
    lines.append('};')
    with open(os.path.join(HERE, 'web_page.h'), 'w') as f:
        f.write('\n'.join(lines) + '\n')

    demo = open(os.path.join(WEB, 'demo.js'), encoding='utf-8').read()
    preview = page.replace('<script>\n"use strict";', '<script>\n' + demo + '\n</script>\n<script>\n"use strict";', 1)
    with open(os.path.join(WEB, 'preview.html'), 'w', encoding='utf-8') as f:
        f.write(preview)
    print(f'page {len(page)} bytes, gzipped {len(data)} bytes -> web_page.h; web/preview.html written')


if __name__ == '__main__':
    main()
