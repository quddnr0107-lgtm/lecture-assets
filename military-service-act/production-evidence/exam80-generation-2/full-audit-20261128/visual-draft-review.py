#!/usr/bin/env python3
"""Read-only visual audit of the17 active (not historical) unfinished drafts."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from collections import Counter
import json,subprocess,hashlib,xml.etree.ElementTree as ET
from PIL import Image,ImageDraw,ImageFont,ImageChops
from fontTools.ttLib import TTFont
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
BASE=ROOT/'military-service-act/production-evidence/exam80-generation-2/draft-batches/20261128-11'
TMP=ROOT.parent/'audit-tmp/draft-review'
TMP.mkdir(parents=True,exist_ok=True)
load=lambda p:json.loads(p.read_text())
active=[{'id':x['id'],'path':x['path']} for x in load(BASE/'checkpoint-17-MS-094-coverage-drafts.json')['changed_artifacts_and_hashes']]
active +=[{'id':x['id'],'path':x['svg_path']} for x in load(BASE/'checkpoint-13-visual-review.json')['remaining'] if x['id'] in {'MS-065-D03-editorial-v1','MS-065-D05-editorial-v1','MS-109-D09-editorial-v1'}]
active.sort(key=lambda x:x['id'])
NS={'s':'http://www.w3.org/2000/svg'}
FONTS=Path('/usr/share/fonts/opentype/noto')
@lru_cache(None)
def font(size,bold=False):return ImageFont.truetype(str(FONTS/('NotoSansCJK-Bold.ttc' if bold else 'NotoSansCJK-Regular.ttc')),size,index=1)
cmap=TTFont(FONTS/'NotoSansCJK-Regular.ttc',fontNumber=1).getBestCmap()
def audit(item):
    svg=ROOT/item['path'];data=svg.read_bytes();png=TMP/(item['id']+'.png')
    result={'id':item['id'],'path':item['path'],'svg_sha256':hashlib.sha256(data).hexdigest(),'findings':[],'text_boxes':[]}
    tree=ET.fromstring(data)
    if tree.get('width')!='1600' or tree.get('height')!='1120' or tree.get('viewBox')!='0 0 1600 1120':result['findings'].append({'kind':'canvas','attributes':tree.attrib})
    for e in tree.findall('.//s:text',NS):
        text=''.join(e.itertext());size=int(e.get('font-size'));bold=int(e.get('font-weight','400'))>=600;f=font(size,bold);x=float(e.get('x'));y=float(e.get('y'));anchor=e.get('text-anchor','start')
        if anchor=='end':x-=f.getlength(text)
        elif anchor=='middle':x-=f.getlength(text)/2
        x0,y0,x1,y1=f.getbbox(text,anchor='ls');box=[x+x0,y+y0,x+x1,y+y1]
        b={'text':text,'box':box,'font_size':size,'baseline':y,'bold':bold,'fill':e.get('fill')};result['text_boxes'].append(b)
        if box[0]<0 or box[1]<0 or box[2]>1600 or box[3]>1120:result['findings'].append({'kind':'text_overflow','run':b})
        missing=sorted({ch for ch in text if not ch.isspace() and ord(ch) not in cmap})
        if missing:result['findings'].append({'kind':'missing_glyph','text':text,'characters':missing})
    for n,a in enumerate(result['text_boxes']):
        ax0,ay0,ax1,ay1=a['box']
        for b in result['text_boxes'][n+1:]:
            bx0,by0,bx1,by1=b['box'];dx=min(ax1,bx1)-max(ax0,bx0);dy=min(ay1,by1)-max(ay0,by0)
            if dx>1.2 and dy>1.2:result['findings'].append({'kind':'text_overlap_candidate','a':a,'b':b})
    body=[t['font_size'] for t in result['text_boxes'] if 400<t['baseline']<950 and not t['bold'] and t['fill']=='#25241F']
    result['minimum_body_font_px']=min(body) if body else None
    run=subprocess.run(['inkscape',str(svg),'--export-type=png',f'--export-filename={png}','--export-width=1600','--export-height=1120'],capture_output=True,text=True)
    if run.returncode:result['findings'].append({'kind':'render_failed','stderr':run.stderr});return result
    with Image.open(png) as im:result['raster_dimensions']=list(im.size);result['png_sha256']=hashlib.sha256(png.read_bytes()).hexdigest()
    webp=svg.with_suffix('.webp')
    if webp.exists():
        a=Image.open(png).convert('RGB');b=Image.open(webp).convert('RGB');result['existing_draft_webp_pixel_match']=ImageChops.difference(a,b).getbbox() is None
        result['existing_draft_webp_sha256']=hashlib.sha256(webp.read_bytes()).hexdigest()
    return result
with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(audit,active))
for start in range(0,len(rows),9):
    part=rows[start:start+9];cw,ch=533,398;sheet=Image.new('RGB',(1599,1194),'#ebeae4');draw=ImageDraw.Draw(sheet)
    for n,r in enumerate(part):
        x=n%3*cw;y=n//3*ch;draw.text((x+5,y+2),r['id'],font=font(18),fill='#111111')
        with Image.open(TMP/(r['id']+'.png')) as im:sheet.paste(im.convert('RGB').resize((533,373),Image.Resampling.LANCZOS),(x,y+25))
    sheet.save(TMP/f'active-drafts-{start//9+1:02d}.jpg',quality=96)
report={'date_kst':'2026-11-28','status':'visual_inspection_required_after_geometry','scope':'Only17 active unfinished drafts; no promotion and no source semantics judgment','summary':{'active_drafts':len(rows),'text_runs':sum(len(x['text_boxes']) for x in rows),'findings_by_kind':dict(Counter(f['kind'] for x in rows for f in x['findings'])),'draft_raster_pixel_matches':sum(x.get('existing_draft_webp_pixel_match') is True for x in rows),'minimum_body_font_px':min(x['minimum_body_font_px'] for x in rows if x['minimum_body_font_px'])},'pages':rows,'note':'MS-109-D09 is evaluated only for geometry and rendered legibility; its ambiguous source-content scope remains unresolved by this audit.'}
(OUT/'visual-active-drafts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['summary']))
