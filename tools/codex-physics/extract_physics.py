"""Geometry-assisted candidates. Editorial review is a separate required step."""
from pathlib import Path
from collections import Counter
import pickle,json,re,math
R=Path(__file__).resolve().parent
P=pickle.loads((R/'physics-cache.pkl').read_bytes())
SUP=str.maketrans('0123456789+-−–=()in','⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻⁼⁽⁾ⁱⁿ')
SUB=str.maketrans('0123456789+-−=()aeiox','₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎ₐₑᵢₒₓ')
def box(cs):return [min(c['x0'] for c in cs),min(c['top'] for c in cs),max(c['x1'] for c in cs),max(c['bottom'] for c in cs)]
def lines(chars):
    anchors=[c for c in chars if c['size']>=8.8 and c['text'].strip() and ('Utopia' in c['fontname'] or 'Helvetica' in c['fontname']) and c['text'] not in '°×−–']
    groups=[]
    for c in sorted(anchors,key=lambda c:c['bottom']):
        g=next((g for g in reversed(groups[-3:]) if abs(g['base']-c['bottom'])<2.3),None)
        if g is None:g={'base':c['bottom'],'chars':[]};groups.append(g)
        g['chars'].append(c)
    for c in chars:
        if c in anchors:continue
        if not c['text'].strip():continue
        near=[g for g in groups if abs((c['top']+c['bottom'])/2-(g['base']-5))<10]
        if near:
            g=min(near,key=lambda g:min(abs(c['x0']-a['x1'])+abs(c['bottom']-g['base'])*.2 for a in g['chars']))
            g['chars'].append(c)
        else:groups.append({'base':c['bottom'],'chars':[c]})
    out=[]
    for g in sorted(groups,key=lambda g:g['base']):
        cs=sorted(g['chars'],key=lambda c:c['x0']);s='';prev=None
        size=Counter(round(c['size'],1) for c in cs).most_common(1)[0][0]
        for c in cs:
            t=c['text']
            if c['size']<size*.85:
                d=c['bottom']-g['base']
                if d<-1:t=t.translate(SUP)
                elif d>1:t=t.translate(SUB)
            if prev and c['x0']-prev['x1']>1.4:s+=' '
            s+=t;prev=c
        out.append({'text':s,'bbox':box(cs),'size':size,'chars':cs})
    return out
def body(c):return 'Utopia' in c['fontname'] or 'STIX' in c['fontname'] or 'Symbol' in c['fontname']
def inline(cs):
    out=[]
    for l in lines(cs):
        t=l['text'].strip()
        if not t:continue
        if out and out[-1].endswith('-') and t[0].islower():out[-1]=out[-1][:-1]+t
        else:out.append(t)
    return '\n'.join(out)
def close(a,b,gap=10):return not(a[2]+gap<b[0] or b[2]+gap<a[0] or a[3]+gap<b[1] or b[3]+gap<a[1])
def union(a,b):return [min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]
def region(p,b):return [c for c in p['chars'] if b[0]<=((c['x0']+c['x1'])/2)<b[2] and b[1]<=((c['top']+c['bottom'])/2)<b[3]]
def diagrams(p,b):
    objs=[]
    for o in p['objects']:
        bb=[o['x0'],o['top'],o['x1'],o['bottom']]
        w=bb[2]-bb[0];h=bb[3]-bb[1]
        if not(b[0]-1<=bb[0] and bb[2]<=b[2]+1 and b[1]<=bb[1] and bb[3]<=b[3]):continue
        if w>540 or h>300 or (w<1 and h<1):continue
        if h<1 and w<60:continue # possible fraction; separately audited
        if h<1 and w>300:continue # separating rule
        objs.append(bb)
    # Connected graphics, then nearby small labels. Keep disconnected figures separate.
    groups=[]
    for bb in objs:
        hit=[x for x in groups if close(x,bb)]
        for x in hit:bb=union(bb,x);groups.remove(x)
        groups.append(bb)
    cs=region(p,b)
    result=[]
    for bb in groups:
        if bb[2]-bb[0]<12:continue
        labels=[c for c in cs if not body(c) and close(bb,[c['x0'],c['top'],c['x1'],c['bottom']],12) and c['size']<11 and 'Hv' not in c['fontname']]
        if labels:bb=union(bb,box(labels))
        if bb[3]-bb[1]<4:continue
        result.append([round(max(b[0],bb[0]-2),2),round(max(b[1],bb[1]-2),2),round(min(b[2],bb[2]+2),2),round(min(b[3],bb[3]+2),2)])
    return result

