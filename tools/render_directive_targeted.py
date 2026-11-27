#!/usr/bin/env python3
"""Render script-bound targeted revisions and supplements; never rebuild unrelated assets."""
import copy,hashlib,json,re,concurrent.futures
from pathlib import Path
from PIL import Image,ImageChops
from render_directive_diagrams import paginate,render_slide,check_boxes,rasterize
root=Path(__file__).resolve().parents[1]; subject=root/'defense-directives'; d=subject/'diagrams'
def load(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
req=load(d/'targeted-render-request.json');q=load(d/'production-queue.json');s=load(d/'diagrams.source.json');m=load(subject/'diagrams-manifest.json');b=load(d/'script-basis.json');qa=load(d/'script-alignment-qa.json');layout=load(d/'layout-qa.json');content=load(d/'content-qa.json')
assert req['exam']==b['exam']['number']==80 and req['schema_version']==2
assert q['state']['active_run']['id']==req['run_id']
records=[]; pending=[]; changed=[]
for g in req['groups']:
    lid=g['lesson_id']; binding=next(x for x in b['lessons'] if x['lesson_id']==lid); lesson=next(x for x in m['lessons'] if x['id']==lid);folder=root/lesson['path']
    assert binding['source_git_blob']==g['expected_source_blob'] and binding['source_sha256']==g['expected_script_sha256']
    assert max(int(x.split('-D')[1]) for x in lesson['diagram_ids'])==g['existing_max']
    assert set(p.stem.split('-editorial')[0] for p in folder.glob('*.svg'))==set(lesson['diagram_ids'])
    for entry in g['items']:
        did=entry['id']; src=entry['slide']; revision=entry['mode']=='revision'
        assert src['lessonId']==lid and src['scriptEvidence']['source_sha256']==binding['source_sha256']
        job=next(x for x in q['production_jobs'] if x['id']==entry['job_id'])
        assert job['status']=='running' and job['claimed_by']==req['run_id']
        old=next((x for x in m['items'] if x['id']==did),None)
        assert bool(old)==revision
        slides=paginate(copy.deepcopy(src));assert len(slides)==1,(did,'pagination required')
        slide=slides[0];svg,boxes=render_slide(slide,did);errors=check_boxes(boxes,did);assert not errors,errors
        paths={ext:folder/f'{did}-editorial-v1.{ext}' for ext in ('svg','png','webp')}
        assert all(p.exists()==revision for p in paths.values())
        paths['svg'].write_text(svg)
        if revision:
            matches=[i for i,x in enumerate(s['diagrams']) if x['lessonId']==lid and x['title']==old['title']]
            assert len(matches)==1
            s['diagrams'][matches[0]]=src
        else:
            assert not any(x['lessonId']==lid and x['title']==src['title'] for x in s['diagrams'])
            s['diagrams'].append(src);lesson['diagram_ids'].append(did)
        pending.append((entry,src,slide,boxes,paths,job,old))
    lesson['diagram_count']=len(lesson['diagram_ids']);changed.append(lid)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(rasterize,[(x[4]['svg'],x[4]['png'],x[4]['webp']) for x in pending]))
