#!/usr/bin/env python3
"""Build the approved monochrome editorial lecture diagrams from content.json.

Requires Pillow and Noto Sans CJK KR. Run from anywhere; all paths are relative
to this script's repository. No remote resources or private lecture scripts.
"""
from pathlib import Path
from html import escape
from PIL import ImageFont
from functools import lru_cache
import json, math, re, hashlib

ROOT = Path(__file__).resolve().parents[2]
SUBJECT = ROOT / 'integrated-defense'
DATA = SUBJECT / 'notion-v1' / 'content.json'
W, H = 1600, 1120
INK, MUTED, RULE, PAPER = '#25241F', '#77756E', '#DFDDD6', '#FFFEFC'
REG = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
BOLD = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

@lru_cache(maxsize=128)
def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else REG, int(size), index=1)

def width(s, size, bold=False):
    return font(size, bold).getlength(str(s))

def wrap(s, maxw, size, bold=False):
    result = []
    for paragraph in str(s).split('\n'):
        line = ''
        for word in paragraph.split():
            candidate = (line + ' ' + word).strip()
            if width(candidate, size, bold) <= maxw:
                line = candidate
            else:
                if line: result.append(line)
                line = word
                if width(line, size, bold) > maxw:
                    part = ''
                    for ch in line:
                        if width(part + ch, size, bold) > maxw:
                            result.append(part); part = ch
                        else: part += ch
                    line = part
        if line: result.append(line)
    return result

class Canvas:
    def __init__(self, ident, title, description):
        self.ident = ident; self.parts = []; self.boxes = []; self.errors = []
        self.parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc" lang="ko">')
        self.parts.append(f'<title id="title">{escape(ident + " · " + title)}</title><desc id="desc">{escape(description)}</desc>')
        self.rect(0, 0, W, H, PAPER)
    def rect(self, x, y, w, h, fill='none', stroke=None, sw=2, r=0):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"'+(f' stroke="{stroke}" stroke-width="{sw}"' if stroke else '')+'/>')
    def path(self, d, stroke=INK, sw=2.3, fill='none'):
        self.parts.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')
    def line(self, x1, y1, x2, y2, color=RULE, sw=2):
        self.path(f'M{x1} {y1} L{x2} {y2}', color, sw)
    def text(self, s, x, y, size=34, bold=False, fill=INK, anchor='start', maxw=None):
        s = str(s); tw = width(s, size, bold)
        if maxw is not None and tw > maxw + 1:
            self.errors.append(f'local width overflow: {s} ({tw:.1f}>{maxw})')
        left = x if anchor == 'start' else x - tw if anchor == 'end' else x - tw/2
        bbox = font(size, bold).getbbox(s, anchor='ls')
        box = {'text':s, 'x':round(left,2), 'y':round(y+bbox[1],2), 'w':round(tw,2), 'h':bbox[3]-bbox[1], 'size':size}
        if left < 42 or left+tw > W-42 or box['y'] < 18 or box['y']+box['h'] > H-12:
            self.errors.append(f'off canvas: {s}')
        self.boxes.append(box)
        self.parts.append(f'<text x="{x}" y="{y}" font-family="Noto Sans CJK KR, Noto Sans KR, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')
        return tw
    def para(self, s, x, y, maxw, size=32, bold=False, fill=INK, lh=None):
        lh = lh or int(size*1.45)
        lines = wrap(s, maxw, size, bold)
        for i, line in enumerate(lines): self.text(line, x, y+i*lh, size, bold, fill, maxw=maxw)
        return len(lines)*lh
    def bracket(self, x, top, bottom):
        self.path(f'M{x+20} {top} Q{x} {top} {x} {top+22} L{x} {bottom-22} Q{x} {bottom} {x+20} {bottom}', sw=2.6)
    def underline(self, x, y, w):
        self.path(f'M{x} {y} C{x+w*.3} {y+5} {x+w*.65} {y-3} {x+w} {y+1}', sw=2.8)
    def arrow(self, x1, y1, x2, y2):
        self.line(x1,y1,x2,y2,INK,2.1)
        a = math.atan2(y2-y1,x2-x1); l=10
        self.path(f'M{x2-l*math.cos(a-.48):.1f} {y2-l*math.sin(a-.48):.1f} L{x2} {y2} L{x2-l*math.cos(a+.48):.1f} {y2-l*math.sin(a+.48):.1f}',sw=2.1)
    def document(self):
        self.path('M1390 127 L1468 116 L1491 184 L1405 201 Z',fill='#F1EFEA')
        self.path('M1366 136 L1450 134 L1453 206 L1364 206 Z',fill=PAPER)
        self.path('M1382 155 L1431 154 M1381 171 L1431 170 M1380 187 L1412 187',sw=2.5)
    def save(self, path):
        overlaps=[]
        for i,a in enumerate(self.boxes):
            for b in self.boxes[i+1:]:
                iw=min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x'])
                ih=min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y'])
                if iw>3 and ih>3: overlaps.append([a['text'],b['text'],round(iw,1),round(ih,1)])
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('\n'.join(self.parts+['</svg>'])+'\n')
        return {'id':self.ident,'path':str(path.relative_to(ROOT)),'errors':self.errors,'overlaps':overlaps,'texts':self.boxes}