CHSTART=[2,47,72,107,129,145,166,183,198,226,260,289,327,346]
REVIEW=[41,67,104,126,142,162,180,195,222,255,286,323,345]
records=[];worked=[]
for n,p in enumerate(P):
    if not 15<=n<383:continue
    # Headings reconstructed independently of body lines.
    hs=lines([c for c in p['chars'] if 'Helvetica' in c['fontname'] and c['size']>=9.5 and 35<c['top']<748])
    for h in hs:
        if re.search(r'sample\s*problem',h['text'],re.I):worked.append({'page':n,'printed_page':n-13,'heading':h['text'],'bbox':h['bbox']})
        m=re.search(r'Revision question\s*([aA]?\d+)\s*\.\s*(\d+)',h['text'],re.I)
        if not m:continue
        x=h['bbox'][0]-6;y=h['bbox'][3]+2
        stops=[o['top'] for o in p['objects'] if o['kind']=='line' and isinstance(o.get('stroke'),str) and o['stroke'].startswith('P') and abs(o['bottom']-o['top'])<1 and o['x1']-o['x0']>250 and o['top']>y+4 and abs(o['x0']-x)<10]
        bottom=min(stops,default=747)
        # A long question can run to the next page; stops are recorded for review.
        right=min(p['width']-4,x+358)
        segs=[{'page':n,'bbox':[x,y,right,bottom]}]
        if bottom==747:
            nxt=P[n+1]
            stop=[o['top'] for o in nxt['objects'] if o['kind']=='line' and abs(o['bottom']-o['top'])<1 and o['x1']-o['x0']>250 and abs(o['x0']-x)<10 and o['top']>40]
            if stop:segs.append({'page':n+1,'bbox':[x,35,right,min(stop)]})
        texts=[];figs=[]
        for sg in segs:
            pg=P[sg['page']];cs=region(pg,sg['bbox'])
            # Revision prompts are set in semibold; regular body prose is not part of them.
            bc=[c for c in cs if body(c) and ('Semibold' in c['fontname'] or 'Bold' in c['fontname'] or 'STIX' in c['fontname'] or 'Symbol' in c['fontname'])]
            texts.append(inline(bc))
            fb=[max(0,x-160),sg['bbox'][1],right,sg['bbox'][3]]
            figs.extend({'page':sg['page'],'bbox':b,'role':'question'} for b in diagrams(pg,fb))
        text='\n'.join(texts)
        if text.strip():records.append({'id':f'PH-R{m[1].upper()}-{int(m[2]):02d}','chapter':m[1].upper(),'number':m[1]+'.'+m[2],'kind':'revision','segments':segs,'text':text,'figures':figs})

for chap,start in enumerate(REVIEW,1):
    a=start+13;b=CHSTART[chap]+13 if chap<len(CHSTART) else 359
    ordered=[];markers=[];question_started=False;columns={}
    for n in range(a,b):
        p=P[n]
        numchars=[c for c in p['chars'] if 'Helvetica' in c['fontname'] and 'Hv' in c['fontname'] and abs(c['size']-9)<.2 and c['text']=='.' and 35<c['top']<745]
        left=max([47,89],key=lambda a:sum(min(abs(c['x0']-(a+10)),abs(c['x0']-(a+269)))<9 for c in numchars))
        columns[n]=[(left,left+259),(left+259,left+518)]
        for col,(x0,x1) in enumerate(columns[n]):
            cs=region(p,[x0,35,x1,748]);ls=lines(cs)
            for l in ls:
                t=l['text']
                if t=='Questions':question_started=True
            # Exact number glyphs in heavy font are robust against formula digits.
            nums=lines([c for c in cs if 'Helvetica' in c['fontname'] and 'Hv' in c['fontname'] and abs(c['size']-9)<.2])
            for l in nums:
                m=re.fullmatch(r'(\d+)\.?',l['text'].replace(' ',''))
                if m and l['bbox'][0]<x0+14:
                    markers.append({'number':int(m[1]),'page':n,'col':col,'y':l['bbox'][1]-1})
            ordered.append((n,col))
    for j,m in enumerate(markers):
        end=markers[j+1] if j+1<len(markers) else {'page':b-1,'col':1,'y':747}
        segs=[];texts=[];figs=[]
        for n,col in ordered:
            if (n,col)<(m['page'],m['col']) or (n,col)>(end['page'],end['col']):continue
            x0,x1=columns[n][col]
            y0=m['y'] if (n,col)==(m['page'],m['col']) else 35
            y1=end['y'] if (n,col)==(end['page'],end['col']) else 748
            if y1<=y0:continue
            bb=[x0,y0,x1,y1];cs=region(P[n],bb)
            bc=[c for c in cs if body(c)]
            if bc:texts.append(inline(bc))
            ds=diagrams(P[n],bb)
            figs.extend({'page':n,'bbox':d,'role':'question'} for d in ds)
            if bc or ds:segs.append({'page':n,'bbox':bb})
        records.append({'id':f'PH-C{chap:02d}-Q{m["number"]:02d}','chapter':str(chap),'number':str(m['number']),'kind':'review','segments':segs,'text':'\n'.join(texts),'figures':figs})

(R/'physics-candidates.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
(R/'physics-worked-locations.json').write_text(json.dumps(worked,ensure_ascii=False,indent=2))
(R/'physics-candidates.txt').write_text('\n\n'.join(q['id']+' | p'+str(q['segments'][0]['page']-13)+' | '+str(len(q['figures']))+' figures\n'+q['text'] for q in records))
print('Candidates',len(records),'worked headings',len(worked));print(Counter((q['chapter'],q['kind']) for q in records))
