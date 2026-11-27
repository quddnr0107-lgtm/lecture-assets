#!/usr/bin/env python3
"""Render only the new, source-checked supplement diagrams. Do not overwrite originals."""
import json, subprocess, sys
from pathlib import Path
import build
ROOT=Path(__file__).resolve().parents[2]
SUB=ROOT/'integrated-defense'
DEST=SUB/'notion-v1'
DRAFT=SUB/'production-queue/supplement-drafts-20261127.json'
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main():
    data=json.loads((DEST/'content.json').read_text())
    records=json.loads((DEST/'render-records.json').read_text())
    draft=json.loads(DRAFT.read_text())
    if data.get('source_basis',{}).get('exam_number') != 80:
        raise ValueError('Require existing exam-80 script basis before supplement rendering')
    if draft.get('script_review',{}).get('status') != 'matched_existing_script':
        raise ValueError('Compare supplements with the existing exam-80 scripts first')
    ids={r['id'] for r in records}; new=[]; qa=[]
    for s in draft['items']:
        l=next(l for l in data['lessons'] if l['lesson']==s['lesson'])
        for d in s['diagrams']:
            ident=f"{l['lecture_id']}-{d['id']}"
            if ident in ids:
                existing=next(x for x in l['diagrams'] if x['id']==d['id'])
                if existing!=d:raise ValueError('Conflicting existing ID '+ident)
                continue
            if any(x['id']==d['id'] for x in l['diagrams']):raise ValueError('Conflicting content '+ident)
            r,q=build.build(l,d)
            if q['errors'] or q['overlaps']:raise ValueError(json.dumps(q,ensure_ascii=False))
            l['diagrams'].append(d);records.append(r);new.append(ident);qa.append(q)
    records.sort(key=lambda r:(r['lesson'],r['id']))
    if new:
        write(DEST/'content.json',data);write(DEST/'render-records.json',records)
        subprocess.run(['node',str(Path(__file__).with_name('render.cjs')),*new],check=True)
        subprocess.run([sys.executable,str(Path(__file__).with_name('package.py'))],check=True)
        # Retain old baseline QA explicitly. New diagrams require a human visual review.
        write(SUB/'production-queue/runs/tb-20261127-01-supplement-layout.json',{'status':'machine_checked_pending_visual_review','new_ids':new,'checks':qa})
    print(json.dumps({'new_ids':new},ensure_ascii=False))
if __name__=='__main__':main()
