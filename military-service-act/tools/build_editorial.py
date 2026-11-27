#!/usr/bin/env python3
"""Build editable Korean editorial diagrams from the reviewed content JSON.

Usage: python military-service-act/tools/build_editorial.py [content.json ...]
Requires Pillow and the Noto Sans CJK regular/bold fonts. Rasterization is
performed by render_editorial.cjs. No external service or private source needed.
"""
from pathlib import Path
from PIL import ImageFont
from functools import lru_cache
from collections import defaultdict
import argparse, copy, html, json, re, hashlib

ROOT = Path(__file__).resolve().parents[2]
SUBJECT = ROOT / 'military-service-act'
W, H = 1600, 1120
PAPER, INK, MUTED, RULE = '#FFFEFC', '#25241F', '#77756E', '#DFDDD6'
FAMILY = 'Noto Sans CJK KR,Noto Sans KR,sans-serif'
FONT_DIR = Path('/usr/share/fonts/opentype/noto')

@lru_cache(None)
def font(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR / ('NotoSansCJK-Bold.ttc' if bold else 'NotoSansCJK-Regular.ttc')), size, index=1)

def width(s, size=38, bold=False):
    return font(size, bold).getlength(str(s))

def wrap(s, max_width, size=38, bold=False):
    """Wrap at spaces or punctuation, never inside a Korean word."""
    result = []
    for paragraph in str(s).split('\n'):
        tokens = re.findall(r'[^\s·ㆍ/]+[·ㆍ/]?|\S', paragraph)
        # Keep actual spaces; allow a break after a middle dot or slash.
        tokens = re.findall(r'\S+\s*', paragraph)
        words = []
        for token in tokens:
            if width(token.rstrip(), size, bold) <= max_width:
                words.append(token)
            else:
                words.extend(re.findall(r'[^·ㆍ/]+[·ㆍ/]?\s*', token))
        line = ''
        for token in words:
            if width(token.rstrip(), size, bold) > max_width + 1:
                raise ValueError(f'Word too wide ({max_width}px): {token}')
            candidate = line + token
            if line and width(candidate.rstrip(), size, bold) > max_width:
                result.append(line.rstrip())
                line = token.lstrip()
            else:
                line = candidate
        if line.strip(): result.append(line.rstrip())
    return result or ['']

def ref_display(ref):
    ref=str(ref).replace('시행규칙','규칙').replace('시행령','영')
    ref=re.sub(r'제(\d+)항',lambda m:chr(0x2460+int(m[1])-1) if 1<=int(m[1])<=20 else m[0],ref)
    ref=re.sub(r'제(\d+)호',r'\1호',ref)
    return ref

def inline_ref(item,usable,ls):
    label=item.get('label','');ref=ref_display(item.get('ref',''))
    return bool(label and ref and '\n' not in label and width(label,ls,True)+width(ref,22)+24 <= usable)

def item_height(item, usable=624, size=38, layout='compare'):
    numeric = layout == 'numbers' and bool(re.fullmatch(r'[\d.,~∼〜–—\-\s년개월일세만억원%이하상]+',item.get('label',''))) and len(item.get('label','')) <= 10
    ls = 54 if numeric else 28
    label_lines = wrap(item.get('label',''), usable, ls, True) if item.get('label') else []
    body_lines = wrap(item['text'], usable, size)
    refs = wrap(ref_display(item.get('ref','')), usable, 22) if item.get('ref') and not inline_ref(item,usable,ls) else []
    return (len(label_lines)*(ls+10)+8 if label_lines else 0) + len(body_lines)*(size+15) + (len(refs)*30+10 if refs else 0) + 28

def section_height(section, usable=624, size=38, layout='compare'):
    return sum(item_height(i,usable,size,layout) for i in section['items'])

