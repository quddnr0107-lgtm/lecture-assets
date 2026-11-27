#!/usr/bin/env python3
"""Audit and package the approved Exam 80 integrated-defense diagrams, without rerendering."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from xml.etree import ElementTree as ET
import hashlib, json, os, re, zipfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
SUB=ROOT/'integrated-defense'
N=SUB/'notion-v1'
P=SUB/'production-queue'
def load(p): return json.loads(p.read_text())
def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(b): return hashlib.sha256(b).hexdigest()
def chash(d): return sha(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def main(req):
    q=load(P/'queue.json')
    j=next(x for x in q['jobs'] if x['id']=='TB-FINAL-AUDIT')
    lease=j.get('lease') or {}
    assert j['status']=='running' and lease.get('run_id')==req['run_id']
    assert datetime.fromisoformat(lease['expires_at'].replace('Z','+00:00'))>datetime.now(timezone.utc)
    assert all(x['status']=='done' for x in q['jobs'] if x['id']!=j['id'])
    s=load(P/'EXAM80-SCRIPT-SOURCE.json'); a=load(N/'script-alignment.json')
    c=load(N/'content.json'); d=load(N/'manifest.json'); m=load(N/'mobile-manifest.json')
    cat=load(N/'lecture-map.json')
    assert s['exam_number']==a['exam_number']==m['exam_number']==req['exam_number']==80
    assert s['script_source_commit']==req['source_commit'] and s['law_cutoff']=='2027-02-02'
    assert c['style']==d['style']==m['style']=='07-notion-editorial'
    sm={x['lecture_id']:x for x in s['lessons']}
    am={x['diagram_id']:x for x in a['items']}
    dm={x['id']:x for x in d['items']}
    assert len(sm)==len(c['lessons'])==len(cat)==25
    assert len(am)==len(dm)==len(d['items'])==55 and len(m['items'])==137
    ids=set()
    for l,k in zip(c['lessons'],cat):
        lid=l['lecture_id']; assert lid==k['lecture_id']==f"TB-{l['lesson']:03d}"
        assert l['article']==k['article'] and sm[lid]['article'].endswith(l['article'])
        assert k['diagrams']==[lid+'-'+x['id'] for x in l['diagrams']]
        for x in l['diagrams']:
            ident=lid+'-'+x['id']; ids.add(ident); ar=am[ident]; dr=dm[ident]
            assert ar['status']=='matched_existing_script' and ar['lecture_id']==lid
            assert ar['script_sha256']==sm[lid]['script_sha256'] and ar['diagram_content_sha256']==chash(x),ident
            assert ar['references'] and dr['sources']==x['sources'] and dr['lecture_id']==lid
    assert ids==set(am)==set(dm)
    groups=defaultdict(list)
    for rec in m['items']:
        ident=rec['source_id']; ar=am[ident]; groups[ident].append(rec)
        assert rec['exam_number']==80 and rec['lesson']==dm[ident]['lesson']
        assert rec['script_sha256']==ar['script_sha256'] and rec['diagram_content_sha256']==ar['diagram_content_sha256']
        assert rec['qa']['text_bounds'] and rec['qa']['no_text_overlap'] and rec['qa']['min_body_px_at_390']>=14
        assert rec['sources']==dm[ident]['sources']
    assert set(groups)==ids
    for ident,rows in groups.items():
        assert sorted(x['page'] for x in rows)==list(range(1,len(rows)+1))
        assert all(x['page_count']==len(rows) for x in rows)
    paths=set()
    for rec in d['items']+m['items']:
        assert set(rec['files'])=={'svg','png','webp'}
        for ext,f in rec['files'].items():
            rel=f['path']; assert rel.startswith(f"integrated-defense/lesson-{rec['lesson']:03d}/diagrams/notion-v1/") and rel.endswith('.'+ext)
            path=ROOT/rel; assert path.resolve().is_relative_to(SUB.resolve()) and rel not in paths
            raw=path.read_bytes(); assert len(raw)==f['bytes'] and sha(raw)==f['sha256'],rel
            if ext=='svg':
                el=ET.fromstring(raw); assert el.tag.endswith('svg')
                assert float(el.attrib['width'].removesuffix('px'))==f['width'] and float(el.attrib['height'].removesuffix('px'))==f['height'],rel
            else:
                with Image.open(path) as im:
                    assert im.size==(f['width'],f['height']),rel
                    im.verify()
            paths.add(rel)
    assert len(paths)==576
    for job in q['jobs']:
        ev=job.get('completed_evidence') or {}
        if ev.get('visual_report'): assert (ROOT/ev['visual_report']).is_file(),job['id']
    assert load(N/'verification.json')['script_alignment']['latest_repair']['visual_review']=='pass'
    class Links(HTMLParser):
        def __init__(self): super().__init__(); self.links=[]
        def handle_starttag(self,tag,attrs):
            for k,v in attrs:
                if k in ('href','src') and v: self.links.append(v)
    html=N/'index.html'; parser=Links(); parser.feed(html.read_text())
    checked=0
    for link in parser.links:
        u=urlsplit(link)
        if u.scheme or u.netloc or not u.path: continue
        target=(html.parent/unquote(u.path)).resolve()
        assert target.is_relative_to(SUB.resolve()) and target.exists(),link
        checked+=1
    idx=(N/'mobile-index.md').read_text()
    for n in range(1,26):
        count=sum(x['lesson']==n for x in m['items'])
        assert re.search(r'\| \['+f'{n:02d}'+r'강\]\([^)]+\) \| '+str(count)+r' \| 완료 \|',idx),n
        for path in (SUB/f'lesson-{n:03d}'/'diagrams'/'notion-v1'/'README.md',SUB/f'lesson-{n:03d}'/'diagrams'/'notion-v1'/'mobile'/'README.md'):
            assert path.is_file(); paths.add(str(path.relative_to(ROOT)))
    for name in ('README.md','index.html','lecture-map.json','manifest.json','mobile-index.md','mobile-manifest.json','content.json','script-alignment.json','style-guide.md','verification.json'):
        paths.add(str((N/name).relative_to(ROOT)))
    paths.add(str((P/'EXAM80-SCRIPT-SOURCE.json').relative_to(ROOT)))
    out=SUB/'downloads'/'exam80-integrated-defense-notion-v1.zip'
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for rel in sorted(paths): z.write(ROOT/rel,rel)
        z.writestr('README.txt','Exam 80 integrated-defense: 25 lessons, 55 core diagrams, 137 mobile pages, 576 image files. Open integrated-defense/notion-v1/index.html or mobile-index.md. Historical queue/design-study links are repository-only. Public learning summaries only.\n')
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None and len(z.namelist())==len(paths)+1
    raw=out.read_bytes(); assert len(raw)<90*1024*1024
    report={'run_id':req['run_id'],'exam_number':80,'status':'audit_pass_remote_verification_pending','input_commit':os.environ.get('GITHUB_SHA'),'source_commit':s['script_source_commit'],'lesson_count':25,'core_diagrams':55,'mobile_pages':137,'asset_files_sha256_verified':576,'desktop_content_hashes_verified':55,'mobile_content_links_verified':137,'gallery_links_verified':checked,'prior_visual_review':'25 lesson mobile jobs done; desktop visual records plus TB-011 direct review','bundle':{'path':str(out.relative_to(ROOT)),'bytes':len(raw),'sha256':sha(raw),'entries':len(paths)+1}}
    save(P/'runs'/(req['run_id']+'.json'),report)
    save(P/'completion.json',report)
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
    main(load(P/'render-request.json'))
