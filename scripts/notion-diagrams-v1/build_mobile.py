#!/usr/bin/env python3
"""Generate one-column mobile pages from approved structured content."""
from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont
from functools import lru_cache
import argparse, hashlib, json, re
ROOT=Path(__file__).resolve().parents[2]
SUB=ROOT/'integrated-defense'
W,H=1080,1800
PAPER,INK,MUTED,RULE='#FFFEFC','#25241F','#77756E','#DFDDD6'
REG='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
@lru_cache(None)
def font(s,b=False): return ImageFont.truetype(BOLD if b else REG,s,index=1)
def wrap(s,size,b=False,width=920):
    f=font(size,b); result=[]
    for paragraph in str(s).splitlines():
        line=''
        for word in paragraph.split():
            pieces=re.split(r'(?<=[·ㆍ/、])',word) if f.getlength(word)>width else [word]
            for i,p in enumerate(pieces):
                if not p: continue
                candidate=line+(' ' if line and i==0 else '')+p
                if f.getlength(candidate)>width:
                    if line:result.append(line)
                    line=p
                    if f.getlength(p)>width:raise ValueError(f'Unbreakable text: {p}')
                else:line=candidate
        if line: result.append(line)
    return result

def block(s,size=42,b=False,kind='body',indent=0):
    return [(line,size,b,kind,indent) for line in wrap(s,size,b,920-indent)]
def height(lines):return sum(round(s*1.45) for _,s,_,_,_ in lines)+20

def paginate(lesson,d):
    title=block(d['title'],56,True); subtitle=block(d.get('subtitle',''),42)
    start=106+height(title)+height(subtitle)+26
    end=H-170
    capacity=end-start
    if capacity<360:raise ValueError('Header exceeds available area')
    pages=[];cur=[];used=0
    def add(lines):
        nonlocal cur,used
        if not lines:return
        h=height(lines)
        if h>capacity:raise ValueError('Block too tall: '+str(lines[0]))
        if used+h>capacity and cur:pages.append(cur);cur=[];used=0
        cur.append(lines);used+=h
    for n,sec in enumerate(d['sections'],1):
        name=sec['title']; heading=block(name,48,True,'heading')
        if d['layout']=='flow' and not re.match(r'^[①②③④⑤⑥⑦⑧⑨0-9]',name):heading=block(f'{n:02d}  {name}',48,True,'heading')
        first=True
        for item in sec['items']:
            lines=block(item['label'],44,True,'label',24)+block(item['detail'],42,False,'body',24)
            if first or used+height(lines)>capacity:
                h=height(heading)+height(lines)
                if h>capacity:raise ValueError('Section and item exceed page')
                if cur and used+h>capacity:pages.append(cur);cur=[];used=0
                add(heading if first else block(name+' (계속)',48,True,'heading'));first=False
            add(lines)
    if d.get('takeaway'):add(block('기억할 문장',48,True,'heading')+block(d['takeaway'],42,True))
    for i,note in enumerate(d.get('notes',[])):
        lines=block(note.replace('오른쪽 3개 사항은', '시행령의 3개 사항은'),42)
        if i==0 or used+height(lines)>capacity:
            h=block('조건·범위',48,True,'heading')
            if cur and used+height(h)+height(lines)>capacity:pages.append(cur);cur=[];used=0
            add(h)
        add(lines)
    for i,source in enumerate(d.get('sources',[])):
        lines=block(source['basis'],42)
        if i==0 or used+height(lines)>capacity:
            h=block('법령 근거',48,True,'heading')
            if cur and used+height(h)+height(lines)>capacity:pages.append(cur);cur=[];used=0
            add(h)
        add(lines)
    if cur:pages.append(cur)
    # Avoid a final page containing only legal references. Preserve all content,
    # font sizes and ordering; move a meaningful suffix of the previous page.
    if len(pages)>1 and pages[-1][0][0][0]=='법령 근거':
        prev,last=pages[-2],pages[-1]
        total=lambda pp:sum(height(b) for b in pp)
        options=[]
        for cut in range(1,len(prev)):
            left,tail=prev[:cut],prev[cut:]
            if left[-1][-1][3]=='heading':continue
            # Preserve context when moving a list item or note across a page.
            prefix=[]
            if tail[0][0][3]!='heading':
                headings=[b for b in left if b[0][3]=='heading']
                if not headings:continue
                name=' '.join(t[0] for t in headings[-1] if t[3]=='heading')
                if not name:continue
                if not name.endswith('(계속)'):name+=' (계속)'
                prefix=[block(name,48,True,'heading')]
            right=prefix+tail+last
            if total(right)<=capacity and total(left)<=capacity:
                options.append((abs(total(left)-total(right)),cut,left,right))
        if not options:raise ValueError('Cannot rebalance reference-only page: '+d['id'])
        _,_,left,right=min(options,key=lambda x:(x[0],x[1]))
        pages[-2:]=[left,right]
    return title,subtitle,pages,start

