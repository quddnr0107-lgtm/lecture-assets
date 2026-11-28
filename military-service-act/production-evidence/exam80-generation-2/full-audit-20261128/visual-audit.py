#!/usr/bin/env python3
"""Read-only integrity and font-geometry audit of official diagram assets.

Only this audit's visual-* evidence files and the explicitly supplied scratch
directory are written. Source scripts and production manifests are not changed.
"""
from pathlib import Path
from collections import Counter, defaultdict
from functools import lru_cache
import argparse, hashlib, json, re, subprocess, xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from lxml import html

ROOT=Path(__file__).resolve().parents[4]
SUB=ROOT/'military-service-act'
OUT=Path(__file__).resolve().parent
TMP=ROOT.parent/'audit-tmp'/'visual'
TMP.mkdir(parents=True,exist_ok=True)
FONTS=Path('/usr/share/fonts/opentype/noto')
NS={'s':'http://www.w3.org/2000/svg'}
W,H=1600,1120
parser=argparse.ArgumentParser()
parser.add_argument('--output-prefix',default='')
parser.add_argument('--no-contact-sheets',action='store_true')
args=parser.parse_args()

def sha(b): return hashlib.sha256(b).hexdigest()
def readj(p): return json.loads(p.read_text())
def compact(s): return re.sub(r'\s+','',str(s))
def rel(p): return str(p.relative_to(ROOT))

@lru_cache(None)
def font(size,bold=False):
    return ImageFont.truetype(str(FONTS/('NotoSansCJK-Bold.ttc' if bold else 'NotoSansCJK-Regular.ttc')),size,index=1)

cmap=TTFont(FONTS/'NotoSansCJK-Regular.ttc',fontNumber=1).getBestCmap()
manifest=readj(SUB/'diagrams-manifest.json')
items=manifest['items']
content=readj(SUB/'editorial-content.json')
sourceindex=readj(SUB/'script-sources-exam80.json')
sources={i['lecture_id']:i for i in sourceindex['lectures']}
bylesson=defaultdict(list)
for i in items: bylesson[i['lecture_id']].append(i)
findings=[]
observations=[]
rows=[]
checks=Counter()

def problem(kind,ident,detail,**kwargs):
    findings.append(dict(kind=kind,id=ident,detail=detail,**kwargs))

if len({i['id'] for i in items})!=len(items): problem('duplicate_id','manifest','Duplicate official page IDs')
for k,n in [('diagram_count',len(items)),('concept_diagram_count',len(content)),('lecture_count',len(bylesson)),('lesson_count',len(bylesson))]:
    if manifest.get(k)!=n: problem('manifest_count','manifest',f'{k}={manifest.get(k)} vs actual {n}')
if set(bylesson)!={f'MS-{n:03d}' for n in range(1,167)}: problem('lecture_coverage','manifest','Expected MS-001..MS-166')
if manifest.get('content_source_sha256')!=sha((SUB/'editorial-content.json').read_bytes()):
    problem('content_source_hash','manifest','editorial-content.json SHA-256 does not equal manifest.content_source_sha256',recorded=manifest.get('content_source_sha256'),actual=sha((SUB/'editorial-content.json').read_bytes()))

