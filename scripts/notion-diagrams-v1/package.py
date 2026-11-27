#!/usr/bin/env python3
"""Create the catalogue, accessible reading text, gallery and file hashes."""
from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont
import json, hashlib, re

ROOT=Path(__file__).resolve().parents[2]
SUB=ROOT/'integrated-defense'
DEST=SUB/'notion-v1'
DATA=json.loads((DEST/'content.json').read_text())
RECORDS=json.loads((DEST/'render-records.json').read_text())
DATE='2026-11-27'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

def font(s,bold=False):return ImageFont.truetype(BOLD if bold else FONT,s,index=1)
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s+'\n')

def main():
    items=[];allpaths=[];cards=[];lesson_rows=[]
    for l in DATA['lessons']:
        local=SUB/f'lesson-{l["lesson"]:03d}'/'diagrams'/'notion-v1'
        md=[f'# {l["lesson"]:02d}강 · {l["title"]}', '', f'**{l["lecture_id"]} · 통합방위법 {l["article"]} · 7번 선택 스타일 적용**','', '[전체 도식 목록](../../../notion-v1/)','']
        for d in l['diagrams']:
            rec=next(x for x in RECORDS if x['id']==f'{l["lecture_id"]}-{d["id"]}')
            files={}
            for ext in ['svg','png','webp']:
                path=SUB/(rec['base']+'.'+ext);raw=path.read_bytes()
                files[ext]={'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'width':1600,'height':1120}
                allpaths.append(str(path.relative_to(ROOT)))
            item={**rec,'status':'prepared','style':'07-notion-editorial','files':files}
            items.append(item)
            name=Path(rec['base']).name
            md += [f'## {d["id"]} · {d["title"]}','',d['subtitle'],'',f'![{d["title"]}]({name}.webp)','',f'[PNG]({name}.png) · [SVG]({name}.svg) · [WebP]({name}.webp)','']
            for sec in d['sections']:
                md += [f'### {sec["title"]}','','| 구분 | 내용 |','|---|---|']
                md += [f'| {i["label"]} | {i["detail"].replace("|","/")} |' for i in sec['items']]
                md += ['']
            md += ['**기억할 문장:** '+d['takeaway'],'','### 조건·범위','']
            md += ['- '+n for n in d['notes']]
            md += ['','### 근거','']+['- ['+s['basis']+']('+s['url']+')' for s in d['sources']]+['']
            search=f'{l["lecture_id"]} {l["lesson"]}강 {l["title"]} {d["title"]}'
            base='../'+rec['base']
            cards.append(f'<article class="card" data-lesson="{l["lesson"]}" data-search="{escape(search,quote=True)}"><a href="{base}.png" target="_blank" rel="noopener"><img src="{base}.webp" width="1600" height="1120" loading="lazy" alt="{escape(d["title"],quote=True)}"></a><div class="caption"><span>{l["lesson"]:02d}강 · {d["id"]}</span><h2>{escape(d["title"])}</h2><p>{escape(d["subtitle"])}</p><nav><a href="{base}.png" target="_blank" rel="noopener">크게 보기</a><a href="{base}.svg" download>SVG</a><a href="{base}.webp" download>WebP</a><a href="../lesson-{l["lesson"]:03d}/diagrams/notion-v1/README.md">본문·근거</a></nav></div></article>')
        write(local/'README.md','\n'.join(md));allpaths.append(str((local/'README.md').relative_to(ROOT)))
        titles=' / '.join(d['title'] for d in l['diagrams'])
        lesson_rows.append(f'| [{l["lesson"]:02d}강 · {l["article"]}](../lesson-{l["lesson"]:03d}/diagrams/notion-v1/) | {l["title"]} | {len(l["diagrams"])} | {titles} |')
    manifest={'schema_version':1,'subject':'integrated-defense','title':'통합방위법 · 7번 선택 스타일 핵심 도식','style':'07-notion-editorial','style_approved_date_kst':DATE,'created_date_kst':DATE,'legal_checked_date_kst':DATE,'lesson_count':len(DATA['lessons']),'diagram_count':len(items),'status':'prepared','content_scope':'각 강의의 핵심 관계를 요약한 도식. 조문 전문·전체 수업 대본·외부 지침을 대체하지 않음.','source_basis':DATA.get('source_basis'),'source_versions':{'law':'법률 제21065호 · 시행 2025-10-01','decree':'대통령령 제36728호 · 시행 2026-10-02'},'items':items}
    write(DEST/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    write(DEST/'lecture-map.json',json.dumps([{'lecture_id':l['lecture_id'],'lesson':l['lesson'],'article':l['article'],'title':l['title'],'diagrams':[f'{l["lecture_id"]}-{d["id"]}' for d in l['diagrams']]} for l in DATA['lessons']],ensure_ascii=False,indent=2))
    # Portable static gallery, no dependencies or remote assets.
    options=''.join(f'<option value="{l["lesson"]}">{l["lesson"]:02d}강 · {escape(l["title"])}</option>' for l in DATA['lessons'])
    html='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>무한회독 · 통합방위법 도식</title><style>
:root{color-scheme:light;font-family:"Noto Sans KR","Apple SD Gothic Neo",system-ui,sans-serif;color:#25241f;background:#fffefc}*{box-sizing:border-box}body{margin:0}header,main,footer{max-width:1460px;margin:auto;padding:30px}header{padding-top:58px;border-bottom:1px solid #dfddd6}.eyebrow{font-size:15px;font-weight:700;letter-spacing:.05em}h1{font-size:clamp(32px,4.5vw,54px);margin:18px 0 16px;letter-spacing:-.04em}header p{color:#706e66;line-height:1.7;max-width:900px}.tools{display:flex;gap:12px;flex-wrap:wrap;margin:26px 0 6px}input,select{font:inherit;padding:13px 15px;border:1px solid #c9c7be;border-radius:3px;background:#fffefc;color:inherit}input{flex:1;min-width:220px}select{max-width:100%}a{color:inherit;text-underline-offset:4px}a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #25241f;outline-offset:4px}.count{margin:0 0 24px;color:#77756e}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:38px 26px}.card{border:1px solid #dfddd6;background:#fffefc}.card img{display:block;width:100%;height:auto}.caption{padding:22px;border-top:1px solid #dfddd6}.caption span{font-size:13px;color:#77756e}.caption h2{font-size:20px;line-height:1.5;margin:8px 0}.caption p{font-size:14px;color:#77756e;line-height:1.6;min-height:44px}.caption nav{display:flex;gap:18px;flex-wrap:wrap;font-size:14px}footer{border-top:1px solid #dfddd6;color:#77756e;line-height:1.8;font-size:14px}[hidden]{display:none!important}@media(max-width:750px){header,main,footer{padding:22px}header{padding-top:36px}.grid{grid-template-columns:1fr;gap:24px}.caption{padding:18px}.tools{display:grid}input{width:100%}}
</style></head><body><header><div class="eyebrow">무한회독 / INTEGRATED DEFENSE ACT</div><h1>통합방위법 도식</h1><p>제80회(27년 전반기) 기존 강의 스크립트를 기준으로 7번 흑백 편집 스타일을 적용한 25강 도식. 그림을 누르면 원본 크기로 볼 수 있습니다. 휴대전화에서는 원본을 열어 확대해 읽으세요.</p><div class="tools"><input id="search" type="search" aria-label="도식 검색" placeholder="강의 번호, 조문, 키워드 검색"><select id="lesson" aria-label="강의 선택"><option value="">모든 강의</option>'''+options+'''</select></div></header><main><p class="count" id="count" aria-live="polite"></p><div class="grid">'''+''.join(cards)+'''</div><p id="empty" hidden>검색 결과가 없습니다. 다른 키워드로 검색해 주세요.</p></main><footer>내용 기준: 제80회 기존 강의 스크립트 · 확인 2026.11.27 · 통합방위법(시행 2025.10.1), 시행령(시행 2026.10.2).<br>흑백 글자, 여백, 괄호와 밑줄을 사용한 자체 제작 도식입니다. <a href="README.md">목록·사용 안내</a> · <a href="style-guide.md">제작 기준</a></footer><script>
const cards=[...document.querySelectorAll('.card')],query=document.querySelector('#search'),lesson=document.querySelector('#lesson');function filter(){const q=query.value.trim().toLocaleLowerCase(),l=lesson.value;let count=0;for(const card of cards){const show=(!q||card.dataset.search.toLocaleLowerCase().includes(q))&&(!l||card.dataset.lesson===l);card.hidden=!show;if(show)count++}document.querySelector('#count').textContent=count+' / '+cards.length+'개 도식';document.querySelector('#empty').hidden=count>0}query.addEventListener('input',filter);lesson.addEventListener('change',filter);filter();
</script></body></html>'''
    write(DEST/'index.html',html)
    md=['# 통합방위법 · 7번 선택 스타일 핵심 도식','','**25강 · '+str(len(items))+'개 도식 · 2026년 11월 27일 작성·법령 확인**','','사용자가 선택한 **07 Notion 참고 편집형**을 공통 스타일로 적용했다. 흰 종이 바탕, 흑백 글자, 얇은 선, 괄호와 밑줄을 사용한다. 도식별 내용에 맞춰 논리 흐름·비교·권한·조건을 다르게 구성했다.','','[갤러리](index.html) · [파일 목록·해시](manifest.json) · [강의 연결표](lecture-map.json) · [제작 기준](style-guide.md) · [검수 기록](verification.json)','','**내용 기준: 제80회(27년 전반기) 기존 통합방위법 스크립트.** [기준 원고·해시](../production-queue/EXAM80-SCRIPT-SOURCE.json) · [원고 일치 검수](script-alignment.json)','','## 강의별 목록','','| 강의·조문 | 주제 | 장수 | 도식 |','|---|---|---:|---|']+lesson_rows+['','## 대표 도식','']
    for ident in ['TB-001-D01','TB-005-D01','TB-013-D01','TB-025-D01']:
        rec=next(x for x in RECORDS if x['id']==ident)
        md += [f'### {ident} · {rec["title"]}','',f'![{rec["title"]}](../{rec["base"]}.webp)','']
    md += ['## 파일과 활용','','- SVG: 편집·확대용 원본. 렌더링 시 Noto Sans CJK KR 사용.','- PNG: 글자 모양이 고정된 확인용 이미지.','- WebP: 사이트 표시용 이미지.','- 각 강의 폴더의 README: 그림 내용, 중요한 조건·범위, 법·시행령 출처.','- `content.json`: 수정 가능한 공개 법령 요약 데이터.','- `index.html`: 내려받은 전체 폴더에서 바로 여는 검색 가능한 갤러리. GitHub는 HTML을 웹페이지로 실행하지 않으므로 저장소에서는 이 목록과 개별 이미지 링크를 사용한다.','','이미지는 1600×1120이다. 글자가 충분히 보이는 크기로 표시하고 작은 화면에서는 확대를 제공한다. 이 자료는 핵심 관계를 정리한 학습 도식이며 조문 전문과 강의의 모든 설명을 대체하지 않는다. 외부 행정규칙·지역별 조례·비공개 작전지침은 이 제작 범위에 포함되지 않는다.','','## 공식 근거','','- [통합방위법 — 법률 제21065호, 시행 2025.10.1](https://www.law.go.kr/LSW/lsInfoR.do?ancYnChk=0&chrClsCd=010202&efYd=20251001&lsiSeq=276315)','- [통합방위법 시행령 — 대통령령 제36728호, 시행 2026.10.2](https://www.law.go.kr/LSW/lsInfoR.do?ancYnChk=0&chrClsCd=010202&efYd=20261002&lsiSeq=290507)','','## 제작·선택 기록','','[10종 디자인 비교 시안](../lesson-005/diagrams/style-studies-v2/) 중 7번을 선택하여 제작했다. Notion 공식 제작물 또는 제휴 자료라는 의미가 아니며 회사 로고는 사용하지 않았다.','','공개 경로: `integrated-defense/lesson-NNN/diagrams/notion-v1/TB-NNN-DNN-topic.{svg,png,webp}`. 사이트 삽입 위치와 영상 시각 정보는 이 자료의 범위에 들어 있지 않다.']
    write(DEST/'README.md','\n'.join(md))
    # Contact pages for visual review: two columns, six diagrams on each page.
    review=ROOT.parent/'production'/'build'; review.mkdir(parents=True,exist_ok=True)
    for offset in range(0,len(RECORDS),6):
        group=RECORDS[offset:offset+6];sheet=Image.new('RGB',(1640,3*610+40),'#eeece6');draw=ImageDraw.Draw(sheet)
        for i,r in enumerate(group):
            x=20+(i%2)*810;y=20+(i//2)*610
            im=Image.open(SUB/(r['base']+'.png')).convert('RGB');im.thumbnail((790,553))
            sheet.paste(im,(x,y));draw.text((x+8,y+563),r['id'],font=font(20,True),fill='#25241f')
        sheet.save(review/f'contact-{offset//6+1:02d}.jpg',quality=93)
    allpaths += [str(p.relative_to(ROOT)) for p in DEST.iterdir() if p.is_file()]
    allpaths += [str(p.relative_to(ROOT)) for p in Path(__file__).parent.iterdir() if p.is_file() and p.suffix in ['.py','.cjs','.md']]
    write(review/'public-paths.json',json.dumps(sorted(set(allpaths)),ensure_ascii=False,indent=2))
    print(json.dumps({'lessons':len(DATA['lessons']),'diagrams':len(items),'asset_files':len(items)*3,'contact_pages':(len(items)+5)//6},ensure_ascii=False))

if __name__=='__main__':main()