def build_page(lesson,d,header,pages,page,start,base):
    im=Image.new('RGB',(W,H),PAPER);draw=ImageDraw.Draw(im)
    ident=f"{lesson['lecture_id']}-{d['id']}"
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" lang="ko">',f'<title>{escape(ident+" · "+d["title"])}</title>',f'<rect width="{W}" height="{H}" fill="{PAPER}"/>']
    boxes=[]
    def line(x,y,x2,y2,color=RULE,w=3):
        draw.line((x,y,x2,y2),fill=color,width=w);svg.append(f'<path d="M{x} {y}L{x2} {y2}" stroke="{color}" stroke-width="{w}" fill="none" stroke-linecap="round"/>')
    def txt(s,x,y,sz,b=False,col=INK):
        f=font(sz,b);box=draw.textbbox((x,y),s,font=f,anchor='ls')
        if box[0]<35 or box[2]>W-35 or box[1]<10 or box[3]>H-10:raise ValueError(f'Out of bounds {ident}: {s}: {box}')
        for old in boxes:
            if min(box[2],old[2])-max(box[0],old[0])>2 and min(box[3],old[3])-max(box[1],old[1])>2:raise ValueError(f'Overlap {ident}: {s}')
        boxes.append(box);draw.text((x,y),s,font=f,fill=col,anchor='ls');svg.append(f'<text x="{x}" y="{y}" font-family="Noto Sans CJK KR, sans-serif" font-weight="{700 if b else 400}" font-size="{sz}" fill="{col}">{escape(s)}</text>')
    def lines(ls,y):
        for s,sz,b,kind,indent in ls:
            x=80+indent;txt(s,x,y+sz,sz,b)
            if kind=='heading':line(x,y+sz+10,min(x+font(sz,b).getlength(s),1000),y+sz+10,INK,3)
            y+=round(sz*1.45)
        return y+20
    txt(f'무한회독 / 통합방위법 · {lesson["lesson"]:02d}강',80,65,35,True)
    y=106;y=lines(header[0],y);y=lines(header[1],y);line(80,y,1000,y)
    y=start
    for b in pages[page-1]:
        if b[0][3]=='label':line(80,y+9,80,y+height(b)-22,INK,3)
        y=lines(b,y)
    if y>H-170:raise ValueError(f'Content overflow {ident} {page}')
    line(80,H-145,1000,H-145)
    txt(f'{lesson["article"]} · {ident} · {page}/{len(pages)}',80,H-91,35,True)
    txt('근거: 마지막 페이지 및 모바일 목록',80,H-43,34,False,MUTED)
    base.parent.mkdir(parents=True,exist_ok=True)
    base.with_suffix('.svg').write_text('\n'.join(svg+['</svg>'])+'\n')
    im.save(base.with_suffix('.png'),optimize=True);im.save(base.with_suffix('.webp'),quality=90,method=6)
    files={}
    for ext in ('svg','png','webp'):
        p=base.with_suffix('.'+ext);raw=p.read_bytes();files[ext]={'path':str(p.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'width':W,'height':H}
    return {'source_id':ident,'lesson':lesson['lesson'],'page':page,'page_count':len(pages),'files':files,'sources':d['sources'],'qa':{'text_bounds':True,'no_text_overlap':True,'min_body_px_at_390':42*390/1080}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lessons',nargs='*',type=int);args=ap.parse_args()
    data=json.loads((SUB/'notion-v1/content.json').read_text());target=set(args.lessons or [l['lesson'] for l in data['lessons']]);mp=SUB/'notion-v1/mobile-manifest.json'
    old=json.loads(mp.read_text()) if mp.exists() else {'items':[]};records=[r for r in old['items'] if r['lesson'] not in target]
    for l in data['lessons']:
        if l['lesson'] not in target:continue
        for d in l['diagrams']:
            t,s,pages,start=paginate(l,d);ident=f"{l['lecture_id']}-{d['id']}"
            for i in range(1,len(pages)+1):
                base=SUB/f'lesson-{l["lesson"]:03d}'/'diagrams/notion-v1/mobile'/f'{ident}-M{i:02d}'
                records.append(build_page(l,d,(t,s),pages,i,start,base))
    records.sort(key=lambda r:(r['source_id'],r['page']));mp.write_text(json.dumps({'schema_version':1,'style':'07-notion-editorial','width':W,'height':H,'items':records},ensure_ascii=False,indent=2)+'\n')
    # A separate navigable list, preserving the existing desktop catalogue.
    for lesson in sorted({r['lesson'] for r in records}):
        rr=[r for r in records if r['lesson']==lesson]
        out=SUB/f'lesson-{lesson:03d}'/'diagrams/notion-v1/mobile/README.md'
        rows=['# '+str(lesson)+'강 모바일 도식','','| 원본 도식 | 페이지 | PNG | SVG | WebP |','|---|---:|---|---|---|']
        for r in rr:
            link=lambda ext:'['+ext.upper()+']('+Path(r['files'][ext]['path']).name+')'
            rows.append('| '+r['source_id']+' | '+str(r['page'])+'/'+str(r['page_count'])+' | '+link('png')+' | '+link('svg')+' | '+link('webp')+' |')
        out.write_text('\n'.join(rows)+'\n')
    print(json.dumps({'lessons':len({r['lesson'] for r in records}),'source_diagrams':len({r['source_id'] for r in records}),'pages':len(records)},ensure_ascii=False))
if __name__=='__main__':main()