for item in items:
    ident=item['id']; lid=item['lecture_id']; row={'id':ident,'lecture_id':lid,'files':{},'text_boxes':[]}
    if item['lesson_number']!=int(lid.split('-')[1]):problem('lesson_number',ident,'ID and lesson_number disagree')
    for ext in ('svg','webp'):
        meta=item['files'][ext]; p=ROOT/meta['path']
        if not p.exists(): problem('missing_file',ident,meta['path']);continue
        data=p.read_bytes(); checks['files_read']+=1
        row['files'][ext]={'path':meta['path'],'bytes':len(data),'sha256':sha(data)}
        if meta['bytes']!=len(data):problem('bytes_mismatch',ident,ext,recorded=meta['bytes'],actual=len(data))
        if meta['sha256']!=sha(data):problem('sha256_mismatch',ident,ext,recorded=meta['sha256'],actual=sha(data))
        expected=f'military-service-act/lesson-{item["lesson_number"]:03d}/diagrams/{ident}.{ext}'
        if meta['path']!=expected:problem('path_mismatch',ident,ext,actual=meta['path'],expected=expected)
        if ext=='webp':
            try:
                with Image.open(p) as im:
                    im.load();row['raster_size']=list(im.size);row['raster_format']=im.format; checks['webp_decoded']+=1
                    if im.size!=(W,H):problem('raster_size',ident,str(im.size))
                    if im.format!='WEBP':problem('raster_format',ident,str(im.format))
                    # RIFF chunks may contain VP8X; find a VP8L image-data chunk.
                    cursor=12; chunks=[]
                    while cursor+8<=len(data):
                        chunk=data[cursor:cursor+4].decode('ascii','replace');n=int.from_bytes(data[cursor+4:cursor+8],'little');chunks.append(chunk);cursor+=8+n+(n%2)
                    row['webp_chunks']=chunks
                    if 'VP8L' not in chunks:problem('not_lossless_webp',ident,str(chunks))
            except Exception as e:problem('raster_decode',ident,str(e))
    svgpath=ROOT/item['files']['svg']['path']
    if not svgpath.exists():rows.append(row);continue
    try:
        tree=ET.fromstring(svgpath.read_bytes()); checks['svg_parsed']+=1
        if tree.get('width')!=str(W) or tree.get('height')!=str(H) or tree.get('viewBox')!='0 0 1600 1120':
            problem('svg_canvas',ident,str(tree.attrib))
        texts=[]
        for e in tree.findall('.//s:text',NS):
            text=''.join(e.itertext());texts.append(text)
            if e.get('transform') or e.get('style'):problem('unsupported_text_style',ident,str(e.attrib))
            size=float(e.get('font-size','16'));bold=int(e.get('font-weight','400'))>=600
            f=font(int(size),bold);x=float(e.get('x','0'));y=float(e.get('y','0'));anchor=e.get('text-anchor','start')
            adv=f.getlength(text)
            if anchor=='end':x-=adv
            elif anchor=='middle':x-=adv/2
            x0,y0,x1,y1=f.getbbox(text,anchor='ls')
            box=[round(x+x0,2),round(y+y0,2),round(x+x1,2),round(y+y1,2)]
            b={'text':text,'box':box,'font_size':size,'fill':e.get('fill'),'bold':bold,'baseline':y}
            row['text_boxes'].append(b);checks['text_runs_measured']+=1
            if box[0]<0 or box[1]<0 or box[2]>W or box[3]>H:problem('text_canvas_overflow',ident,text,box=box)
            bad=sorted({ch for ch in text if ord(ch) not in cmap and not ch.isspace()})
            if bad:problem('missing_font_glyph',ident,''.join(bad),text=text)
        concat=compact(' '.join(texts))
        fields=[('title',item['content']['title']),('subtitle',item['content'].get('subtitle','')),('takeaway',item['content'].get('takeaway',''))]
        for n,sec in enumerate(item['content']['sections']):
            fields.append((f'section{n}.heading',sec['heading']))
            for m,it in enumerate(sec['items']):
                for key in ('label','text'):fields.append((f'section{n}.item{m}.{key}',it.get(key,'')))
        for name,txt in fields:
            if txt and compact(txt) not in concat:
                # Hand-reviewed supplements sometimes replace a slash/comma/colon
                # delimiter with a line break. Preserve as an observation.
                separators=lambda s:re.sub(r'[\s/,:：]+','',s)
                if separators(txt) in separators(' '.join(texts)):
                    observations.append({'kind':'punctuation_replaced_by_linebreak','id':ident,'field':name,'content':txt})
                else:problem('content_not_in_svg',ident,name,content=txt)
        for a_i,a in enumerate(row['text_boxes']):
            ax0,ay0,ax1,ay1=a['box']
            for b in row['text_boxes'][a_i+1:]:
                bx0,by0,bx1,by1=b['box'];ix=min(ax1,bx1)-max(ax0,bx0);iy=min(ay1,by1)-max(ay0,by0)
                if ix>1.2 and iy>1.2:
                    problem('text_overlap_candidate',ident,'Actual-font glyph boxes overlap',a=a,b=b,intersection=[round(ix,2),round(iy,2)])
        # The upper-right page counter should use published order/total rather than old totals.
        counters=[t for t in texts if '개념·핵심 도식' in t]
        row['printed_counter']=counters[0] if counters else None
        if counters:
            m=re.search(r'(\d+)\s*/\s*(\d+)',counters[0])
            if m and (int(m[1])!=item['diagram_number'] or int(m[2])!=len(bylesson[lid])):
                problem('stale_page_counter',ident,counters[0],expected_diagram_number=item['diagram_number'],actual_published_pages=len(bylesson[lid]))
        else:row['counter_kind']='supplement_label'
        index=item['content_index']
        if not isinstance(index,int) or not 0<=index<len(content):problem('content_index',ident,str(index))
        elif content[index]['lecture_id']!=lid or content[index]['title']!=item['title']:problem('content_index_identity',ident,str(index))
        ss=item.get('script_source',{});source=sources.get(lid,{})
        if ss.get('path')!=source.get('path') or ss.get('git_blob_sha')!=source.get('script_git_blob_sha') or ss.get('source_commit')!=sourceindex['source_commit']:
            problem('script_reference_identity',ident,'Manifest does not match public pinned source index')
    except Exception as e:problem('svg_parse_or_measure',ident,str(e))
    rows.append(row)

