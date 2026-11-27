#!/usr/bin/env python3
"""Render a script-bound supplement request without regenerating unrelated diagrams."""
import copy, hashlib, json, re
from pathlib import Path
from PIL import Image, ImageChops
from render_directive_diagrams import paginate, render_slide, check_boxes, rasterize
root=Path(__file__).resolve().parents[1]
subject=root/'defense-directives'
d=subject/'diagrams'
def load(p): return json.loads(p.read_text())
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
req=load(d/'targeted-render-request.json')
q=load(d/'production-queue.json')
s=load(d/'diagrams.source.json')
m=load(subject/'diagrams-manifest.json')
b=load(d/'script-basis.json')
qa=load(d/'script-alignment-qa.json')
assert req['exam']==80 and b['exam']['number']==80
assert q['state']['active_run']['id']==req['run_id']
lid=req['lesson_id']
binding=next(x for x in b['lessons'] if x['lesson_id']==lid)
assert binding['source_git_blob']==req['expected_source_blob']
assert binding['source_sha256']==req['expected_script_sha256']
lesson=next(x for x in m['lessons'] if x['id']==lid)
folder=root/lesson['path']
assert max(int(re.search(r'-D(\d+)',x).group(1)) for x in lesson['diagram_ids'])==req['existing_max']
assert set(p.stem.split('-editorial')[0] for p in folder.glob('*.svg'))==set(lesson['diagram_ids'])
new=[]; records=[]
for entry in req['items']:
    did=entry['id']; source=entry['slide']
    assert source['lessonId']==lid and source['scriptEvidence']['source_sha256']==binding['source_sha256']
    assert did not in lesson['diagram_ids']
    assert not any(x['lessonId']==lid and x['title']==source['title'] for x in s['diagrams'])
    slides=paginate(copy.deepcopy(source))
    assert len(slides)==1, f'{did}: needs explicit pagination review'
    slide=slides[0]
    svg,boxes=render_slide(slide,did)
    errors=check_boxes(boxes,did)
    assert not errors,errors
    paths={ext:folder/f'{did}-editorial-v1.{ext}' for ext in ('svg','png','webp')}
    assert not any(p.exists() for p in paths.values())
    paths['svg'].write_text(svg)
    rasterize((paths['svg'],paths['png'],paths['webp']))
    with Image.open(paths['png']) as a,Image.open(paths['webp']) as w:
        assert a.size==w.size==(1600,1120)
        assert ImageChops.difference(a.convert('RGB'),w.convert('RGB')).getbbox() is None
    files={k:{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in paths.items()}
    row={'id':did,'lecture_id':lid,'lesson_number':int(lid.split('-')[1]),'title':source['title'],'article':source['sourceArticle'],'article_key':source['articleKey'],'source_clauses':source['sourceClauses'],'source_url':source['sourceUrl'],'source_version':source['sourceVersion'],'effective_date':source['effectiveDate'],'note':source.get('note',''),'width':1600,'height':1120,'body_font_size':slide['_bodySize'],'files':files,'script_ref':lid,'script_evidence':source['scriptEvidence']}
    new.append(row);s['diagrams'].append(source)
    job=next(x for x in q['production_jobs'] if x['id']==entry['job_id'])
    assert job['claimed_by']==req['run_id'] and job['status']=='running'
    job.update({'status':'qa','outputs':list(files.values()),'diagram_id':did,'layout_errors':[],'png_webp_pixel_equal':True,'visual_review':'pending','claimed_by':None,'claimed_at':None,'lease_expires_at':None})
    records.append({'id':did,'script_evidence':source['scriptEvidence'],'layout_errors':[],'png_webp_pixel_equal':True,'visual_review':'pending','files':files,'text_boxes':boxes})
m['items'].extend(new);m['items'].sort(key=lambda x:x['id'])
s['diagrams'].sort(key=lambda x:x['lessonId'])
lesson['diagram_ids'].extend(row['id'] for row in new);lesson['diagram_count']=len(lesson['diagram_ids'])
m['coverage']['diagrams']=len(m['items'])
m['status']='exam80_script_alignment_in_progress'
j=next(x for x in q['jobs'] if x['lesson_id']==lid)
j.update({'status':'queued','claimed_by':None,'claimed_at':None,'lease_expires_at':None,'existing_diagram_count':lesson['diagram_count'],'existing_diagram_ids':lesson['diagram_ids'],'result':{'scope':'기존 원고 전문·D01 비교; 신규 3장 렌더 완료, 시각 검수 대기','source_sha256':binding['source_sha256']}})
q['state'].update({'active_run':None,'coverage_reviews_queued':sum(x['status']=='queued' for x in q['jobs']),'coverage_reviews_completed':sum(x['status']=='completed' for x in q['jobs']),'production_jobs_queued':sum(x['status']=='queued' for x in q['production_jobs']),'production_jobs_qa':sum(x['status']=='qa' for x in q['production_jobs']),'diagrams_added_after_baseline':len(m['items'])-q['baseline']['diagrams']})
q['runs'].append({'id':req['run_id'],'status':'rendered_pending_visual_qa','new_diagrams':len(new),'completed_reviews':1,'diagram_ids':[x['id'] for x in new]})
qa.setdefault('targeted_render_runs',[]).append({'run_id':req['run_id'],'lesson_id':lid,'records':records})
qa['full_lecture_coverage_reviews_completed']=q['state']['coverage_reviews_completed']
qa['remaining_full_lecture_reviews']=len(q['jobs'])-q['state']['coverage_reviews_completed']
qa['new_diagrams']=q['state']['diagrams_added_after_baseline']
layout=load(d/'layout-qa.json')
layout['diagrams']=len(m['items'])
layout.setdefault('lessonCounts',{})[lid]=lesson['diagram_count']
layout.setdefault('targeted_runs',[]).append({'run_id':req['run_id'],'ids':[x['id'] for x in new],'errors':[]})
content=load(d/'content-qa.json')
content.setdefault('script_targeted_runs',[]).append({'run_id':req['run_id'],'ids':[x['id'] for x in new],'script_sha256':binding['source_sha256'],'status':'content_checked_rendered_visual_pending'})
for path,data in [(d/'diagrams.source.json',s),(subject/'diagrams-manifest.json',m),(d/'production-queue.json',q),(d/'script-alignment-qa.json',qa),(d/'layout-qa.json',layout),(d/'content-qa.json',content)]:save(path,data)
rows=[x for x in m['items'] if x['lecture_id']==lid]
md=[f'# {lid} · {lesson["title"]}','',f'도식 **{len(rows)}장** · 1600 × 1120 · 흑백 편집형 디자인','','[훈령 전체 목록](../../README.md) · [전체 매니페스트](../../diagrams-manifest.json)','']
for row in rows:
    stem=Path(row['files']['svg']['path']).stem
    md += [f'## {row["id"]} · {row["title"]}','','[WebP]('+stem+'.webp) · [PNG]('+stem+'.png) · [SVG 원본]('+stem+'.svg)','',f'![{row["title"]}]({stem}.webp)','',f'근거: [{row["article"]}]({row["source_url"]}) · {row["source_version"]}','','']
(folder/'README.md').write_text('\n'.join(md))
readme=subject/'README.md';t=readme.read_text();t=re.sub(r'78강 전체 · \d+장',f'78강 전체 · {len(m["items"])}장',t);t=re.sub(r'(\| \[DR-045\]\(lesson-045/diagrams/\) \|[^|]*\| )\d+장',lambda x:x.group(1)+str(lesson['diagram_count'])+'장',t)
for ext in ('svg','png','webp'):
    total=sum(row['files'][ext]['bytes'] for row in m['items'])/1024/1024
    t=re.sub(r'(\| '+ext.upper()+r' \|[^|]*\| )[\d.]+ MiB',lambda x:x.group(1)+f'{total:.2f} MiB',t)
readme.write_text(t)
print(json.dumps({'rendered':[x['id'] for x in new],'layout_errors':0,'visual_review':'pending'},ensure_ascii=False))
