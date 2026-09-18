from pathlib import Path
import re,json,pickle
R=Path(__file__).resolve().parent
exec((R/'extract_physics.py').read_text().split('CHSTART=')[0])
answers={};current=None;chapter=1
for n in range(383,389):
    p=P[n]
    for x0,x1 in [(48,305),(309,565)]:
        cs=[c for c in region(p,[x0,35,x1,749]) if body(c) or ('Bd' in c['fontname'] and c['size']>=10)]
        for l in lines(cs):
            t=l['text'].strip()
            if re.match(r'Chapter\s+\d+',t):chapter=int(re.search(r'\d+',t)[0]);current=None;continue
            if re.match(r'Page\s+\d+|Review questions',t):current=None;continue
            m=re.match(r'^(\d+\.\d+|\d+\.)\s*(.*)',t)
            first=sorted(l['chars'],key=lambda c:c['x0'])[0]
            if m and l['bbox'][0]<x0+13 and 'Bold' not in first['fontname']:
                number=m[1];t=m[2]
                if '.' in number[:-1]:a,b=number.split('.');key=f'PH-R{a}-{int(b):02d}'
                elif not number.endswith('.'):a,b=number.split('.');key=f'PH-R{a}-{int(b):02d}'
                else:key=f'PH-C{chapter:02d}-Q{int(number[:-1]):02d}'
                current=key;answers.setdefault(key,{'lines':[],'regions':[]})
            if current:
                answers[current]['lines'].append(t)
                answers[current]['regions'].append({'page':n,'bbox':l['bbox']})
(R/'physics-answers.json').write_text(json.dumps(answers,ensure_ascii=False,indent=2))
print('Answer entries',len(answers));print(list(answers.items())[:3])

worked=json.loads((R/'physics-worked-locations.json').read_text());prompts={}
for w in worked:
    m=re.search(r'([aA]?\d+)\s*\.\s*(\d+)',w['heading'])
    if not m:continue
    key=f'{m[1].upper()}.{int(m[2])}';p=P[w['page']];x0=w['bbox'][0]-6;y0=w['bbox'][3]+2
    sol=[l for l in lines([c for c in p['chars'] if 'Helvetica' in c['fontname'] and c['size']>=9]) if re.search(r'^solution',l['text'],re.I) and l['bbox'][1]>y0]
    if not sol:continue
    y1=min(l['bbox'][1] for l in sol);bb=[x0,y0,min(p['width']-4,x0+358),y1]
    text=inline([c for c in region(p,bb) if body(c)])
    if text:prompts[key]={'text':text,'page':w['page'],'bbox':bb,'figures':diagrams(p,[max(0,x0-160),y0,min(p['width']-4,x0+358),y1])}
(R/'physics-example-prompts.json').write_text(json.dumps(prompts,ensure_ascii=False,indent=2))
print('Worked prompts',len(prompts))
