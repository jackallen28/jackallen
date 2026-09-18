from pathlib import Path
import pdfplumber, pickle, re, json
R=Path(__file__).resolve().parent
src='/Users/jack/Downloads/jackallen/sources/physics/physics34textbook.pdf'
pages=[]
with pdfplumber.open(src) as pdf:
    for i,p in enumerate(pdf.pages):
        chars=[{k:c[k] for k in ['text','x0','x1','top','bottom','size','fontname','non_stroking_color']} for c in p.chars]
        objs=[]
        for kind,items in [('image',p.images),('curve',p.curves),('rect',p.rects),('line',p.lines)]:
            for o in items:
                objs.append(dict(kind=kind,**{k:o[k] for k in ['x0','x1','top','bottom']},color=o.get('non_stroking_color'),stroke=o.get('stroking_color')))
        text=p.extract_text() or ''
        pages.append(dict(page=i,width=p.width,height=p.height,chars=chars,objects=objs,text=text))
        p.close()
        if (i+1)%50==0:print(i+1,flush=True)
with (R/'physics-cache.pkl').open('wb') as f:pickle.dump(pages,f)
(R/'physics-clean-pages.txt').write_text('\n'.join(f'\n=== PDF {p["page"]+1} / PRINT {p["page"]-13} ===\n'+p['text'] for p in pages))
print('Cached',len(pages))