def item_height(item, w, fs):
    labels=wrap(item.get('label',''),w,fs,True)
    details=wrap(item.get('detail',''),w,fs-5)
    return len(labels)*int(fs*1.35) + (8 if details and labels else 0) + len(details)*int((fs-5)*1.48)

def draw_item(c, item, x, top, w, fs):
    y=top
    if item.get('label'):
        y += c.para(item['label'],x,y+fs,w,fs,True,lh=int(fs*1.35))
    if item.get('detail'):
        y += 8 if item.get('label') else 0
        y += c.para(item['detail'],x,y+fs-5,w,fs-5,False,MUTED,lh=int((fs-5)*1.48))
    return y

def fitted_list(items, w, room, maxfs=38, minfs=28):
    for fs in range(maxfs,minfs-1,-1):
        needed=sum(item_height(item,w,fs) for item in items)+max(0,len(items)-1)*24
        if needed<=room:return fs,needed
    return minfs,needed

def draw_columns(c, sections, top, bottom, numbered=False):
    n=len(sections); gap=70 if n<3 else 46
    weights=getattr(c,'column_weights',None) or [1]*n
    if len(weights)!=n:weights=[1]*n
    widths=[(1440-gap*(n-1))*v/sum(weights) for v in weights]
    for i,sec in enumerate(sections):
        cw=widths[i]; x=80+sum(widths[:i])+i*gap
        if i:c.line(x-gap/2,top+3,x-gap/2,bottom-12)
        title=sec.get('title','')
        ts=42 if n<3 else 38
        while width(title,ts,True)>cw-10 and ts>28:ts-=1
        ht=c.para(title,x,top+ts,cw-8,ts,True,lh=int(ts*1.36))
        if title:
            if sec.get('emphasis')=='circle' or '시·도만' in title:
                tw=min(width(title,ts,True),cw-20)
                c.path(f'M{x-24} {top+24} C{x-24} {top-20} {x+tw+28} {top-22} {x+tw+26} {top+24} C{x+tw+26} {top+70} {x-24} {top+70} {x-24} {top+24}',sw=2.2)
            else:c.underline(x,top+ht+14,min(width(title,ts,True),cw-10))
        start=top+ht+43
        items=sec.get('items',[])
        ix=x+32 if len(items)>1 else x
        iw=cw-32 if len(items)>1 else cw
        fs,needed=fitted_list(items,iw,bottom-start,38 if n<3 else 34)
        if needed>bottom-start:c.errors.append(f'column overflow {title}: {needed}>{bottom-start}')
        if len(items)>1:c.bracket(x,start+4,bottom-10)
        gap_item=max(24,min(50,((bottom-start)-sum(item_height(t,iw,fs) for t in items))/max(1,len(items)-1)))
        y=start
        for j,item in enumerate(items):
            end=draw_item(c,item,ix,y,iw,fs)
            y=end+gap_item

def draw_checklist(c, sections, top, bottom):
    if len(sections)>1:return draw_columns(c,sections,top,bottom)
    sec=sections[0]; items=sec.get('items',[])
    if len(items)<=4:return draw_columns(c,sections,top,bottom)
    title=sec.get('title','')
    if title:
        c.text(title,80,top+42,42,True,maxw=1400);c.underline(80,top+57,min(width(title,42,True),1280))
    start=top+88 if title else top
    rows=math.ceil(len(items)/2); rh=(bottom-start)/rows
    for i,item in enumerate(items):
        col=i//rows; row=i%rows; x=80+col*744; y=start+row*rh
        c.text(f'{i+1:02}',x,y+33,23,False,MUTED)
        fs=35
        while item_height(item,615,fs)>rh-22 and fs>27:fs-=1
        draw_item(c,item,x+60,y-1,615,fs)
        if row<rows-1:c.line(x+60,y+rh-12,x+670,y+rh-12)
    c.line(800, start,800,bottom-12)

