#!/usr/bin/env python3
"""Render script-reviewed Exam 80 Reserve Forces Act diagrams without network calls.

Fixed 1600 x 900 frame, exact font metrics, no font shrinking or text truncation.
Private scripts are optional audit inputs and are never copied into this archive.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import html
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from PIL import Image, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'reserve-forces-act'
DATA = BASE / 'diagrams'
WIDTH, HEIGHT = 1600, 900
BG, INK, MUTED, BLUE = '#F4F4F4', '#202124', '#545860', '#275AA3'
FONT_DIR = Path('/usr/share/fonts/opentype/noto')
KINDS = {'compare': '주체·기준 비교', 'process': '처리 절차', 'rule': '핵심 구조', 'deadline': '기한·숫자', 'exception': '원칙·예외'}
FONTS = {}

def font(size, bold=False):
    key = (size, bold)
    if key not in FONTS:
        FONTS[key] = ImageFont.truetype(str(FONT_DIR / ('NotoSansCJK-Bold.ttc' if bold else 'NotoSansCJK-Regular.ttc')), size, index=1)
    return FONTS[key]

def text_width(text, size, bold=False):
    return font(size, bold).getlength(str(text))

def wrap(text, width, size, bold=False):
    """Keep words, particles and number/unit expressions intact at line ends."""
    lines = []
    text = re.sub(r'(\d)\s+(일|명|년|월|시간|분|초|세|원|퍼센트)(?=\s|$|[.,·])', r'\1\2', str(text))
    for paragraph in text.split('\n'):
        current = ''
        for word in paragraph.split():
            if text_width(word, size, bold) > width + 0.5:
                raise ValueError(f'어절이 열 너비를 초과함: {word}')
            candidate = (current + ' ' + word).strip()
            if current and text_width(candidate, size, bold) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines or ['']

def esc(value):
    return html.escape(str(value), quote=True)

class Canvas:
    def __init__(self, title, description):
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc" lang="ko">', f'<title id="title">{esc(title)}</title>', f'<desc id="desc">{esc(description)}</desc>']
        self.boxes = []
        self.rect(0, 0, WIDTH, HEIGHT, BG)

    def rect(self, x, y, w, h, fill, radius=0, stroke='none'):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def line(self, x1, y1, x2, y2, color='#DADDE2', sw=2):
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"/>')

    def text(self, text, x, y, size, bold=False, color=INK, anchor='start', region=None, role='body'):
        width = text_width(text, size, bold)
        left = x if anchor == 'start' else x - width if anchor == 'end' else x - width/2
        box = font(size, bold).getbbox(str(text), anchor='ls')
        b = {'text':str(text), 'x':round(left+box[0], 2), 'y':round(y+box[1], 2), 'width':round(box[2]-box[0], 2), 'height':round(box[3]-box[1], 2), 'fontSize':size, 'role':role}
        if region:
            b['region'] = region
        self.boxes.append(b)
        self.parts.append(f'<text x="{x:g}" y="{y:g}" font-family="Noto Sans CJK KR,Noto Sans KR,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" text-anchor="{anchor}">{esc(text)}</text>')

    def finish(self):
        return '\n'.join(self.parts + ['</svg>', ''])

def item_layout(item, width=636):
    label = wrap(item.get('label',''), width, 24, True) if item.get('label') else []
    body = wrap(item['text'], width, 32)
    return {'label':label, 'body':body, 'height': len(label)*31 + len(body)*44 + (7 if label else 0)}

def render_diagram(lesson, d, page, total, source):
    c = Canvas(d['title'], f"{lesson['lessonId']} {lesson['lessonTitle']}. {d.get('subtitle','')}")
    c.rect(64, 38, 7, 29, BLUE, 3)
    c.text('제80회  ·  예비군법', 87, 63, 25, True, BLUE, role='eyebrow')
    c.text(KINDS[d['kind']], 1536, 63, 23, color=MUTED, anchor='end', role='eyebrow')
    title_lines = wrap(d['title'], 1472, 52, True)
    if len(title_lines) != 1:
        raise ValueError('제목을 한 줄로 나눠야 함: '+d['title'])
    c.text(d['title'], 64, 142, 52, True, role='title')
    subtitle = wrap(d.get('subtitle',''), 1468, 27)
    if len(subtitle) > 2:
        raise ValueError('부제 설명이 너무 김: '+d['title'])
    for i, line in enumerate(subtitle):
        c.text(line, 67, 190 + 35*i, 27, color=MUTED, role='subtitle')
    for side, x in [('left',64), ('right',816)]:
        col = d[side]
        c.rect(x, 248, 720, 492, '#FFFFFF', 18)
        c.rect(x, 248, 720, 83, '#EAF0F8', 18)
        c.rect(x, 309, 720, 22, '#EAF0F8')
        header = wrap(col['title'], 636, 34, True)
        if len(header) != 1:
            raise ValueError(f"열 제목이 너무 김: {d['title']} / {col['title']}")
        c.text(col['title'], x+42, 303, 34, True, BLUE, region=[x+36,257,648,72], role='column-title')
        layouts = [item_layout(item) for item in col['items']]
        used = sum(item['height'] for item in layouts) + 24*max(0,len(layouts)-1)
        if used > 357:
            raise ValueError(f"카드 내용이 높이를 초과함({used}px > 357px): {lesson['lessonId']} / {d['id']} / {side}; 항목 단위로 분할 필요")
        gap = min(40, (357-sum(item['height'] for item in layouts))/max(1,len(layouts)-1)) if len(layouts)>1 else 0
        y = 365
        for i, item in enumerate(layouts):
            if i:
                c.line(x+42, y-18, x+678, y-18, '#E5E7EB', 1.5)
            for line in item['label']:
                c.text(line, x+42, y+24, 24, True, BLUE, region=[x+36,342,648,380], role='item-label')
                y += 31
            if item['label']:
                y += 7
            for line in item['body']:
                c.text(line, x+42, y+32, 32, region=[x+36,342,648,380])
                y += 44
            y += gap
    if d.get('note'):
        c.rect(64, 760, 1472, 77, '#E6EDF7', 12)
        c.rect(64, 760, 6, 77, BLUE, 3)
        lines = wrap(d['note'], 1390, 28, True)
        if len(lines)>2:
            raise ValueError('아래 요점이 두 줄을 초과함: '+d['id'])
        start = 807 if len(lines)==1 else 792
        for i,line in enumerate(lines):
            c.text(line, 92, start + i*34, 28, True, BLUE, region=[85,767,1420,65], role='note')
    footer = source.get('article', lesson['lessonTitle'])
    if text_width(footer,20)>1150:
        footer = lesson['lessonTitle'].split(',')[0]
    if text_width(footer,20)>1150:
        raise ValueError('조문 출처가 너무 김: '+footer)
    c.text(footer, 66, 877, 20, color=MUTED, role='source')
    c.text(f"{lesson['lessonId']}  ·  {page:02d} / {total:02d}", 1536, 877, 20, True, MUTED, anchor='end', role='page')
    errors = check_geometry(c.boxes)
    if errors:
        raise ValueError(f"{lesson['lessonId']} {d['id']} geometry: {errors[:3]}")
    return c.finish(), c.boxes

def check_geometry(boxes):
    errors=[]
    for b in boxes:
        if b['x'] < 0 or b['y'] < 0 or b['x']+b['width'] > WIDTH+.5 or b['y']+b['height'] > HEIGHT+.5:
            errors.append({'type':'canvas-overflow','text':b['text']})
        if 'region' in b:
            x,y,w,h=b['region']
            if b['x'] < x-.5 or b['y'] < y-.5 or b['x']+b['width'] > x+w+.5 or b['y']+b['height'] > y+h+.5:
                errors.append({'type':'region-overflow','text':b['text']})
    for i,a in enumerate(boxes):
        for b in boxes[i+1:]:
            if not a['text'].strip() or not b['text'].strip(): continue
            dx=min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])
            dy=min(a['y']+a['height'],b['y']+b['height'])-max(a['y'],b['y'])
            if dx>1 and dy>1:
                errors.append({'type':'text-overlap','text':[a['text'],b['text']]})
    return errors

def validate(lesson, source, script=None):
    errors=[]
    if lesson.get('lessonId')!=source['lessonId']: errors.append('lesson-id-mismatch')
    if lesson.get('lessonTitle')!=source['title']: errors.append('lesson-title-mismatch')
    if not lesson.get('diagrams'): errors.append('empty-diagrams')
    if not lesson.get('review',{}).get('scriptReadInFull'): errors.append('script-not-reviewed')
    if lesson.get('review',{}).get('issues'): errors.append('unresolved-content-issues')
    ids=[d['id'] for d in lesson['diagrams']]
    if len(ids)!=len(set(ids)): errors.append('duplicate-diagram-ids')
    refs=set()
    for c in lesson.get('coverage',[]): refs.update(c.get('diagramIds',[]))
    if not lesson.get('coverage'): errors.append('empty-topic-coverage')
    if refs-set(ids): errors.append('coverage-links-missing')
    if set(ids)-refs: errors.append('diagrams-without-topic-coverage')
    for d in lesson['diagrams']:
        if d.get('kind') not in KINDS: errors.append(d['id']+': invalid-kind')
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',d['id']): errors.append(d['id']+': invalid-id')
        for side in ['left','right']:
            col=d.get(side,{})
            if not col.get('title') or not 1<=len(col.get('items',[]))<=3: errors.append(d['id']+': invalid-column')
            if any(not i.get('text','').strip() for i in col.get('items',[])): errors.append(d['id']+': empty-text')
        if not d.get('sourceRanges'): errors.append(d['id']+': no-source-ranges')
        for r in d.get('sourceRanges',[]):
            if not isinstance(r.get('startLine'),int) or not isinstance(r.get('endLine'),int) or not 1<=r['startLine']<=r['endLine']<=source['sourceLines']:
                errors.append(d['id']+': invalid-source-range')
        if script is not None:
            segments=['\n'.join(script.splitlines()[r['startLine']-1:r['endLine']]) for r in d.get('sourceRanges',[]) if isinstance(r.get('startLine'),int) and isinstance(r.get('endLine'),int)]
            if not any(s.strip() for s in segments): errors.append(d['id']+': source-range-empty')
    return errors

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def rasterize(path):
    png=path.with_suffix('.png')
    if not png.exists() or png.stat().st_mtime < path.stat().st_mtime:
        subprocess.run(['inkscape',str(path),'--export-type=png','--export-filename='+str(png),'--export-width=1600','--export-height=900'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        with Image.open(png) as im:
            im.convert('RGB').quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE).save(png,optimize=True)
    with Image.open(png) as im:
        if im.size!=(WIDTH,HEIGHT): raise ValueError('Wrong PNG dimensions '+str(png))
        if im.mode!='P':
            im.convert('RGB').quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE).save(png,optimize=True)
    return png

def gallery(manifest):
    cards=[]
    for lesson in manifest['lessons']:
        heading=esc(lesson['title'])
        items=[]
        for d in lesson['diagrams']:
            svg='../'+d['svg'].removeprefix('reserve-forces-act/')
            png='../'+d['png'].removeprefix('reserve-forces-act/')
            items.append(f'<article class="diagram" data-search="{esc(lesson["lessonId"]+" "+lesson["title"]+" "+d["title"])}"><a href="{png}" target="_blank"><img loading="lazy" src="{png}" width="1600" height="900" alt="{esc(d["title"])}"></a><div class="caption"><b>{esc(d["title"])}</b><span><a href="{svg}" download>SVG</a><a href="{png}" download>PNG</a></span></div></article>')
        cards.append(f'<section data-lesson="{esc(lesson["lessonId"])}"><h2>{esc(lesson["lessonId"])} <span>{heading}</span><small>{len(items)}장</small></h2><div class="grid">'+''.join(items)+'</div></section>')
    doc='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>예비군법 제80회 강의 도식</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f4f4;color:#202124;word-break:keep-all;font:16px/1.55 "Noto Sans CJK KR",sans-serif}header{padding:40px max(24px,calc((100% - 1440px)/2));background:#fff;border-bottom:1px solid #dce0e5}header p{color:#545860;max-width:900px}h1{margin:0 0 12px;font-size:34px;letter-spacing:-1px}.tools{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px}input,select{font:inherit;padding:12px 16px;border:1px solid #b8c2d1;border-radius:8px;background:#fff}input{flex:1;min-width:230px}main{max-width:1488px;margin:auto;padding:24px}h2{display:flex;gap:15px;align-items:baseline;font-size:17px;color:#275aa3;margin:32px 0 14px}h2 span{font-size:20px;color:#202124}h2 small{margin-left:auto;white-space:nowrap}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.diagram{background:#fff;border:1px solid #dce0e5;border-radius:12px;overflow:hidden}img{width:100%;height:auto;display:block}.caption{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:14px 18px;border-top:1px solid #edf0f3}.caption span{display:flex;gap:14px}.caption a{color:#275aa3;text-decoration:none}footer{max-width:1440px;margin:20px auto 45px;padding:0 24px;color:#545860}a{color:#275aa3}[hidden]{display:none!important}.count{font-size:15px;color:#545860;margin-top:16px}@media(max-width:850px){.grid{grid-template-columns:1fr}header{padding:28px 20px}main{padding:16px}h1{font-size:28px}h2{flex-wrap:wrap;gap:6px 12px}h2 span{font-size:18px;flex-basis:100%}.caption{font-size:14px}h2 small{margin:0}.tools{gap:8px}select{width:100%}}@media print{header .tools,.caption span{display:none}.grid{grid-template-columns:1fr}.diagram{break-inside:avoid}body{background:white}}
</style><header><h1>예비군법 강의 도식</h1><p>제80회 · 2027년 전반기. 기존 34강 스크립트의 설명 순서에 맞춰 주체, 절차, 기한, 원칙과 예외를 정리했습니다. 이미지를 누르면 원래 크기로 볼 수 있습니다.</p><div class="tools"><input id="q" aria-label="강의와 도식 검색" placeholder="강의 번호·제목·키워드 검색"><select id="lesson" aria-label="강의 선택"><option value="">전체 강의</option>'''+''.join(f'<option value="{l["lessonId"]}">{l["lessonId"]} · {esc(l["title"])}</option>' for l in manifest['lessons'])+'''</select></div><div class="count" id="count"></div></header><main>'''+''.join(cards)+'''</main><footer>내용 기준: 제80회 기존 강의 스크립트. 강의 화면에 삽입하기 전용으로 정리한 자료이며, 법령을 독립적으로 최신 검증한 자료는 아닙니다. <a href="manifest.json">도식 목록</a> · <a href="review/audit-report.json">제작·검수 기록</a></footer><script>
const q=document.querySelector('#q'),sel=document.querySelector('#lesson');function filter(){let n=0;const term=q.value.trim().toLowerCase();for(const s of document.querySelectorAll('section')){let visible=0;for(const d of s.querySelectorAll('.diagram')){const show=(!sel.value||sel.value===s.dataset.lesson)&&d.dataset.search.toLowerCase().includes(term);d.hidden=!show;if(show){n++;visible++}}s.hidden=!visible}document.querySelector('#count').textContent=`현재 ${n}장 표시`;}q.addEventListener('input',filter);sel.addEventListener('change',filter);filter();
</script></html>'''
    (DATA/'gallery.html').write_text(doc)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--only',nargs='*')
    ap.add_argument('--source-root',type=Path)
    ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--svg-only',action='store_true')
    args=ap.parse_args()
    sources=json.loads((DATA/'source-index.json').read_text())
    source_map={l['lessonId']:l for l in sources['lessons']}
    files=sorted((DATA/'content').glob('RL-*.json'))
    if args.only: files=[f for f in files if f.stem in args.only]
    failures=[]; lessons=[]; pending=[]; boxes_count=0; font_sizes=Counter()
    for path in files:
        l=json.loads(path.read_text()); source=source_map[l['lessonId']]
        script=None
        if args.source_root:
            raw=(args.source_root/source['sourcePath']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=source['sourceSha256']:
                failures.append({'lessonId':l['lessonId'],'error':'source-sha256-mismatch'});continue
            script=raw.decode()
        errors=validate(l,source,script)
        if errors:
            failures.append({'lessonId':l['lessonId'],'error':errors});continue
        records=[]
        for i,d in enumerate(l['diagrams'],1):
            try:
                svg,boxes=render_diagram(l,d,i,len(l['diagrams']),source)
                folder=BASE/f"lesson-{l['lessonId'][3:]}/diagrams"
                folder.mkdir(parents=True,exist_ok=True)
                file=folder/f"rl-{l['lessonId'][3:]}-{i:02d}-{d['id']}.svg"
                if not file.exists() or file.read_text()!=svg:file.write_text(svg)
                pending.append(file)
                boxes_count+=len(boxes)
                for b in boxes:font_sizes[(b['role'],b['fontSize'])]+=1
                records.append({'id':d['id'],'title':d['title'],'kind':d['kind'],'svg':str(file.relative_to(ROOT)),'png':str(file.with_suffix('.png').relative_to(ROOT)),'sourceRanges':d['sourceRanges'],'svgSha256':hashlib.sha256(svg.encode()).hexdigest(),'geometry':{'textBoxes':len(boxes),'overflow':0,'overlap':0}})
            except Exception as e:
                failures.append({'lessonId':l['lessonId'],'diagramId':d['id'],'error':str(e)})
        lessons.append({'lessonId':l['lessonId'],'title':l['lessonTitle'],'source':source,'contentPath':str(path.relative_to(ROOT)),'contentSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'diagrams':records,'topicCoverage':l['coverage'],'review':l['review']})
    write_json(DATA/'review/render-errors.json',failures)
    if failures:
        print(json.dumps({'failures':failures,'renderedSVGs':len(pending)},ensure_ascii=False,indent=2));return 1
    if not args.svg_only:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:list(ex.map(rasterize,pending))
        for l in lessons:
            for d in l['diagrams']:
                png=ROOT/d['png'];d['pngSha256']=hashlib.sha256(png.read_bytes()).hexdigest();d['pngBytes']=png.stat().st_size
    manifest={'schemaVersion':'reserve-script-diagrams-v1','exam':'80','examPeriod':'27h1','contentBasis':'existing-lecture-scripts','canvas':{'width':WIDTH,'height':HEIGHT},'lessonCount':len(lessons),'diagramCount':len(pending),'lessons':lessons}
    if args.only:
        write_json(DATA/'review/partial-render.json',manifest)
    else:
        write_json(DATA/'manifest.json',manifest)
        gallery(manifest)
        expected={ROOT/d[key] for l in lessons for d in l['diagrams'] for key in ('svg','png')}
        for l in lessons:
            folder=BASE/f"lesson-{l['lessonId'][3:]}/diagrams"
            for old in folder.iterdir():
                if re.fullmatch(r'rl-\d{3}-\d{2,3}-[a-z0-9-]+\.(svg|png)',old.name) and old not in expected:
                    old.unlink()
        (DATA/'review/partial-render.json').unlink(missing_ok=True)
        report={'schemaVersion':1,'exam':'80','contentBasis':'script-only','expectedLessons':34,'renderedLessons':len(lessons),'renderedDiagrams':len(pending),'sourceHashesVerified':bool(args.source_root),'scriptReview':'authored by agents after reading all assigned scripts; independent review recorded separately','textBoundsChecked':boxes_count,'overflowCount':0,'overlapCount':0,'bodyFontSize':32,'autoFontShrink':False,'textTruncation':False,'rasterized':not args.svg_only,'pngDimensions':[WIDTH,HEIGHT],'sourceLawFreshnessVerified':False,'siteIntegrationVerified':False,'failures':failures,'fontSizes':[{'role':r,'size':s,'boxes':n} for (r,s),n in sorted(font_sizes.items())]}
        write_json(DATA/'review/audit-report.json',report)
    print(json.dumps({'lessons':len(lessons),'diagrams':len(pending),'boxes':boxes_count,'rasterized':not args.svg_only,'errors':len(failures)},ensure_ascii=False))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
