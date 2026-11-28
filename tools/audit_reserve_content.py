#!/usr/bin/env python3
"""Check exact source ranges and flag numbers/actors for independent review.

This is an evidence-gap detector, not a claim that legal meaning was verified.
No private source excerpt is written to the public audit output.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'reserve-forces-act/diagrams'
ACTORS=['국방부장관','병무청장','지방병무청장','수임군부대의 장','수임군부대장','각 군 참모총장','경찰서장','시·도지사','직장의 장','고용노동부장관','보건복지부장관','국가보훈부장관','행정안전부장관','해군참모총장','국가보훈처장','산업통상부장관','산업통상자원부장관']

def numbers(s):
    s=re.sub(r'(?<=\d),(?=\d)','',s)
    values=set()
    for m in re.finditer(r'\d+(?:[만천백십]\d*)*',s):
        text=m.group()
        if not re.search('[만천백십]',text):
            values.add(int(text));continue
        value=0;section=0;current=''
        for ch in text:
            if ch.isdigit():current+=ch
            elif ch=='만':
                value+=(section+(int(current) if current else 0) or 1)*10000
                section=0;current=''
            else:
                section+=(int(current) if current else 1)*{'천':1000,'백':100,'십':10}[ch];current=''
        if current:section+=int(current)
        values.add(value+section)
    words={'한':1,'하나':1,'첫':1,'첫째':1,'두':2,'둘':2,'둘째':2,'세':3,'셋':3,'셋째':3,'네':4,'넷':4,'넷째':4,'다섯':5,'여섯':6,'일곱':7,'여덟':8,'아홉':9,'열':10,'열한':11,'열두':12,'서른':30,'예순':60}
    for word,num in words.items():
        if re.search(r'(?<![가-힣])'+word+r'(?=\s|$|[.,·]|째|번째|개|명|갈래|가지|입니다|이나)',s):values.add(num)
    return values

def instructional_text(d):
    parts=[d['title'],d.get('subtitle',''),d.get('note','')]
    for side in ['left','right']:
        col=d[side];parts.append(col['title'])
        for item in col['items']:parts.extend([item.get('label',''),item['text']])
    return '\n'.join(parts)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,required=True);args=ap.parse_args()
    sources=json.loads((DATA/'source-index.json').read_text())
    source_map={r['lessonId']:r for r in sources['lessons']}
    failures=[];flags=[];stats=[]
    for path in sorted((DATA/'content').glob('RL-*.json')):
        l=json.loads(path.read_text());r=source_map[l['lessonId']]
        raw=(args.source_root/r['sourcePath']).read_bytes();s=raw.decode();lines=s.splitlines()
        blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if blob!=r['gitBlobSha'] or hashlib.sha256(raw).hexdigest()!=r['sourceSha256']:
            failures.append({'lessonId':l['lessonId'],'type':'source-hash-mismatch'})
        for d in l['diagrams']:
            selected=[]
            for span in d['sourceRanges']:
                start,end=span['startLine'],span['endLine']
                if not 1<=start<=end<=len(lines):
                    failures.append({'lessonId':l['lessonId'],'diagramId':d['id'],'type':'invalid-range','range':span});continue
                selected.extend(lines[start-1:end])
            excerpt='\n'.join(selected);visible=instructional_text(d)
            # An article number in a subtitle can be established by the lesson's
            # opening title. Other numbers must have a recorded evidence range.
            reference=excerpt+'\n'+lines[0]
            missing=sorted(numbers(visible)-numbers(reference))
            actors=[a for a in ACTORS if a in visible and a not in reference]
            if missing or actors:
                flags.append({'lessonId':l['lessonId'],'diagramId':d['id'],'numbersAbsentFromRanges':missing,'actorsAbsentFromRanges':actors,'numbersAbsentFromWholeScript':sorted(set(missing)-numbers(s)),'actorsAbsentFromWholeScript':[a for a in actors if a not in s]})
        stats.append({'lessonId':l['lessonId'],'sourceLines':len(lines),'sourceBytes':len(raw),'diagramCount':len(l['diagrams']),'topicCount':len(l['coverage']),'sourceBlobVerified':blob==r['gitBlobSha']})
    report={'schemaVersion':1,'scope':'numeric-and-actor-evidence-gaps','automatedSemanticVerdict':False,'lessonCount':len(stats),'diagramCount':sum(x['diagramCount'] for x in stats),'sourceLineCount':sum(x['sourceLines'] for x in stats),'failures':failures,'flags':flags,'lessons':stats}
    (DATA/'review').mkdir(parents=True,exist_ok=True)
    (DATA/'review/evidence-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'lessons':len(stats),'diagrams':report['diagramCount'],'failures':len(failures),'flags':flags},ensure_ascii=False,indent=2))
    return bool(failures)

if __name__=='__main__':raise SystemExit(main())
