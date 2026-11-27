#!/usr/bin/env python3
"""Render exact, editable lecture diagrams from reviewed structured content.

Python 3 + Pillow and Inkscape; no network requests. The layout follows the
user-selected 07-notion-editorial reference. Never truncates instructional text.
"""
from __future__ import annotations
import argparse, concurrent.futures, copy, hashlib, html, json, math, re, subprocess
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1600, 1120
BG, INK, MUTED, RULE = '#FFFEFC', '#25241F', '#77756E', '#DFDDD6'
FONT_DIR = Path('/usr/share/fonts/opentype/noto')
FONT_FAMILY = 'Noto Sans CJK KR,Noto Sans KR,sans-serif'
_fonts = {}

def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONT_DIR / ('NotoSansCJK-Bold.ttc' if bold else 'NotoSansCJK-Regular.ttc')), size, index=1)
    return _fonts[key]

def width(s, size, bold=False):
    return font(size, bold).getlength(s)

def wrap(s, max_width, size, bold=False):
    """Wrap at spaces only. Explicit newlines are meaningful; never split words."""
    out = []
    for paragraph in str(s).split('\n'):
        words = paragraph.split()
        if not words:
            out.append('')
            continue
        current = ''
        for word in words:
            if width(word, size, bold) > max_width + .5:
                raise ValueError(f'Unbreakable word exceeds column: {word!r} ({max_width}px)')
            candidate = f'{current} {word}' if current else word
            if current and width(candidate, size, bold) > max_width:
                out.append(current)
                current = word
            else:
                current = candidate
        if current:
            out.append(current)
    return out

def escaped(s):
    return html.escape(str(s), quote=True)

class Canvas:
    def __init__(self, title, desc):
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc" lang="ko">', f'<title id="title">{escaped(title)}</title><desc id="desc">{escaped(desc)}</desc>', f'<rect width="{W}" height="{H}" fill="{BG}"/>']
        self.boxes = []

    def text(self, s, x, y, size, bold=False, color=INK, anchor='start', role='body'):
        tw = width(s, size, bold)
        left = x if anchor == 'start' else x-tw if anchor == 'end' else x-tw/2
        ascent, descent = font(size, bold).getmetrics()
        # PIL baseline bounding boxes track the actual Korean glyph extent.
        bbox = font(size, bold).getbbox(s, anchor='ls')
        self.boxes.append({'text':s, 'x':round(left+bbox[0],2), 'y':round(y+bbox[1],2), 'width':round(bbox[2]-bbox[0],2), 'height':round(bbox[3]-bbox[1],2), 'fontSize':size, 'role':role})
        self.parts.append(f'<text x="{x:g}" y="{y:g}" font-family="{FONT_FAMILY}" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" text-anchor="{anchor}">{escaped(s)}</text>')

    def path(self, d, stroke=INK, sw=2.5, fill='none'):
        self.parts.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')

    def line(self, x1,y1,x2,y2, color=RULE, sw=2):
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>')

    def finish(self):
        self.parts.append('</svg>')
        return '\n'.join(self.parts)+'\n'

def column_specs(layout):
    if layout == 'equal':
        return [(80, 144, 634), (856, 860, 660)], 808
    return [(80, 144, 810), (1030, 1034, 486)], 990

def item_specs(col, maxwidth, size, right=False):
    specs=[]
    for item in col['items']:
        bold = bool(item.get('bold', False)) or right
        lines=wrap(item['text'],maxwidth,size,bold)
        labels=wrap(item.get('label',''),maxwidth,23,False)
        total=len(labels)*30+12+len(lines)*(size*1.42)
        specs.append({'item':item,'lines':lines,'labels':labels,'bold':bold,'height':total})
    return specs

def fits(slide, size=35):
    specs,_=column_specs(slide.get('layout','equal'))
    bottom=973 if slide.get('note') else 1002
    avail=bottom-475
    heights=[]
    for i,name in enumerate(['left','right']):
        its=item_specs(slide[name], specs[i][2],size,i==1)
        heights.append(sum(x['height'] for x in its)+max(0,len(its)-1)*22)
    return max(heights)<=avail