def draw_flow(c, sections, top, bottom):
    sections=[{**s,'title':re.sub(r'^[①②③④⑤]\s*','',s.get('title',''))} for s in sections]
    n=len(sections)
    if n>5:
        c.errors.append('Flow has more than five stages; split the content.');return
    titlew=340; bodyw=875; left=140; right=600
    fs=34
    def rowsizes(fs):
        sizes=[]
        for sec in sections:
            th=len(wrap(sec.get('title',''),titlew,40,True))*55+12
            ih=sum(item_height(item,bodyw,fs) for item in sec.get('items',[]))+max(0,len(sec.get('items',[]))-1)*14
            sizes.append(max(th,ih)+30)
        return sizes
    sizes=rowsizes(fs)
    if sum(sizes)>bottom-top and n==3:
        cw=(1440-92)/3
        for i in range(3):
            x=80+i*(cw+46)
            c.text(f'{i+1:02}',x,top+23,22,False,MUTED)
            if i<2:c.arrow(x+62,top+14,x+cw+20,top+14)
        draw_columns(c,sections,top+45,bottom)
        return
    while sum(sizes)>bottom-top and fs>27:
        fs-=1;sizes=rowsizes(fs)
    if sum(sizes)>bottom-top:c.errors.append(f'Flow height overflow {sum(sizes)}>{bottom-top}')
    extra=max(0,(bottom-top-sum(sizes))/n)
    y=top
    for i,(sec,h) in enumerate(zip(sections,sizes)):
        h+=extra
        c.text(f'{i+1:02}',80,y+40,25,False,MUTED)
        c.para(sec.get('title',''),left,y+42,titlew,40,True,lh=55)
        yy=y
        for item in sec.get('items',[]):yy=draw_item(c,item,right,yy,bodyw,fs)+14
        if i<n-1:
            c.arrow(102,y+66,102,y+h-8)
            c.line(left,y+h-14,1520,y+h-14)
        y+=h

def draw_roles(c, sections, top, bottom):
    if len(sections)==1:return draw_checklist(c,sections,top,bottom)
    if len(sections)==2:return draw_columns(c,sections,top,bottom)
    if len(sections)==3 and sum(len(s.get('items',[])) for s in sections)>5:
        return draw_columns(c,sections,top,bottom)
    n=len(sections); fs=34
    def needed(sec,fs):
        return max(len(wrap(sec.get('title',''),355,38,True))*52,sum(item_height(i,925,fs) for i in sec.get('items',[]))+max(0,len(sec.get('items',[]))-1)*12)+34
    while sum(needed(s,fs) for s in sections)>bottom-top and fs>27:fs-=1
    total=sum(needed(s,fs) for s in sections)
    if total>bottom-top:c.errors.append(f'Roles height overflow {total}>{bottom-top}')
    extra=max(0,(bottom-top-total)/n);y=top
    for i,sec in enumerate(sections):
        h=needed(sec,fs)+extra
        c.para(sec.get('title',''),80,y+40,355,38,True,lh=52)
        c.bracket(487,y+2,y+h-24)
        yy=y-1
        for item in sec.get('items',[]):yy=draw_item(c,item,550,yy,925,fs)+12
        if i<n-1:c.line(80,y+h-10,1520,y+h-10)
        y+=h

def draw_matrix(c, sections, top, bottom):
    labels=[[i.get('label','') for i in sec.get('items',[])] for sec in sections]
    if len(sections)<2 or len(sections)>3 or not labels or any(v!=labels[0] for v in labels[1:]):
        return draw_columns(c,sections,top,bottom)
    keys=labels[0]; n=len(sections); keyw=260; gap=30; cw=(1440-keyw)/n
    for i,sec in enumerate(sections):
        x=80+keyw+i*cw+24
        ts=36
        while width(sec['title'],ts,True)>cw-40 and ts>28:ts-=1
        c.para(sec['title'],x,top+ts,cw-42,ts,True,lh=45)
    header=top+87;c.line(80,header,1520,header,INK,2)
    rh=(bottom-header)/max(len(keys),1)
    for row,key in enumerate(keys):
        y=header+row*rh
        c.para(key,80,y+49,keyw-35,31,True,lh=44)
        for col,sec in enumerate(sections):
            x=80+keyw+col*cw+24; detail=sec['items'][row].get('detail','')
            fs=32
            while len(wrap(detail,cw-46,fs))*int(fs*1.45)>rh-24 and fs>26:fs-=1
            c.para(detail,x,y+fs+16,cw-46,fs,False,INK)
        c.line(80,y+rh,1520,y+rh)

