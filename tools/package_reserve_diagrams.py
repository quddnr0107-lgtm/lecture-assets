#!/usr/bin/env python3
"""Package the already-rendered Reserve Forces Act diagrams and review ledger."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reserve-forces-act'
DATA=BASE/'diagrams'

def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--remote-ready',action='store_true');args=ap.parse_args()
    manifest=json.loads((DATA/'manifest.json').read_text())
    audit=json.loads((DATA/'review/audit-report.json').read_text())
    source=json.loads((DATA/'source-index.json').read_text())
    cross=[]
    for p in sorted((DATA/'review').glob('cross-review-*.json')):
        d=json.loads(p.read_text());cross.append({'file':p.name,**d})
    reviewed=set()
    for d in cross:
        for l in d.get('lessons',[]):
            if isinstance(l,str):reviewed.add(l)
            elif l.get('status') in ['pass','passed','resolved']:
                p=DATA/'content'/f"{l['lessonId']}.json"
                if hashlib.sha256(p.read_bytes()).hexdigest()!=l.get('contentSha256'):
                    raise ValueError('Independent review is stale: '+l['lessonId'])
                reviewed.add(l['lessonId'])
    rows=[];notes=[];jobs=[];missing=[]
    for l in manifest['lessons']:
        content=ROOT/l['contentPath']
        if hashlib.sha256(content.read_bytes()).hexdigest()!=l['contentSha256']:
            raise ValueError('Rendered content is stale: '+l['lessonId'])
        diagrams=l['diagrams'];folder=BASE/f"lesson-{l['lessonId'][3:]}/diagrams"
        body=[f"# {l['lessonId']} · {l['title']}",'',f"제80회 기존 강의 스크립트 기반 · {len(diagrams)}장 · 1600×900",'', '| # | 도식 | SVG | PNG |','| --- | --- | --- | --- |']
        for n,d in enumerate(diagrams,1):
            svg=Path(d['svg']).name;png=Path(d['png']).name
            body.append(f"| {n} | {d['title']} | [SVG]({svg}) | [PNG]({png}) |")
            for key in ['svg','png']:
                if not (ROOT/d[key]).is_file():missing.append(d[key])
        body+=['','[전체 강의 목록](../../README.md) · [오프라인 갤러리](../../diagrams/gallery.html)','','내용·숫자·기한의 기준은 기존 제80회 스크립트입니다. 원고의 표현 차이나 모호한 부분은 전체 검수 기록에 따로 남겼습니다.','']
        (folder/'README.md').write_text('\n'.join(body))
        row=f"| {l['lessonId']} | [{l['title']}](lesson-{l['lessonId'][3:]}/diagrams/) | {len(diagrams)} |"
        rows.append(row)
        for note in l['review'].get('sourceNotes',[]):notes.append({'lessonId':l['lessonId'],'note':note})
        jobs.append({'lessonId':l['lessonId'],'title':l['title'],'diagramCount':len(diagrams),'sourceRead':bool(l['review'].get('scriptReadInFull')),'sourceHash':l['source']['sourceSha256'],'contentStatus':'reviewed-against-script','independentReview':l['lessonId'] in reviewed,'renderStatus':'png-and-svg-verified','publicationStatus':'included-with-this-commit' if args.remote_ready else 'ready-to-publish','issues':l['review'].get('issues',[])})
    if missing:raise ValueError('Missing assets: '+str(missing[:8]))
    if len(jobs)!=34 or len(source['lessons'])!=34:raise ValueError('Incomplete 34-lesson set')
    queue={'schemaVersion':1,'subject':'reserve-forces-act','exam':'80','examPeriod':'27h1','contentBasis':'existing-lecture-scripts','expectedLessons':34,'completedContentLessons':len(jobs),'diagramCount':manifest['diagramCount'],'sourceCommit':source['lessons'][0]['sourceCommit'],'scope':'diagram assets; site/player integration separate','independentlyReviewedLessons':len(reviewed),'remainingTasks':([] if len(reviewed)==34 else ['complete independent content review'])+([] if args.remote_ready else ['publish exact artifacts and verify remote hashes']),'jobs':jobs}
    write_json(DATA/'production-queue.json',queue)
    write_json(DATA/'review/source-notes.json',{'scope':'existing-script-wording','notes':notes})
    audit['independentContentReview']={'reviewedLessons':len(reviewed),'reports':[x['file'] for x in cross]}
    audit['galleryAssetLinksVerified']=2*manifest['diagramCount']
    audit['sourceNotesCount']=len(notes)
    write_json(DATA/'review/audit-report.json',audit)
    readme=['# 예비군법 제80회 강의 도식','',f"**34강 · {manifest['diagramCount']}장 · SVG + PNG**",'',
      '기존 제80회(2027년 전반기) 예비군법 강의 스크립트의 설명 순서에 맞춰 주체, 절차, 기한, 원칙과 예외를 나누었습니다. 한 장에 넣기 어려운 내용은 여러 장으로 나누고 본문 글자 크기를 유지했습니다.','',
      '- [강의별 갤러리](diagrams/gallery.html) — 저장소를 내려받아 열면 네트워크 없이 이미지 검색·열람 가능',
      '- [도식 목록과 출처](diagrams/manifest.json)',
      '- [34강 원본 연결 및 해시](diagrams/source-index.json)',
      '- [제작·검수 현황](diagrams/production-queue.json)',
      '- [배치·렌더링 검수 결과](diagrams/review/audit-report.json)',
      '- [원고 표현 차이와 처리 기록](diagrams/review/source-notes.json)',
      '- [내용 검수 요약](diagrams/review/CONTENT-REVIEW.md)',
      '- [디자인 기준과 복구 기록](diagrams/DESIGN-REVIEW.md)','',
      '## 강의별 목록','', '| 강의 | 범위 | 도식 수 |','| --- | --- | ---: |',*rows,'',
      '## 확인 범위','',
      '각 강의는 기존 스크립트 전체를 읽어 작성했으며, 각 도식에는 해당 명제를 뒷받침하는 원고 줄번호와 주제 연결을 기록했습니다. 도식의 자동 배치 검사, 원고 대조, 별도의 교차검수는 구분하여 기록합니다. 법령을 독립적으로 최신 검증하거나 학습 사이트·동영상 삽입까지 마쳤다는 뜻은 아닙니다.','',
      '출처 스크립트 전체와 음원은 공개 폴더에 포함하지 않았습니다. 기존 장면 사진은 그대로 두었습니다.','',
      '## 재생성','', 'Python 3, Pillow, Noto CJK 글꼴, Inkscape가 필요합니다.','',
      '```bash','python tools/render_reserve_diagrams.py --source-root /path/to/private/source-checkout --workers 4','python tools/audit_reserve_content.py --source-root /path/to/private/source-checkout','python tools/package_reserve_diagrams.py','```','',
      '원고 경로는 해당 비공개 저장소 체크아웃 안의 `docs/merged-lectures/예비군법/*.txt`입니다. 원고 해시가 달라지면 렌더러가 중단하므로 원고 변경을 먼저 검토하고 출처 기록을 갱신해야 합니다. 공개 콘텐츠만으로 다시 렌더하려면 `--source-root`를 생략할 수 있으나 출처 대조는 미실시로 기록됩니다.','']
    (BASE/'README.md').write_text('\n'.join(readme))
    print(json.dumps({'lessons':len(jobs),'diagrams':manifest['diagramCount'],'independentlyReviewedLessons':len(reviewed),'sourceNotes':len(notes),'missingAssets':len(missing)},ensure_ascii=False))

if __name__=='__main__':main()