def paginate(entry):
    if entry['layout'] == 'flow':
        # Four steps at most, full-width text column.
        total = sum(max(100, sum(item_height(i,980,38,'flow') for i in s['items'])) for s in entry['sections'])
        budget = 600 if entry.get('takeaway') else 670
        if total + max(0,len(entry['sections'])-1)*18 <= budget: return [copy.deepcopy(entry)]
        out=[]; cur=[]; used=0; offset=0
        for s in entry['sections']:
            sh=max(100,sum(item_height(i,980,38,'flow') for i in s['items']))
            if cur and used+sh+len(cur)*18>budget:
                e=copy.deepcopy(entry);e['sections']=cur;e['_step_start']=offset;out.append(e);offset+=len(cur);cur=[];used=0
            cur.append(copy.deepcopy(s));used+=sh
        if cur:
            e=copy.deepcopy(entry);e['sections']=cur;e['_step_start']=offset;out.append(e)
        return out
    sections=entry['sections']
    available = 525 if entry.get('takeaway') else 595
    for size in (40,38,36):
        if all(section_height(s,624,size,entry['layout']) <= available for s in sections):
            e=copy.deepcopy(entry);e['_body_size']=size;return [e]
    remaining=[copy.deepcopy(s['items']) for s in sections]
    pages=[]
    while any(remaining):
        page=copy.deepcopy(entry);page['sections']=[];page['_body_size']=38
        for s,items in zip(sections,remaining):
            selected=[]; used=0
            while items:
                height=item_height(items[0],624,38,entry['layout'])
                if selected and used+height>available:break
                if height>available:raise ValueError('Single item too tall: '+str(items[0]))
                selected.append(items.pop(0));used+=height
            if selected:page['sections'].append({**s,'items':selected})
        pages.append(page)
    return pages