def build(lesson,d):
    lid=f'TB-{lesson["lesson"]:03d}'
    ident=f'{lid}-{d["id"]}'
    desc=' '.join([d.get('subtitle','')]+[sec.get('title','')+'：'+'；'.join(i.get('label','')+' '+i.get('detail','') for i in sec.get('items',[])) for sec in d.get('sections',[])]+d.get('notes',[]))
    c=Canvas(ident,d['title'],desc)
    c.column_weights=d.get('column_weights')
    c.text('무한회독  /  통합방위법',80,73,25,True)
    c.text(f'{lesson["lesson"]:02d}강   ·   {lesson["article"]}   /   {d["id"]}',1520,73,24,False,MUTED,'end')
    ts=66
    while width(d['title'],ts,True)>1220 and ts>46:ts-=1
    c.para(d['title'],80,177,1220,ts,True,lh=75)
    c.para(d.get('subtitle',''),84,235,1230,28,False,MUTED,lh=39)
    c.document();c.line(80,274,1520,274)
    notes='  '.join(d.get('display_notes',d.get('notes',[])))
    note_lines=wrap(notes,1428,23)
    takeaway_lines=wrap(d.get('takeaway',''),1380,31,True)
    footer_top=1046
    note_top=footer_top-12-len(note_lines)*31
    takeaway_top=note_top-21-len(takeaway_lines)*43
    content_bottom=min(943,takeaway_top-30)
    layout=d.get('layout','compare')
    funcs={'flow':draw_flow,'compare':draw_columns,'matrix':draw_matrix,'roles':draw_roles,'checklist':draw_checklist}
    funcs.get(layout,draw_columns)(c,d['sections'],313,content_bottom)
    if takeaway_lines:
        c.line(80,takeaway_top-14,1520,takeaway_top-14)
        for i,line in enumerate(takeaway_lines):c.text(line,84,takeaway_top+31+i*43,31,True)
    for i,line in enumerate(note_lines):c.text(line,84,note_top+23+i*31,23,False,MUTED)
    c.line(80,footer_top,1520,footer_top)
    basis=' · '.join(dict.fromkeys(s.get('basis','') for s in d.get('sources',[])))
    while width(basis,22)>1180 and len(basis)>20:
        basis=basis[:basis.rfind(' · ')] if ' · ' in basis else basis[:80]+'…'
        if width(basis,22)<=1180:break
        if ' · ' not in basis:break
    if width(basis,22)>1180:basis='통합방위법 '+lesson['article']+' 및 관련 시행령 · 상세 근거는 README'
    c.text(basis,80,1086,22,False,MUTED)
    c.text('2026.11.27 확인',1520,1086,21,False,MUTED,'end')
    rel=Path(f'lesson-{lesson["lesson"]:03d}')/'diagrams'/'notion-v1'/f'{ident}-{d["slug"]}'
    qa=c.save(SUBJECT/(str(rel)+'.svg'))
    return {'id':ident,'lesson':lesson['lesson'],'lecture_id':lid,'article':lesson['article'],'title':d['title'],'layout':layout,'base':str(rel),'alt':desc,'sources':d.get('sources',[]),'notes':d.get('notes',[])},qa

def main():
    data=json.loads(DATA.read_text()); manifest=[]; qa=[]
    for lesson in data['lessons']:
        for d in lesson['diagrams']:
            record,check=build(lesson,d);manifest.append(record);qa.append(check)
    (SUBJECT/'notion-v1'/'render-records.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    qa_path=ROOT.parent/'production'/'build'/'layout-qa.json';qa_path.parent.mkdir(parents=True,exist_ok=True)
    qa_path.write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
    errors=[{'id':q['id'],'errors':q['errors'],'overlaps':q['overlaps']} for q in qa if q['errors'] or q['overlaps']]
    print(json.dumps({'diagrams':len(qa),'errors':errors},ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