def paginate(slide):
    # Content should be reviewed for the reference's two-column density.
    # A second page is preferable to unreadably small type or deleted facts.
    original_layout=slide.get('layout','equal')
    for size in (36,35,34,33,32):
        for layout in [original_layout]+(['equal'] if original_layout=='split' else []):
            slide['layout']=layout
            try:
                if fits(slide,size):
                    slide['_bodySize']=size
                    return [slide]
            except ValueError:
                continue
    pages = max(2, math.ceil(max(len(slide['left']['items']),len(slide['right']['items']))/2))
    result=[]
    for i in range(pages):
        p=copy.deepcopy(slide)
        for name in ['left','right']:
            items=slide[name]['items']
            n=math.ceil(len(items)/pages)
            part=items[i*n:(i+1)*n]
            # Keep a short context column when all its content fits on one page.
            p[name]['items']=part or items
        p['title']=f"{slide['title']} · {i+1}/{pages}"
        p['continuation']={'page':i+1,'total':pages}
        for size in (36,35,34,33,32):
            if fits(p,size):
                p['_bodySize']=size
                break
        else:
            raise ValueError(f"Content requires manual split: {slide['lessonId']} {slide['title']}")
        result.append(p)
    return result

def render_slide(slide, diagram_id):
    c=Canvas(slide['title'], f"{slide['lessonId']} · {slide['sourceArticle']}. "+slide['subtitle'])
    group='조직·편성·운영' if slide['articleKey'].startswith('1-') else '교육훈련'
    c.text(f"훈령  /  {slide['lessonId']}",80,74,25,True,role='eyebrow')
    c.text(group,1520,74,23,color=MUTED,anchor='end',role='eyebrow')
    ts=64
    while width(slide['title'],ts,True)>1230 and ts>46:
        ts-=1
    if width(slide['title'],ts,True)>1230:
        raise ValueError('Title too wide '+slide['title'])
    c.text(slide['title'],80,181,ts,True,role='title')
    subtitle=wrap(slide['subtitle'],1220,28)
    if len(subtitle)>2:
        raise ValueError('Subtitle requires editing '+slide['title'])
    for i,line in enumerate(subtitle):
        c.text(line,84,233+i*35,28,color=MUTED,role='subtitle')
    # Reuse the simple editorial document motif from the selected reference.
    c.path('M1364 142 L1458 130 L1484 211 L1380 229 Z',sw=3,fill='#F1EFEA')
    c.path('M1337 153 L1438 151 L1442 235 L1334 235 Z',sw=3,fill=BG)
    c.path('M1356 175 L1416 174 M1355 191 L1416 190 M1354 207 L1392 207',sw=3)
    c.line(80,284,1520,284)
    cols, divider=column_specs(slide.get('layout','equal'))
    bottom=973 if slide.get('note') else 1002
    c.line(divider,336,divider,bottom)
    for i,name in enumerate(['left','right']):
        col=slide[name]
        hx,tx,mw=cols[i]
        size=44 if i==0 else 42
        while width(col['title'],size,True)>mw and size>34: size-=1
        c.text(col['title'],hx,372,size,True,role='section-title')
        tw=width(col['title'],size,True)
        if i==0:
            end=hx+tw+15
            c.path(f'M{hx+1} 385 C{hx+tw*.42:g} 391 {hx+tw*.76:g} 381 {end:g} 386',sw=2.7)
        else:
            l=hx-18; r=min(hx+tw+26,1534); mid=(l+r)/2
            c.path(f'M{l+6:g} 341 C{l+28:g} 311 {r-60:g} 307 {r-6:g} 331 C{r+15:g} 346 {r+1:g} 381 {r-28:g} 393 C{mid:g} 413 {l+28:g} 400 {l+5:g} 375 C{l-8:g} 363 {l-4:g} 349 {l+6:g} 341',sw=2.2)
        sub=wrap(col.get('subtitle',''),mw+(tx-hx),27)
        if len(sub)>2: raise ValueError('Section subtitle too long '+slide['title'])
        for j,line in enumerate(sub): c.text(line,hx+4,426+j*32,27,color=MUTED,role='section-subtitle')
        first_y=487 if len(sub)<2 else 509
        size=slide.get('_bodySize',35)
        its=item_specs(col,mw,size,i==1)
        available=bottom-first_y
        total=sum(it['height'] for it in its)
        gap=max(22,min(110,(available-total)/max(1,len(its)-1)))
        if total+max(0,len(its)-1)*gap>available+16:
            raise ValueError(f'Column exceeds space: {diagram_id} {name}: {total} / {available}')
        y=first_y
        for it in its:
            for line in it['labels']:
                c.text(line,tx,y,23,color=MUTED,role='label'); y+=30
            y+=12
            for line in it['lines']:
                c.text(line,tx,y,size,it['bold'],role='body'); y+=size*1.42
            y+=gap
        if i==0:
            end=min(bottom+3,y-gap-8)
            c.path(f'M116 {first_y-28:g} C96 {first_y-28:g} 92 {first_y-21:g} 92 {first_y-2:g} L92 {end-32:g} C92 {end-9:g} 102 {end:g} 117 {end:g}',sw=2.7)
    if slide.get('note'):
        n=wrap(slide['note'],1440,23)
        if len(n)>2: raise ValueError('Note too long '+slide['title'])
        for i,line in enumerate(n): c.text(line,80,1000+i*29,23,color=MUTED,role='note')
    c.line(80,1051,1520,1051)
    footer=f"{slide['sourceArticle']} · {diagram_id}"
    c.text(footer,80,1091,22,color=MUTED,role='footer')
    c.text('무한회독',1520,1091,23,True,anchor='end',role='footer')
    return c.finish(), c.boxes