observed_body=[]
for row in rows:
    # Supplement templates use different minimum sizes. Audit their actual body
    # runs rather than borrowing the baseline builder's old 36px guarantee.
    sizes=[t['font_size'] for t in row['text_boxes'] if 400<t['baseline']<1010 and t['fill']=='#25241F' and not t['bold']]
    if sizes:observed_body.append({'id':row['id'],'min_body_font_px':min(sizes)})
audit=readj(SUB/'editorial-audit.json')
declared_min=audit['layout']['body_font_minimum_px']
smaller=[r for r in observed_body if r['min_body_font_px']<declared_min]
if smaller:problem('audit_font_minimum_stale','editorial-audit.json','Declared minimum is not the actual minimum after supplements',declared_minimum_px=declared_min,actual_minimum_px=min(r['min_body_font_px'] for r in observed_body),affected_pages=smaller)

for lid,group in bylesson.items():
    folder=SUB/f'lesson-{int(lid.split("-")[1]):03d}'/'diagrams';lm=readj(folder/'manifest.json')
    if lm['diagram_count']!=len(group):problem('lesson_manifest_count',lid,str(lm['diagram_count']))
    if lm['items']!=group:problem('lesson_manifest_content',lid,'Lesson and global manifest items differ')
    expected={i['id'] for i in group}
    for ext in ('svg','webp'):
        actual={p.stem for p in folder.glob('*.'+ext)}
        if expected!=actual:problem('official_directory_set',lid,ext,missing=sorted(expected-actual),extra=sorted(actual-expected))

layout=readj(SUB/'editorial-layout-check.json')
layout_ids=[x['id'] for x in layout['checks']]
if set(layout_ids)!={i['id'] for i in items} or len(layout_ids)!=len(items):problem('layout_record_coverage','all','Layout check ID set/count differs')
doc=html.fromstring((SUB/'editorial-index.html').read_text())
image_srcs=doc.xpath('//main//img/@src')
expected_srcs=[str(Path(i['files']['webp']['path']).relative_to('military-service-act')) for i in items]
if Counter(image_srcs)!=Counter(expected_srcs):problem('gallery_image_set','gallery','Gallery image paths differ from official manifest')
for target in doc.xpath('//main//a/@href')+image_srcs:
    if not target.startswith(('http:','https:','#')) and not (SUB/target).exists():problem('gallery_broken_link','gallery',target)