for entry,src,slide,boxes,paths,job,old in pending:
    did=entry['id'];lid=src['lessonId']
    with Image.open(paths['png']) as a,Image.open(paths['webp']) as w:
        assert a.size==w.size==(1600,1120)
        assert ImageChops.difference(a.convert('RGB'),w.convert('RGB')).getbbox() is None
    files={k:{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for k,p in paths.items()}
    row={'id':did,'lecture_id':lid,'lesson_number':int(lid.split('-')[1]),'title':src['title'],'article':src['sourceArticle'],'article_key':src['articleKey'],'source_clauses':src['sourceClauses'],'source_url':src['sourceUrl'],'source_version':src['sourceVersion'],'effective_date':src['effectiveDate'],'note':src.get('note',''),'width':1600,'height':1120,'body_font_size':slide['_bodySize'],'files':files,'script_ref':lid,'script_evidence':src['scriptEvidence']}
    if old:m['items'][m['items'].index(old)]=row
    else:m['items'].append(row)
    job.update(status='qa',outputs=list(files.values()),diagram_id=did,layout_errors=[],png_webp_pixel_equal=True,visual_review='pending',claimed_by=None,claimed_at=None,lease_expires_at=None)
    records.append({'id':did,'mode':entry['mode'],'script_evidence':src['scriptEvidence'],'layout_errors':[],'png_webp_pixel_equal':True,'visual_review':'pending','files':files,'text_boxes':boxes})
m['items'].sort(key=lambda x:x['id']);s['diagrams'].sort(key=lambda x:x['lessonId']);m['coverage']['diagrams']=len(m['items']);m['status']='exam80_script_alignment_in_progress'
for lid in changed:
    lesson=next(x for x in m['lessons'] if x['id']==lid);j=next(x for x in q['jobs'] if x['lesson_id']==lid)
    j.update(existing_diagram_count=lesson['diagram_count'],existing_diagram_ids=lesson['diagram_ids'])
    layout.setdefault('lessonCounts',{})[lid]=lesson['diagram_count']
    folder=root/lesson['path'];rows=[x for x in m['items'] if x['lecture_id']==lid]
    md=[f'# {lid} · {lesson["title"]}','','도식 **'+str(len(rows))+'장** · 1600 × 1120 · 흑백 편집형 디자인','','[훈령 전체 목록](../../README.md) · [전체 매니페스트](../../diagrams-manifest.json)','']
    for row in rows:
        stem=Path(row['files']['svg']['path']).stem
        md += [f'## {row["id"]} · {row["title"]}','','[WebP]('+stem+'.webp) · [PNG]('+stem+'.png) · [SVG 원본]('+stem+'.svg)','',f'![{row["title"]}]({stem}.webp)','',f'근거: [{row["article"]}]({row["source_url"]}) · {row["source_version"]}','','']
    (folder/'README.md').write_text('\n'.join(md))
q['state'].update(active_run=None,production_jobs_queued=sum(x['status']=='queued' for x in q['production_jobs']),production_jobs_qa=sum(x['status']=='qa' for x in q['production_jobs']),diagrams_added_after_baseline=len(m['items'])-q['baseline']['diagrams'])
q['runs'].append({'id':req['run_id'],'status':'rendered_pending_visual_qa','new_diagrams':sum(x['mode']=='new' for x in records),'revised_diagrams':sum(x['mode']=='revision' for x in records),'completed_reviews':0,'diagram_ids':[x['id'] for x in records]})
qa.setdefault('targeted_render_runs',[]).append({'run_id':req['run_id'],'lesson_ids':changed,'records':records})
qa['new_diagrams']=q['state']['diagrams_added_after_baseline']
layout['diagrams']=len(m['items']);layout.setdefault('targeted_runs',[]).append({'run_id':req['run_id'],'ids':[x['id'] for x in records],'errors':[]})
content.setdefault('script_targeted_runs',[]).append({'run_id':req['run_id'],'ids':[x['id'] for x in records],'status':'content_checked_rendered_visual_pending'})
for path,data in [(d/'diagrams.source.json',s),(subject/'diagrams-manifest.json',m),(d/'production-queue.json',q),(d/'script-alignment-qa.json',qa),(d/'layout-qa.json',layout),(d/'content-qa.json',content)]:save(path,data)
readme=subject/'README.md';t=readme.read_text();t=re.sub(r'78강 전체 · \d+장',f'78강 전체 · {len(m["items"])}장',t)
for lid in changed:
    lesson=next(x for x in m['lessons'] if x['id']==lid)
    t=re.sub(r'(\| \['+lid+r'\]\(lesson-'+lid.split('-')[1]+r'/diagrams/\) \|[^|]*\| )\d+장',lambda x:x.group(1)+str(lesson['diagram_count'])+'장',t)
for ext in ('svg','png','webp'):
    total=sum(row['files'][ext]['bytes'] for row in m['items'])/1024/1024
    t=re.sub(r'(\| '+ext.upper()+r' \|[^|]*\| )[\d.]+ MiB',lambda x:x.group(1)+f'{total:.2f} MiB',t)
readme.write_text(t)
print(json.dumps({'rendered':[x['id'] for x in records],'layout_errors':0,'visual_review':'pending'},ensure_ascii=False))