def rasterize(job):
    svg,png,webp=job
    result=subprocess.run(['inkscape',str(svg),'--export-type=png',f'--export-filename={png}',f'--export-width={W}'],capture_output=True,text=True)
    if result.returncode: raise RuntimeError(result.stderr)
    with Image.open(png) as im:
        # Lossless WebP preserves small Korean strokes and the paper-colored field.
        rgb=im.convert('RGB')
        rgb.save(webp,'WEBP',lossless=True,quality=80,method=6)
    return {'pngBytes':png.stat().st_size,'webpBytes':webp.stat().st_size}

def check_boxes(boxes,diagram_id):
    errors=[]
    for b in boxes:
        if b['x']<60 or b['x']+b['width']>1544 or b['y']<30 or b['y']+b['height']>1108:
            errors.append({'id':diagram_id,'kind':'page-boundary','box':b})
        if b['role']=='body' and b['y']+b['height']>1025:
            errors.append({'id':diagram_id,'kind':'body-footer-overlap','box':b})
    # Compare actual glyph rectangles; do not treat empty whitespace as overlap.
    for i,a in enumerate(boxes):
        for b in boxes[i+1:]:
            if min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])>1 and min(a['y']+a['height'],b['y']+b['height'])-max(a['y'],b['y'])>1:
                errors.append({'id':diagram_id,'kind':'text-overlap','a':a['text'],'b':b['text']})
    return errors

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('inputs',nargs='+')
    parser.add_argument('--out',type=Path,default=ROOT/'defense-directives')
    parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--svg-only',action='store_true')
    args=parser.parse_args()
    data=[]
    for p in args.inputs:
        raw=json.loads(Path(p).read_text())
        data.extend(raw if isinstance(raw,list) else raw['diagrams'])
    data.sort(key=lambda s:s['lessonId'])
    slides=[]
    for d in data: slides.extend(paginate(copy.deepcopy(d)))
    count=Counter(); records=[]; jobs=[]; errors=[]
    for slide in slides:
        lid=slide['lessonId']; count[lid]+=1
        did=f'{lid}-D{count[lid]:02d}'
        folder=args.out/f"lesson-{lid.split('-')[1]}"/'diagrams'
        folder.mkdir(parents=True,exist_ok=True)
        stem=f'{did}-editorial-v1'
        svg=folder/(stem+'.svg');png=folder/(stem+'.png');webp=folder/(stem+'.webp')
        text,boxes=render_slide(slide,did)
        svg.write_text(text)
        errors.extend(check_boxes(boxes,did))
        if not args.svg_only: jobs.append((svg,png,webp))
        record={k:v for k,v in slide.items() if not k.startswith('_') and k!='evidence'}
        record.update({'id':did,'width':W,'height':H,'bodyFontSize':slide['_bodySize'],'files':{e:str(folder.relative_to(args.out)/(stem+'.'+e)) for e in ['svg','png','webp']},'textBoxes':boxes})
        records.append(record)
    report={'diagrams':len(records),'lessons':len(count),'lessonCounts':dict(count),'errors':errors,'minimumBodyFontSize':min(s['_bodySize'] for s in slides)}
    report_path=args.out/'diagrams'/'layout-qa.json';report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if errors:
        print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(1)
    if jobs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for rec,stats in zip(records,pool.map(rasterize,jobs)):rec.update(stats)
    (args.out/'diagrams'/'rendered-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'diagrams':len(records),'lessons':len(count),'errors':len(errors),'minBodyFont':report['minimumBodyFontSize']},ensure_ascii=False))

if __name__=='__main__':main()
