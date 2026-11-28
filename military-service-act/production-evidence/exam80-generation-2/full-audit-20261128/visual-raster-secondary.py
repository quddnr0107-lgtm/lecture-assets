#!/usr/bin/env python3
"""Verify supplemental images with their recorded Inkscape rendering pipeline."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,subprocess,hashlib
from PIL import Image,ImageChops,ImageStat
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
TMP=ROOT.parent/'audit-tmp'/'visual'/'inkscape'
TMP.mkdir(parents=True,exist_ok=True)
m=json.loads((ROOT/'military-service-act/diagrams-manifest.json').read_text())
items={i['id']:i for i in m['items']}
initial=json.loads((OUT/'visual-raster-comparison.json').read_text())
pending=[r for r in initial['pages'] if r.get('identical') is False]
def check(row):
    item=items[row['id']];svg=ROOT/item['files']['svg']['path'];target=TMP/(item['id']+'.png')
    r=subprocess.run(['inkscape',str(svg),'--export-type=png',f'--export-filename={target}','--export-width=1600','--export-height=1120'],capture_output=True,text=True)
    if r.returncode:return {'id':item['id'],'error':r.stderr}
    a=Image.open(target).convert('RGB');b=Image.open(ROOT/item['files']['webp']['path']).convert('RGB');diff=ImageChops.difference(a,b);bounds=diff.getbbox()
    return {'id':item['id'],'identical':bounds is None,'difference_bbox':bounds,'mean_absolute_difference':sum(ImageStat.Stat(diff).mean)/3,'inkscape_pixel_sha256':hashlib.sha256(a.tobytes()).hexdigest(),'webp_pixel_sha256':hashlib.sha256(b.tobytes()).hexdigest()}
with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(check,pending))
report={'date_kst':'2026-11-28','method':'Inkscape PNG export at 1600x1120, then RGB decoded-pixel comparison against official WebP','reason':'33 supplements were rendered by Inkscape in the repository workflow; sharp uses a different rasterizer','summary':{'pages':len(rows),'exact_pixel_matches':sum(bool(x.get('identical')) for x in rows),'mismatches':sum(x.get('identical') is False for x in rows),'errors':sum('error' in x for x in rows)},'pages':rows}
(OUT/'visual-raster-inkscape-comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report['summary']))
