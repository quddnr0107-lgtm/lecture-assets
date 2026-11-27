#!/usr/bin/env python3
"""Targeted Exam 80 TB-011-D01 source-alignment repair; no private manuscript in assets."""
from pathlib import Path
from PIL import Image
import hashlib, json, os, subprocess, tempfile
import build as desktop

ROOT=desktop.ROOT
SUB=ROOT/'integrated-defense'
N=SUB/'notion-v1'
P=SUB/'production-queue'
IDENT='TB-011-D01'
SOURCE_COMMIT='ca55be300f0280bb52e874eb93c540ca76c5c16f'
SOURCE_SHA='56e3e3568ff5d310b7383614f99bef808c18bdc1a0a883d1e31e6c43a41c3d67'
OLD_CONTENT_SHA='7c379da8309296b5858e51352c047cc5b5902b7da61a10c1e53a375715be4131'
CHANGES=[["진행 상황·대국민 협조를 알릴 필요가 있으면 설치·운영 가능","통합방위 진행 상황 및 대국민 협조사항 등을 알릴 필요가 있으면 설치·운영 가능"],["합동보도본부를 통해 기자단에 진행 상황을 하루 1차례 이상 제공","합동보도본부를 통해 취재기자단에 통합방위작전의 진행 상황을 1일 한 차례 이상 제공하여야 함"],["효율적 작전 수행에 필요하면 적의 행위·아군 작전상황 공개 유보 가능","효율적 작전 수행에 필요하면 적의 구체적 침투·도발 행위 내용과 아군의 통합방위작전 상황 등 공개 유보 가능"]]
def load(p): return json.loads(p.read_text())
def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def digest(d): return hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def repair(req):
    assert req['mode']=='desktop-mobile-script-repair' and req['lessons']==[11]
    source=load(P/'EXAM80-SCRIPT-SOURCE.json')
    assert source['exam_number']==80 and source['script_source_commit']==SOURCE_COMMIT
    pinned=next(x for x in source['lessons'] if x['lecture_id']=='TB-011')
    assert pinned['script_sha256']==SOURCE_SHA and pinned['script_blob_sha']=='7be74a2cc300ed21f060e36f862aecf71a3e06ce'
    data=load(N/'content.json')
    lesson=next(x for x in data['lessons'] if x['lecture_id']=='TB-011')
    d=next(x for x in lesson['diagrams'] if x['id']=='D01')
    a=load(N/'script-alignment.json')
    item=next(x for x in a['items'] if x['diagram_id']==IDENT)
    assert item['script_sha256']==SOURCE_SHA and item['diagram_content_sha256']==digest(d)
    assert digest(d)==OLD_CONTENT_SHA, 'Canonical diagram changed; re-review before editing'
    details=[x for sec in d['sections'] for x in sec['items']]
    for old,new in CHANGES:
        matching=[x for x in details if x['detail']==old]
        assert len(matching)==1, old
        matching[0]['detail']=new
    rec,qa=desktop.build(lesson,d)
    assert not qa['errors'] and not qa['overlaps'], str(qa['errors'])+str(qa['overlaps'])
    records=load(N/'render-records.json')
    idx=next(i for i,x in enumerate(records) if x['id']==IDENT)
    records[idx]=rec
    save(N/'render-records.json',records)
    # Use the existing SVG -> Sharp rasterizer, scoped to exactly one diagram.
    with tempfile.TemporaryDirectory() as deps:
        subprocess.run(['npm','install','--prefix',deps,'--no-save','--no-package-lock','sharp'],check=True,cwd=ROOT)
        env={**os.environ,'NODE_PATH':str(Path(deps)/'node_modules')}
        subprocess.run(['node',str(Path(__file__).with_name('render.cjs')),IDENT],check=True,cwd=ROOT,env=env)
    files={}
    for ext in ('svg','png','webp'):
        p=SUB/(rec['base']+'.'+ext)
        raw=p.read_bytes()
        if ext!='svg':
            with Image.open(p) as im:
                assert im.size==(1600,1120)
                im.verify()
        files[ext]={'path':str(p.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'width':1600,'height':1120}
    manifest=load(N/'manifest.json')
    mi=next(i for i,x in enumerate(manifest['items']) if x['id']==IDENT)
    manifest['items'][mi]={**manifest['items'][mi],**rec,'files':files}
    save(N/'manifest.json',manifest)
    rd=SUB/'lesson-011/diagrams/notion-v1/README.md'
    md=rd.read_text()
    for old,new in CHANGES:
        assert md.count(old)==1
        md=md.replace(old,new)
    rd.write_text(md)
    item['diagram_content_sha256']=digest(d)
    item['corrected_in_this_review']=True
    item['correction_note']='설치·운영 권한과 기자단 제공 의무의 진행 상황 표현 및 적의 침투·도발 범위 구분.'
    if IDENT not in a['corrected_diagrams']: a['corrected_diagrams'].append(IDENT)
    a['corrections'].append({'diagram_id':IDENT,'change':item['correction_note']})
    save(N/'script-alignment.json',a)
    save(N/'content.json',data)
    v=load(N/'verification.json')
    v['script_alignment']['corrected_diagrams']=a['corrected_diagrams']
    v['script_alignment']['latest_repair']={'diagram':IDENT,'visual_review':'pending','source_sha256':SOURCE_SHA,'diagram_content_sha256':digest(d),'files':files}
    save(N/'verification.json',v)
    report={'run_id':req['run_id'],'diagram_id':IDENT,'source_commit':SOURCE_COMMIT,'script_sha256':SOURCE_SHA,'old_content_sha256':OLD_CONTENT_SHA,'new_content_sha256':digest(d),'desktop_files':files,'layout_errors':qa['errors'],'text_overlaps':qa['overlaps'],'visual_review':'pending'}
    save(P/'runs'/(req['run_id']+'-desktop.json'),report)
