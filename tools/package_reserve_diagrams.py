#!/usr/bin/env python3
"""Package the already-rendered Reserve Forces Act diagrams and review ledger."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reserve-forces-act'
DATA=BASE/'diagrams'

def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def verify_artifacts(manifest, audit, source):
    """Check the exact rendered inputs before writing any completion records."""
    expected_ids=[f'RL-{n:03d}' for n in range(1,35)]
    lessons=manifest['lessons']
    if [l['lessonId'] for l in lessons]!=expected_ids:
        raise ValueError('Incomplete or misordered 34-lesson manifest')
    if [l['lessonId'] for l in source['lessons']]!=expected_ids:
        raise ValueError('Incomplete or misordered source index')
    count=sum(len(l['diagrams']) for l in lessons)
    if manifest.get('lessonCount')!=34 or manifest.get('diagramCount')!=count:
        raise ValueError('Manifest counts do not match its contents')
    if manifest.get('exam')!='80' or source.get('exam')!='80':
        raise ValueError('Unexpected exam version')
    if (audit.get('rasterized') is not True or audit.get('failures')
            or audit.get('overflowCount')!=0 or audit.get('overlapCount')!=0
            or audit.get('renderedLessons')!=34 or audit.get('renderedDiagrams')!=count):
        raise ValueError('A complete, successful SVG and PNG render is required')
    if json.loads((DATA/'review/render-errors.json').read_text()):
        raise ValueError('Unresolved render errors')
    if manifest.get('canvas')!={'width':1600,'height':900} or audit.get('pngDimensions')!=[1600,900]:
        raise ValueError('Unexpected canvas dimensions')
    paths=set()
    text_boxes=0
    for lesson,original in zip(lessons,source['lessons']):
        lesson_id=lesson['lessonId']
        if lesson['source']!=original:
            raise ValueError('Source mapping is stale: '+lesson_id)
        content_path=ROOT/lesson['contentPath']
        raw=content_path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=lesson['contentSha256']:
            raise ValueError('Rendered content is stale: '+lesson_id)
        content=json.loads(raw)
        diagrams=lesson['diagrams']
        if not diagrams or [d['id'] for d in diagrams]!=[d['id'] for d in content['diagrams']]:
            raise ValueError('Rendered diagram order is stale: '+lesson_id)
        if len({d['id'] for d in diagrams})!=len(diagrams):
            raise ValueError('Duplicate diagram IDs: '+lesson_id)
        if content['review'].get('issues') or not content['review'].get('scriptReadInFull'):
            raise ValueError('Unresolved content review: '+lesson_id)
        for number,(diagram,authored) in enumerate(zip(diagrams,content['diagrams']),1):
            for field in ('title','kind','sourceRanges'):
                if diagram.get(field)!=authored.get(field):
                    raise ValueError('Rendered metadata is stale: '+lesson_id+'/'+diagram['id'])
            geometry=diagram['geometry']
            if geometry.get('overflow')!=0 or geometry.get('overlap')!=0:
                raise ValueError('Unresolved layout errors: '+lesson_id+'/'+diagram['id'])
            text_boxes+=geometry['textBoxes']
            for extension in ('svg','png'):
                relative=diagram[extension]
                expected=f"reserve-forces-act/lesson-{lesson_id[3:]}/diagrams/rl-{lesson_id[3:]}-{number:02d}-{diagram['id']}.{extension}"
                if relative!=expected or relative in paths:
                    raise ValueError('Unexpected or duplicate asset path: '+relative)
                paths.add(relative)
                asset=ROOT/relative
                if not asset.is_file():
                    raise ValueError('Missing asset: '+relative)
                data=asset.read_bytes()
                if hashlib.sha256(data).hexdigest()!=diagram.get(extension+'Sha256'):
                    raise ValueError('Asset checksum mismatch: '+relative)
                if extension=='png':
                    if (len(data)<33 or data[:8]!=b'\x89PNG\r\n\x1a\n'
                            or data[12:16]!=b'IHDR' or struct.unpack('>II',data[16:24])!=(1600,900)
                            or len(data)!=diagram.get('pngBytes')):
                        raise ValueError('Invalid PNG or dimensions: '+relative)
    if text_boxes!=audit.get('textBoundsChecked'):
        raise ValueError('Layout audit does not match the rendered diagrams')
    return {'algorithm':'sha256','verifiedSvg':count,'verifiedPng':count,
            'verifiedContentFiles':len(lessons),'mismatches':0,
            'checkedBeforeWritingCompletionRecords':True}

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
        if d.get('issues'):
            raise ValueError('Unresolved independent review: '+d['file'])
        for l in d.get('lessons',[]):
            if isinstance(l,dict) and l.get('status') in ['pass','passed','resolved']:
                p=DATA/'content'/f"{l['lessonId']}.json"
                if hashlib.sha256(p.read_bytes()).hexdigest()!=l.get('contentSha256'):
                    raise ValueError('Independent review is stale: '+l['lessonId'])
                reviewed.add(l['lessonId'])
    integrity=verify_artifacts(manifest,audit,source)
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
    audit['artifactIntegrity']=integrity
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
      '- [강의 제작 도구에 연결하는 방법](diagrams/INTEGRATION.md)',
      '- [파일 무결성·완료 판정 검증](diagrams/review/packaging-check.json)',
      '- [디자인 기준과 복구 기록](diagrams/DESIGN-REVIEW.md)','',
      '## 열람과 검색','',
      '저장소를 내려받아 압축을 풀고, 폴더 구조를 유지한 채 `reserve-forces-act/diagrams/gallery.html`을 브라우저로 엽니다. HTML 파일만 따로 옮기면 상대 경로로 연결된 이미지가 표시되지 않습니다.','',
      '검색은 제목과 도식 화면에 표시된 본문을 함께 찾습니다. `6시간`, `관혼상제`, `7강`, `7강 관혼상제`처럼 입력할 수 있습니다. `7강`은 17강·27강을 포함하지 않습니다. 강의 선택 메뉴와 검색어는 함께 적용되며, 전체를 보려면 검색어를 지우고 전체 강의를 선택합니다.','',
      'SVG·PNG 버튼은 원본 파일을 엽니다. 오프라인 브라우저에서 자동 다운로드 대신 이미지가 열리면 브라우저의 저장 기능을 사용합니다.','',
      '## 강의별 목록','', '| 강의 | 범위 | 도식 수 |','| --- | --- | ---: |',*rows,'',
      '## 확인 범위','',
      '각 강의는 기존 스크립트 전체를 읽어 작성했으며, 각 도식에는 해당 명제를 뒷받침하는 원고 줄번호와 주제 연결을 기록했습니다. 도식의 자동 배치 검사, 원고 대조, 별도의 교차검수는 구분하여 기록합니다. 법령을 독립적으로 최신 검증하거나 학습 사이트·동영상 삽입까지 마쳤다는 뜻은 아닙니다.','',
      '출처 스크립트 전체와 음원은 공개 폴더에 포함하지 않았습니다. 기존 장면 사진은 그대로 두었습니다.','',
      '## 재생성','', '아래 명령은 저장소 루트에서 실행합니다. Python 3, Pillow, Inkscape가 필요합니다. 현재 렌더러는 Linux의 `/usr/share/fonts/opentype/noto/`에서 `NotoSansCJK-Regular.ttc`와 `NotoSansCJK-Bold.ttc`를 읽습니다. 다른 환경에서는 같은 글꼴 파일을 준비하고 렌더러의 `FONT_DIR`을 설치 위치에 맞춥니다.','',
      '```bash','python tools/render_reserve_diagrams.py --source-root /path/to/private/source-checkout --workers 4','python tools/audit_reserve_content.py --source-root /path/to/private/source-checkout','python tools/package_reserve_diagrams.py','```','',
      '패키징은 34강의 연결·내용 해시·렌더 상태와 SVG/PNG 670개 파일의 SHA256을 먼저 확인합니다. 손상된 파일, 이전 PNG가 남은 SVG 전용 렌더, 누락된 이미지 해시는 완료 기록을 쓰기 전에 차단합니다. 원고 내용을 수정했다면 독립 내용검수 기록도 해당 내용 해시에 맞춰 갱신해야 합니다.','',
      '갤러리를 수정한 경우 Node.js, Playwright와 Chromium을 준비한 후 `node tools/check_reserve_gallery.cjs`로 실제 검색·필터·모바일 동작을 확인합니다. 별도 Chromium 실행 파일을 사용할 때는 `RESERVE_DIAGRAM_CHROMIUM`에 그 경로를 지정합니다.','',
      '원고 경로는 해당 비공개 저장소 체크아웃 안의 `docs/merged-lectures/예비군법/*.txt`입니다. 원고 해시가 달라지면 렌더러가 중단하므로 원고 변경을 먼저 검토하고 출처 기록을 갱신해야 합니다. 공개 콘텐츠만으로 다시 렌더하려면 `--source-root`를 생략할 수 있으나 출처 대조는 미실시로 기록됩니다.','']
    (BASE/'README.md').write_text('\n'.join(readme))
    print(json.dumps({'lessons':len(jobs),'diagrams':manifest['diagramCount'],'independentlyReviewedLessons':len(reviewed),'sourceNotes':len(notes),'missingAssets':len(missing)},ensure_ascii=False))

if __name__=='__main__':main()
