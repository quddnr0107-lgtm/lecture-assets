#!/usr/bin/env python3
"""Render approved Exam 80 content in independent lesson workers."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from PIL import Image
import json, hashlib, os, subprocess
import build_mobile as b
ROOT=b.ROOT
SUB=b.SUB
P=SUB/'production-queue'
N=SUB/'notion-v1'
def load(p): return json.loads(p.read_text())
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(x): return hashlib.sha256(x).hexdigest()
def content_hash(d): return sha(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def verify_file(f,ext):
    p=ROOT/f['path']; raw=p.read_bytes()
    assert len(raw)==f['bytes'] and sha(raw)==f['sha256'],str(p)
    if ext!='svg':
        with Image.open(p) as im:
            assert im.size==(f['width'],f['height']),str(p)
            im.verify()
def render_lesson(l):
    records=[]
    for d in l['diagrams']:
        title,subtitle,pages,start=b.paginate(l,d)
        ident=f"{l['lecture_id']}-{d['id']}"
        for i in range(1,len(pages)+1):
            out=SUB/f'lesson-{l["lesson"]:03d}'/'diagrams/notion-v1/mobile'/f'{ident}-M{i:02d}'
            rec=b.build_page(l,d,(title,subtitle),pages,i,start,out)
            for ext,f in rec['files'].items():verify_file(f,ext)
            rec['exam_number']=80
            rec['diagram_content_sha256']=content_hash(d)
            records.append(rec)
    return records
def main():
    req=load(P/'render-request.json'); q=load(P/'queue.json')
    assert req['exam_number']==80
    if req.get('mode') == 'final-audit-package':
        from final_exam80_audit import main as final_audit
        return final_audit(req)
    # Validate only the requested lesson leases, not unrelated jobs.
    from datetime import datetime, timezone
    requested = set(req['lessons'])
    assert requested and len(requested) == len(req['lessons'])
    assert 1 <= req['worker_limit'] <= 3
    claimed = {j['lesson']: j for j in q['jobs']
               if j['kind'] == 'lesson_mobile_reflow' and j['lesson'] in requested}
    assert set(claimed) == requested
    for n, job in claimed.items():
        lease = job.get('lease') or {}
        assert job['status'] in ('running', 'reserved'), f'{n}: not reserved'
        assert lease.get('run_id') == req['run_id'], f'{n}: wrong lease owner'
        assert datetime.fromisoformat(lease['expires_at'].replace('Z','+00:00')) > datetime.now(timezone.utc), f'{n}: expired lease'
    if req.get('mode') == 'desktop-mobile-script-repair':
        from repair_exam80_11 import repair
        repair(req)
    source=load(P/'EXAM80-SCRIPT-SOURCE.json'); align=load(N/'script-alignment.json')
    data=load(N/'content.json'); desktop=load(N/'manifest.json')
    assert source['exam_number']==align['exam_number']==80 and source['script_source_commit']==req['source_commit']
    source_map={x['lecture_id']:x for x in source['lessons']}
    aligned={x['diagram_id']:x for x in align['items']}
    desktop_map={x['id']:x for x in desktop['items']}
    failures={}; ready=[]
    for l in data['lessons']:
        try:
            for d in l['diagrams']:
                ident=l['lecture_id']+'-'+d['id']
                a=aligned[ident]
                assert a['status']=='matched_existing_script'
                assert a['script_sha256']==source_map[l['lecture_id']]['script_sha256']
                assert a['diagram_content_sha256']==content_hash(d),ident+' content hash mismatch'
                for ext,f in desktop_map[ident]['files'].items():verify_file(f,ext)
            ready.append(l)
        except Exception as e:failures[str(l['lesson'])]='source/desktop validation: '+str(e)
    mp=N/'mobile-manifest.json'
    old=load(mp) if mp.exists() else {'items':[]}
    successful={}
    with ProcessPoolExecutor(max_workers=min(req['worker_limit'],os.cpu_count() or 1)) as pool:
        futures={pool.submit(render_lesson,l):l for l in ready if l['lesson'] in req['lessons']}
        for f in as_completed(futures):
            l=futures[f]
            try:
                records=f.result()
                for r in records:r['script_sha256']=source_map[l['lecture_id']]['script_sha256']
                successful[l['lesson']]=records
            except Exception as e: failures[str(l['lesson'])]='render: '+str(e)
    for l in data['lessons']:
        n=l['lesson']
        if n not in successful:
            # Do not publish partial output from failed workers.
            d=SUB/f'lesson-{n:03d}'/'diagrams/notion-v1/mobile'
            rel=str(d.relative_to(ROOT))
            subprocess.run(['git','restore','--worktree','--',rel],cwd=ROOT,check=False,capture_output=True)
            subprocess.run(['git','clean','-fd','--',rel],cwd=ROOT,check=True,capture_output=True)
    records=[r for r in old['items'] if r['lesson'] not in successful]
    for rr in successful.values():records.extend(rr)
    # Remove only old, manifest-owned mobile files for successful lessons.
    keep = {f['path'] for rec in records for f in rec['files'].values()}
    for rec in old['items']:
        if rec['lesson'] in successful:
            for f in rec['files'].values():
                path = f['path']
                expected = f"integrated-defense/lesson-{rec['lesson']:03d}/diagrams/notion-v1/mobile/"
                if path.startswith(expected) and path not in keep:
                    (ROOT/path).unlink(missing_ok=True)
    records.sort(key=lambda r:(r['source_id'],r['page']))
    save(mp,{'schema_version':1,'style':'07-notion-editorial','exam_number':80,'width':b.W,'height':b.H,'items':records})
    for n,rr in successful.items():
        d=SUB/f'lesson-{n:03d}'/'diagrams/notion-v1/mobile'
        rows=[f'# {n}강 모바일 도식 · 제80회','','| 원본 도식 | 페이지 | PNG | SVG | WebP |','|---|---:|---|---|---|']
        for r in rr:
            link=lambda ext:'['+ext.upper()+']('+Path(r['files'][ext]['path']).name+')'
            rows.append('| '+r['source_id']+' | '+str(r['page'])+'/'+str(r['page_count'])+' | '+link('png')+' | '+link('svg')+' | '+link('webp')+' |')
        (d/'README.md').write_text('\n'.join(rows)+'\n')
    # Verification report is deliberately separate from human visual acceptance.
    report={'run_id':req['run_id'],'exam_number':80,'source_commit':source['script_source_commit'],'input_commit':os.environ.get('GITHUB_SHA'),'desktop_verified_lessons':[l['lesson'] for l in ready],'rendered_lessons':sorted(successful),'rendered_pages':sum(map(len,successful.values())),'failures':failures,'visual_review':'pending','status':'rendered_pending_visual','files':[r for rr in successful.values() for r in rr]}
    save(P/'runs'/(req['run_id']+'.json'),report)
    # Mark only rendered outputs awaiting independent image review, never done.
    for j in q['jobs']:
        if (j.get('lease') or {}).get('run_id')!=req['run_id']:continue
        n=j.get('lesson')
        if j['kind']=='lesson_mobile_reflow':
            j['status']='rendered_pending_visual' if n in successful else 'queued'
        elif j['kind']=='supplement_diagram':
            j['status']='rendered_pending_visual' if n in report['desktop_verified_lessons'] else 'queued'
        else:j['status']='rendered_pending_visual' if successful else 'queued'
        j['lease']=None
    q['status']='review_pending'
    q['last_render_run']=req['run_id']
    q['progress']['mobile_rendered_pages']=len(records)
    q['progress']['mobile_rendered_lessons']=len({r['lesson'] for r in records})
    # Rebuild the complete index from the manifest and queue; never patch a potentially truncated index.
    index=N/'mobile-index.md'
    rows=['# 제80회 통합방위법 모바일 도식','','기존 제80회 강의 스크립트 기준. 생성 완료 목록이며 최종 검수 상태는 작업 큐를 따른다.','','[모바일 파일·해시 목록](mobile-manifest.json) · [작업 상태](../production-queue/queue.json)','','| 강의 | 페이지 | 검수 상태 |','|---|---:|---|']
    jobs={j['lesson']:j for j in q['jobs'] if j['kind']=='lesson_mobile_reflow'}
    for l in data['lessons']:
        n=l['lesson']
        count=sum(r['lesson']==n for r in records)
        status='완료' if jobs[n]['status']=='done' else ('시각 재검수 대기' if count else '제작 대기')
        rows.append(f'| [{n:02d}강](../lesson-{n:03d}/diagrams/notion-v1/mobile/) | {count} | {status} |')
    index.write_text('\n'.join(rows)+'\n')
    save(P/'queue.json',q)
    print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))
if __name__=='__main__':main()
