#!/usr/bin/env python3
"""Render only approved generation-2 draft SVGs; never promote or change a lecture."""
import hashlib, json, pathlib, subprocess, tempfile, sys
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[2]
SUBJECT = ROOT / "military-service-act"
DRAFT = SUBJECT / "production-evidence/exam80-generation-2/draft-batches"
REQUEST = DRAFT / "render-request-20261127.json"
RECEIPT = DRAFT / "render-receipt-20261127.json"
def load(p): return json.loads(p.read_text(encoding="utf-8"))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def validate():
    q=load(SUBJECT/"production-queue.json")
    idx=load(SUBJECT/"script-sources-exam80.json")
    req=load(REQUEST)
    assert q["generation"]==req["generation"]==2
    assert q["source_basis_sha256"]==req["source_basis_sha256"]
    assert q["source_basis"]["commit"]==idx["source_commit"]==req["source_commit"]
    assert req["scope"]=="draft_raster_only_not_final"
    src={i["lecture_id"]:i["script_git_blob_sha"] for i in idx["lectures"]}
    jobs={i["lecture_id"]:i for i in q["jobs"]}
    seen=set()
    for i in req["items"]:
        p=(ROOT/i["svg_path"]).resolve()
        assert p.is_relative_to(DRAFT) and p.suffix==".svg" and p not in seen
        assert p.parent.parent.name in {"20261127-01","20261127-02"}
        assert digest(p)==i["svg_sha256"]
        assert src[i["lecture_id"]]==jobs[i["lecture_id"]]["source"]["script_git_blob_sha"]==i["script_git_blob_sha"]
        seen.add(p)
    return req
def main():
    req=validate()
    if "--validate-only" in sys.argv: return
    outputs=[]
    previous={}
    if RECEIPT.exists():
        prev=load(RECEIPT)
        if all(prev.get(k)==req[k] for k in ("generation","source_basis_sha256","source_commit")):
            previous={item["svg_path"]:item for item in prev.get("items",[])}
    with tempfile.TemporaryDirectory() as td:
        for n,i in enumerate(req["items"]):
            svg=ROOT/i["svg_path"]
            cached=previous.get(i["svg_path"])
            existing=svg.with_suffix(".webp")
            if cached and existing.exists() and all(cached.get(k)==v for k,v in i.items()):
                binary=existing.read_bytes()
                if cached.get("webp_sha256")==digest(existing) and cached.get("webp_bytes")==len(binary) and binary[:4]==b"RIFF" and binary[8:12]==b"WEBP" and binary[12:16]==b"VP8L":
                    with Image.open(existing) as im:
                        assert im.size==(1600,1120) and im.format=="WEBP"
                        im.verify()
                    outputs.append(cached)
                    continue
            png=pathlib.Path(td)/f"{n}.png"
            subprocess.run(["inkscape",str(svg),"--export-type=png",f"--export-filename={png}","--export-width=1600","--export-height=1120"],check=True)
            out=svg.with_suffix(".webp")
            with Image.open(png) as im:
                assert im.size==(1600,1120)
                im.convert("RGB").save(out,"WEBP",lossless=True,method=6)
            with Image.open(out) as im:
                assert im.size==(1600,1120) and im.format=="WEBP"
                im.verify()
            binary=out.read_bytes()
            assert binary[:4]==b"RIFF" and binary[8:12]==b"WEBP" and binary[12:16]==b"VP8L"
            outputs.append({**i,"webp_path":str(out.relative_to(ROOT)),"webp_sha256":digest(out),"webp_bytes":len(binary),"dimensions":[1600,1120],"lossless":True,"status":"rendered_draft_requires_visual_review"})
    validate()
    RECEIPT.write_text(json.dumps({"generation":req["generation"],"source_basis_sha256":req["source_basis_sha256"],"source_commit":req["source_commit"],"request_sha256":digest(REQUEST),"status":"draft_raster_only_not_final","final_new_images":0,"items":outputs},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
