#!/usr/bin/env python3
"""Create the public catalog, per-lesson index and provenance for rendered diagrams."""
from __future__ import annotations
import argparse, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATE='2026-11-27'
STYLE='integrated-defense/lesson-005/diagrams/style-studies-v2/07-notion-editorial.svg'

def save(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--content',nargs='+',required=True,type=Path)
    p.add_argument('--official',required=True,type=Path)
    p.add_argument('--catalog',required=True,type=Path)
    args=p.parse_args()
    subject=ROOT/'defense-directives'
    out=subject/'diagrams'
    official=json.loads(args.official.read_text())
    raw=[]
    for f in args.content:raw.extend(json.loads(f.read_text()))
    raw.sort(key=lambda x:x['lessonId'])
    catalog=next(c for c in json.loads(args.catalog.read_text())['courses'] if c['id']=='DR')
    lessons={l['id']:l for l in catalog['lessons']}
    records=json.loads((out/'rendered-records.json').read_text())
    counts=Counter(r['lessonId'] for r in records)
    if set(counts)!=set(lessons):
        raise ValueError(f'Lesson coverage mismatch: {set(lessons)-set(counts)} / {set(counts)-set(lessons)}')
    docs=[{k:v for k,v in d.items() if k not in ['file']} for d in official['documents']]
    sources=[]
    for row in raw:
        row=dict(row)
        art=official['articles'][row['articleKey']]
        row.update({'sourceUrl':art['sourceUrl'],'sourceVersion':art['version'],'effectiveDate':art['effective']})
        sources.append(row)
    save(out/'diagrams.source.json',{'schema_version':1,'subject':'defense-directives','created_date_kst':DATE,'style_reference':STYLE,'law_versions':docs,'diagrams':sources})
    by_lesson=defaultdict(list)
    items=[]
    for rec in records:
        art=official['articles'][rec['articleKey']]
        files={}
        for ext,rel in rec['files'].items():
            f=subject/rel
            b=f.read_bytes()
            files[ext]={'path':str(f.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
        item={'id':rec['id'],'lecture_id':rec['lessonId'],'lesson_number':int(rec['lessonId'].split('-')[1]),'title':rec['title'],'article':rec['sourceArticle'],'article_key':rec['articleKey'],'source_clauses':rec['sourceClauses'],'source_url':art['sourceUrl'],'source_version':art['version'],'effective_date':art['effective'],'note':rec.get('note',''),'width':1600,'height':1120,'body_font_size':rec['bodyFontSize'],'files':files}
        if 'continuation' in rec:item['continuation']=rec['continuation']
        items.append(item);by_lesson[rec['lessonId']].append(item)
    manifest={'schema_version':1,'subject':'defense-directives','subject_name':'훈령','created_date_kst':DATE,'status':'ready_for_lesson_integration','style':{'name':'editorial-monochrome','reference':STYLE,'background':'#FFFEFC','ink':'#25241F','canvas':[1600,1120]},'coverage':{'expected_lessons':len(lessons),'included_lessons':len(counts),'diagrams':len(items),'missing_lessons':[]},'law_versions':docs,'lessons':[{'id':lid,'title':l['title'],'diagram_count':counts[lid],'diagram_ids':[i['id'] for i in by_lesson[lid]],'path':f'defense-directives/lesson-{lid.split("-")[1]}/diagrams/'} for lid,l in lessons.items()],'items':items}
    save(subject/'diagrams-manifest.json',manifest)
    for lid,l in lessons.items():
        folder=subject/f'lesson-{lid.split("-")[1]}'/'diagrams'
        rows=by_lesson[lid]
        md=[f'# {lid} · {l["title"]}', '',f'도식 **{len(rows)}장** · 1600 × 1120 · 흑백 편집형 디자인','', '[훈령 전체 목록](../../README.md) · [전체 매니페스트](../../diagrams-manifest.json)','']
        for item in rows:
            stem=Path(item['files']['webp']['path']).stem
            md += [f'## {item["id"]} · {item["title"]}','','[WebP]('+stem+'.webp) · [PNG]('+stem+'.png) · [SVG 원본]('+stem+'.svg)','',f'![{item["title"]}]({stem}.webp)','',f'근거: [{item["article"]}]({item["source_url"]}) · {item["source_version"]}']
            if item['note']:md += ['',item['note']]
            md += ['']
        (folder/'README.md').write_text('\n'.join(md))
    total_bytes={ext:sum(i['files'][ext]['bytes'] for i in items) for ext in ['svg','png','webp']}
    md=['# 훈령 강의 도식','','**78강 전체 · '+str(len(items))+'장**. 무한회독 강의용 도식입니다. 사용자가 선택한 흰 종이 바탕, 검은 글자, 얇은 구분선, 손으로 그은 괄호와 동그라미 디자인을 적용했습니다.','','## 바로 보기','','- [DR-002 조직과 편성](lesson-002/diagrams/)','- [DR-012 중기·연도·수시 계획](lesson-012/diagrams/)','- [DR-034 보급지원계통](lesson-034/diagrams/)','- [DR-050 예비군훈련 체계](lesson-050/diagrams/)','- [DR-060 기타훈련](lesson-060/diagrams/)','- [DR-078 보류 해소와 관리](lesson-078/diagrams/)','','## 파일 형식','','| 형식 | 용도 | 전체 용량 |','|---|---|---:|']
    for ext,desc in [('webp','사이트·강의 화면 삽입 / 무손실 압축'),('png','영상 편집·발표 자료 삽입'),('svg','확대·문구 편집용 벡터 원본')]:
        md.append(f'| {ext.upper()} | {desc} | {total_bytes[ext]/1024/1024:.2f} MiB |')
    md += ['','모든 도식은 1600 × 1120 비율입니다. SVG의 지정 서체는 Noto Sans CJK KR이며, PNG·WebP에는 글자가 이미지로 고정되어 있습니다.','','## 원문 기준','','2026-11-27 확인한 공식 원문을 바탕으로 제작했습니다.']
    for d in docs:md.append(f'- [{d["name"]}]({d["sourceUrl"]}): {d["version"]}, 시행 {d["effective"]}')
    md += ['','교육훈련 제16조제4항제4호는 **2027-01-01 시행**이며 해당 도식에 별도 표기했습니다. 공식 시험 공고상의 출제 범위 확정을 의미하지는 않습니다.','','## 강의별 목록','','| 강의 | 제목 | 도식 |','|---|---|---:|']
    for lid,l in lessons.items():
        title=l['title'].split(', ',1)[-1]
        md.append(f'| [{lid}](lesson-{lid.split("-")[1]}/diagrams/) | {title} | {counts[lid]}장 |')
    md += ['','## 관리 자료','','- [전체 매니페스트](diagrams-manifest.json): 강의·조문·파일 경로·SHA-256','- [도식 원고와 근거](diagrams/diagrams.source.json): 편집·재생성용 구조화 원본','- [레이아웃 검사](diagrams/layout-qa.json): 모든 도식의 영역·텍스트 겹침 검사','- [검수 기록](diagrams/QA.md)','','이 폴더는 도식 자료입니다. 강의 재생 시점과 화면 배치는 매니페스트의 `lecture_id`로 연결할 수 있습니다.','']
    (subject/'README.md').write_text('\n'.join(md))
    (out/'README.md').write_text('# 훈령 도식 제작 원본\n\n[78강 전체 목록](../README.md)에서 강의별 이미지를 볼 수 있습니다.\n\n`diagrams.source.json`은 원고·조문 근거, `layout-qa.json`은 렌더링 검사 결과입니다.\n\n## 다시 만들기\n\n저장소 루트에서 Python 3, Pillow, Inkscape 및 Noto Sans CJK 서체가 설치된 환경을 사용합니다.\n\n```bash\npython tools/render_directive_diagrams.py defense-directives/diagrams/diagrams.source.json\n```\n')
    print(json.dumps({'lessons':len(counts),'diagrams':len(items),'totalBytes':total_bytes},ensure_ascii=False))

if __name__=='__main__':main()
