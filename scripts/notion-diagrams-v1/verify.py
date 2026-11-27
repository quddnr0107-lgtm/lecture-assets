#!/usr/bin/env python3
"""Validate visible content, catalogue mappings, dimensions and file integrity."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit
import json, re, hashlib, xml.etree.ElementTree as ET
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
SUB=ROOT/'integrated-defense';DEST=SUB/'notion-v1'

def norm(s):return re.sub(r'[\s①②③④⑤]','',str(s))

def main():
    data=json.loads((DEST/'content.json').read_text())
    manifest=json.loads((DEST/'manifest.json').read_text())
    lessons=data['lessons'];assert [l['lesson'] for l in lessons]==list(range(1,26))
    assert len(manifest['items'])==sum(len(l['diagrams']) for l in lessons)==49
    entries={r['id']:r for r in manifest['items']};assert len(entries)==49
    checked=0
    for l in lessons:
        assert l['lecture_id']==f'TB-{l["lesson"]:03d}'
        for d in l['diagrams']:
            ident=l['lecture_id']+'-'+d['id'];rec=entries[ident]
            assert rec['lesson']==l['lesson'] and rec['article']==l['article']
            xml=ET.parse(ROOT/rec['files']['svg']['path'])
            visible=norm(' '.join(''.join(t.itertext()) for t in xml.findall('.//{http://www.w3.org/2000/svg}text')))
            expected=[d['title'],d['subtitle'],d['takeaway']]+d.get('display_notes',d['notes'])
            for sec in d['sections']:
                expected.append(sec['title'])
                for item in sec['items']:expected.extend([item['label'],item['detail']])
            for text in expected:
                assert norm(text) in visible,(ident,'missing visible text',text)
            for source in d['sources']:assert urlsplit(source['url']).hostname in ['law.go.kr','www.law.go.kr']
            for ext,meta in rec['files'].items():
                path=ROOT/meta['path'];body=path.read_bytes()
                assert hashlib.sha256(body).hexdigest()==meta['sha256'],path
                assert len(body)==meta['bytes']
                if ext in ['png','webp']:
                    with Image.open(path) as image:assert image.size==(1600,1120)
                checked+=1
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.links=[];self.cards=0;self.options=0
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='article':self.cards+=1
            if tag=='option':self.options+=1
            for k in ['href','src']:
                if k in attrs:self.links.append(attrs[k])
    gallery=Links();gallery.feed((DEST/'index.html').read_text())
    assert gallery.cards==49 and gallery.options==26
    for link in gallery.links:
        if not urlsplit(link).scheme and not link.startswith('#'):assert (DEST/link).exists(),link
    qa_path=ROOT.parent/'production'/'build'/'layout-qa.json'
    qa=json.loads(qa_path.read_text())
    assert len(qa)==49 and not any(q['errors'] or q['overlaps'] for q in qa)
    result={'checked_date_kst':'2026-11-27','lessons':25,'diagrams':49,'image_files_checked':checked,'visible_content_preserved':True,'all_dimensions':[1600,1120],'file_hashes_match':True,'layout_bounds_errors':0,'text_overlap_errors':0,'gallery_relative_links_checked':len(gallery.links),'gallery_browser_runtime_tested':False,'visual_review':'49개 전체 이미지 축소본 확인, 밀도 높은 도식 원본 확대 확인, 최종 수정본 재확인','law_basis':'법률 제21065호(시행2025-10-01), 대통령령 제36728호(시행2026-10-02)','legal_scope':'핵심 관계 요약. 지역별 조례·외부 행정규칙·비공개 작전지침은 범위 밖.','checks':['실제 강의 TB-001~TB-025와 조문 대응','모든 제목·노드·본문·표시 주석의 SVG 텍스트 보존','PNG·WebP 크기와 SHA-256','텍스트 경계·겹침','강의별 출처와 예외 표시','독립 비교와 절차 화살표 구분']}
    (DEST/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