header=' '.join(doc.xpath('//header//text()'))
queue=readj(SUB/'production-queue.json');support=queue['existing_diagram_support_review'];done=sum(j['status']=='completed' for j in queue['jobs'])
gallery_patterns = [(r'공개\s*(\d+)장 문구 대조·교정 완료',support['published_diagram_claims_verified_pages'],'published diagram claims reviewed'),(r'원고 전체 범위 검토:\s*(\d+)강 완료',done,'completed lectures'),(r'완료\s*·\s*(\d+)강 대기',166-done,'pending full-script coverage lectures')] if '공개316장 문구 대조·교정 완료' in header else [(r'원고 근거 확인\s*(\d+)장',support['verified_existing_pages'],'verified existing pages'),(r'대조 대기\s*(\d+)장',support['pending_existing_pages'],'pending existing pages'),(r'전체 핵심 검토 완료\s*(\d+)강',done,'completed lectures')]
for patt,expected,label in gallery_patterns:
    m=re.search(patt,header)
    if not m or int(m[1])!=expected:problem('gallery_stale_status','gallery',label,recorded=int(m[1]) if m else None,expected=expected)

readme=(SUB/'README.md').read_text()
readme_counts={f'MS-{m[1]}':int(m[2]) for m in re.finditer(r'\| \[MS-(\d{3})\].*?\| (\d+)장 \|',readme)}
if readme_counts!={k:len(v) for k,v in bylesson.items()}:problem('readme_lecture_counts','README','Counts differ from global manifest')

drafts={ext:sorted(rel(p) for p in SUB.glob('production-evidence/**/draft-batches/**/*.'+ext)) for ext in ('svg','webp')}
report={'schema_version':1,'date_kst':'2026-11-28','audit_scope':'Published diagram asset integrity, font geometry, file-list consistency; no manuscript semantic audit','repository_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'summary':{'official_pages':len(items),'official_lectures':len(bylesson),'concept_diagrams':len(content),'checks':dict(checks),'draft_svg_files':len(drafts['svg']),'draft_webp_files':len(drafts['webp']),'findings_by_kind':dict(Counter(f['kind'] for f in findings))},'method_limits':['Pillow FreeType measurements use Noto Sans CJK KR font index 1 and actual glyph boxes; no browser DOM geometry was available.','Text overlap candidates require inspection because deliberate decoration and font rendering differences are possible.','Raster-vs-SVG pixel comparison is recorded separately.','This audit does not read the private manuscripts or establish legal/content accuracy.','Physical draft counts include superseded and already-promoted draft files.'],'findings':findings,'observations':observations,'pages':rows,'draft_paths':drafts}
(OUT/(args.output_prefix+'visual-integrity-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report['summary'],ensure_ascii=False,indent=2))
if args.no_contact_sheets:
    raise SystemExit(0)

# All official pages in indexed contact sheets; labels remain legible at review size.
thumb_w,thumb_h=400,280;cell_h=306;cols,per=4,16
labelfont=font(17)
sheets=[]
for start in range(0,len(items),per):
    batch=items[start:start+per];sheet=Image.new('RGB',(cols*thumb_w,4*cell_h),'#ebeae4');draw=ImageDraw.Draw(sheet)
    for pos,item in enumerate(batch):
        x=(pos%cols)*thumb_w;y=(pos//cols)*cell_h
        with Image.open(ROOT/item['files']['webp']['path']) as im:sheet.paste(im.convert('RGB').resize((thumb_w,thumb_h),Image.Resampling.LANCZOS),(x,y+24))
        draw.text((x+5,y+2),item['id'],font=labelfont,fill='#111111')
    name=f'contact-{start//per+1:02d}.jpg';sheet.save(TMP/name,quality=94)
    sheets.append({'path':str(TMP/name),'ids':[i['id'] for i in batch]})
(OUT/(args.output_prefix+'visual-contact-sheet-index.json')).write_text(json.dumps(sheets,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report['summary'],ensure_ascii=False,indent=2))
print('Evidence:',OUT/'visual-integrity-report.json')