class SVG:
    def __init__(self,title,desc):
        self.parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc" lang="ko">',f'<title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(desc)}</desc>',f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']
        self.boxes=[]
    def text(self,s,x,y,size=38,bold=False,fill=INK,anchor='start',zone=None):
        s=str(s);tw=width(s,size,bold)
        left=x if anchor=='start' else x-tw
        top=y-size*1.15; bottom=y+size*.3
        if left < 58 or left+tw>1542 or top<12 or bottom>1114:
            raise ValueError(f'Text outside canvas: {s} ({left},{top},{tw},{bottom})')
        if zone and (left<zone[0]-1 or left+tw>zone[2]+1 or bottom>zone[3]+2):
            raise ValueError(f'Text outside zone: {s} ({left},{y},{tw}) zone={zone}')
        self.boxes.append({'text':s,'x':round(left,2),'y':y,'width':round(tw,2),'font_size':size,'role':zone and 'body' or 'header'})
        self.parts.append(f'<text x="{x}" y="{y}" font-family="{FAMILY}" font-size="{size}" font-weight="{700 if bold else 400}" fill="{fill}" text-anchor="{anchor}">{html.escape(s)}</text>')
    def line(self,x1,y1,x2,y2,color=RULE,sw=2):
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>')
    def path(self,d,color=INK,sw=2.6,fill='none'):
        self.parts.append(f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')
    def finish(self):return '\n'.join(self.parts+['</svg>'])+'\n'

def label_ref(key):
    _,kind,num=key.split('|');prefix={'본법':'병역법','시행령':'시행령','시행규칙':'시행규칙'}[kind]
    n=num.split('의');return f'{prefix} 제{n[0]}조'+('의'+n[1] if len(n)>1 else '')

def draw_item(s,item,x,top,usable,size,layout,zone):
    numeric=layout=='numbers' and bool(re.fullmatch(r'[\d.,~∼〜–—\-\s년개월일세만억원%이하상]+',item.get('label',''))) and len(item.get('label',''))<=10
    ls=54 if numeric else 28
    y=top
    in_ref=inline_ref(item,usable,ls)
    if in_ref:
        s.text(ref_display(item['ref']),x+usable,y+ls,22,False,MUTED,'end',zone=zone)
    if item.get('label'):
        for line in wrap(item['label'],usable,ls,True):
            s.text(line,x,y+ls,ls,True,INK if numeric else MUTED,zone=zone);y+=ls+10
        y+=8
    for line in wrap(item['text'],usable,size):
        s.text(line,x,y+size,size,zone=zone);y+=size+15
    if item.get('ref') and not in_ref:
        y+=10
        for line in wrap(ref_display(item['ref']),usable,22):
            s.text(line,x,y+22,22,False,MUTED,zone=zone);y+=30
    return y+28

def render(entry,lesson,diagram_no,total):
    ident=f"{entry['lecture_id']}-D{diagram_no:02d}-editorial-v1"
    desc=' / '.join(h['heading']+': '+'; '.join((i.get('label','')+' '+i['text']).strip() for i in h['items']) for h in entry['sections'])
    s=SVG(entry['title'],desc)
    s.text(f"병역법  /  {entry['lecture_id']}",80,74,25,True)
    s.text(f'개념·핵심 도식   {diagram_no:02d} / {total:02d}',1520,74,23,False,MUTED,'end')
    ts=64
    while width(entry['title'],ts,True)>1230 and ts>48:ts-=2
    if width(entry['title'],ts,True)>1230:raise ValueError('Title too long '+entry['title'])
    s.text(entry['title'],80,182,ts,True)
    sub=entry.get('subtitle','')
    ss=29
    while width(sub,ss)>1220 and ss>25:ss-=1
    if width(sub,ss)>1220:raise ValueError('Subtitle too long '+sub)
    s.text(sub,84,241,ss,False,MUTED)
    s.path('M1364 142 L1458 130 L1484 211 L1380 229 Z',fill='#F1EFEA')
    s.path('M1337 153 L1438 151 L1442 235 L1334 235 Z',fill=PAPER)
    s.path('M1356 175 L1416 174 M1355 191 L1416 190 M1354 207 L1392 207')
    s.line(80,284,1520,284)
    note=entry.get('takeaway','')
    end=948 if note else 1018
    sections=entry['sections']
    if entry['layout']=='flow':
        top=330
        heights=[max(100,sum(item_height(i,980,38,'flow') for i in sec['items'])) for sec in sections]
        gap=max(18,(end-top-sum(heights))/max(1,len(sections)))
        s.line(108,349,108,min(end-22,top+sum(heights)+gap*(len(heights)-1)-50),INK,2)
        for si,(sec,sh) in enumerate(zip(sections,heights),entry.get('_step_start',0)+1):
            # Clear the line behind the small number, leaving an editorial spine.
            s.parts.append(f'<rect x="76" y="{top+2}" width="72" height="55" fill="{PAPER}"/>')
            s.text(f'{si:02d}',80,top+39,31,True)
            hy=top+38
            for line in wrap(sec['heading'],315,36,True):
                s.text(line,164,hy,36,True);hy+=48
            iy=top
            for it in sec['items']:iy=draw_item(s,it,520,iy,1000,38,'flow',(520,top,1520,end))
            top+=max(sh,hy-top+16)+gap
    else:
        size=entry.get('_body_size',38)
        cols=[(80,1520)] if len(sections)==1 else [(80,760),(840,1520)]
        if len(sections)>2:raise ValueError('Non-flow layout requires 1 or 2 sections')
        if len(sections)==2:s.line(800,334,800,end-12)
        for si,(sec,(x,right)) in enumerate(zip(sections,cols)):
            hs=44
            while width(sec['heading'],hs,True)>right-x-30 and hs>36:hs-=2
            s.text(sec['heading'],x,371,hs,True)
            hw=width(sec['heading'],hs,True)
            if si==0:
                s.path(f'M{x} 386 C{x+hw*.28:.1f} 393 {x+hw*.72:.1f} 380 {x+hw+12:.1f} 386',sw=2.8)
            else:
                s.path(f'M{x-15} 342 C{x+hw*.1:.1f} 315 {x+hw*.82:.1f} 314 {x+hw+18:.1f} 338 C{x+hw+44:.1f} 362 {x+hw+12:.1f} 390 {x+hw*.75:.1f} 397 C{x+hw*.24:.1f} 408 {x-28} 385 {x-18} 357 Z',sw=2.2)
            usable=right-x-56;top=423
            used=section_height(sec,usable,size,entry['layout'])
            gap=max(0,min(72,(end-top-used)/max(1,len(sec['items'])-1)))
            if used>end-top+3:raise ValueError(f'Body too tall {ident} {used} > {end-top}')
            bracket_end=min(end-8,top+used+gap*max(0,len(sec['items'])-1)-30)
            s.path(f'M{x+25} {top+6} C{x+11} {top+6} {x+9} {top+16} {x+9} {top+30} L{x+9} {bracket_end-23:.1f} C{x+9} {bracket_end-6:.1f} {x+15} {bracket_end:.1f} {x+27} {bracket_end:.1f}',sw=2.3)
            for it in sec['items']:
                top=draw_item(s,it,x+48,top,usable,size,entry['layout'],(x+48,411,right,end))+gap
    if note:
        s.line(80,982,1520,982)
        lines=wrap(note,1398,27)
        if len(lines)>1:
            # This area is deliberately small; long qualifications belong in a diagram item.
            raise ValueError('Takeaway too long '+note)
        s.text(lines[0],84,1021,27,False,INK)
    s.line(80,1052,1520,1052)
    base=next((x for x in entry['source_keys'] if '|본법|' in x),entry['source_keys'][0])
    footer=f"{label_ref(base)} · {entry['lecture_id']} · 핵심 구조"
    s.text(footer,80,1092,23,False,MUTED)
    s.text('무한회독',1520,1092,23,True,INK,'end')
    return ident,s.finish(),s.boxes

def main():
    ap=argparse.ArgumentParser();ap.add_argument('content',nargs='*');ap.add_argument('--only',default='');args=ap.parse_args()
    paths=[Path(p) for p in args.content] or [SUBJECT/'editorial-content.json']
    entries=[]
    for p in paths:entries.extend(json.loads(p.read_text()))
    expanded=defaultdict(list)
    for n,e in enumerate(entries):
        if args.only and e['lecture_id'] not in args.only.split(','):continue
        pages=paginate(e)
        for i,part in enumerate(pages):
            part['_content_index']=n;part['_part']=i+1;part['_parts']=len(pages);expanded[e['lecture_id']].append(part)
    manifest={'schema_version':1,'subject':'military-service-act','subject_name':'병역법','style':'editorial-monochrome-v1','canvas':{'width':W,'height':H},'generated_date_kst':'2026-11-27','items':[]}
    bounds=[];errors=[]
    for lid,pages in sorted(expanded.items()):
        ln=int(lid.split('-')[1]);folder=SUBJECT/f'lesson-{ln:03d}'/'diagrams';folder.mkdir(parents=True,exist_ok=True)
        for i,e in enumerate(pages,1):
            try:ident,svg,boxes=render(e,None,i,len(pages))
            except Exception as ex:errors.append({'lecture_id':lid,'title':e['title'],'error':str(ex)});continue
            path=folder/(ident+'.svg');path.write_text(svg)
            clean={k:v for k,v in e.items() if not k.startswith('_')}
            manifest['items'].append({'id':ident,'lecture_id':lid,'lesson_number':ln,'diagram_number':i,'title':e['title'],'layout':e['layout'],'source_keys':e['source_keys'],'part':e['_part'],'parts':e['_parts'],'content_index':e['_content_index'],'files':{'svg':{'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}},'content':clean})
            bounds.append({'id':ident,'text_blocks':len(boxes),'min_body_font':min([b['font_size'] for b in boxes if b['role']=='body' and b['font_size']>=36] or [36]),'bounds_valid':True})
    manifest['lesson_count']=len(expanded);manifest['diagram_count']=len(manifest['items'])
    (SUBJECT/'diagrams-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (SUBJECT/'editorial-layout-check.json').write_text(json.dumps({'canvas':[W,H],'checks':bounds,'errors':errors},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'lessons':len(expanded),'diagrams':len(manifest['items']),'errors':errors},ensure_ascii=False))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
