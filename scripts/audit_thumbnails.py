"""Read-only audit for MC thumbnail files, duplicates, quality, and Markdown links."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from collections import defaultdict
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from image.thumbnail_quality import quality_issues

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def image_ref(path, field):
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m: return None
    f = re.search(rf"^{re.escape(field)}:\s*[\"']?([^\"'\n]+)", m.group(1), re.M)
    return f.group(1).strip() if f else None

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--images", type=Path, default=Path("output/images"))
    p.add_argument("--content", type=Path, default=Path("output/drafts"))
    p.add_argument("--report", type=Path, default=Path("output/thumbnail-audit.json"))
    p.add_argument("--image-field", default="image")
    p.add_argument("--min-size-kb", type=int, default=15)
    args = p.parse_args()
    files = sorted(args.images.glob("thumb_*.webp"))
    groups = defaultdict(list); records=[]; invalid=[]
    for path in files:
        digest = sha256(path); groups[digest].append(str(path))
        record={"path":str(path),"sha256":digest,"size_bytes":path.stat().st_size}
        issues=quality_issues(path, min_bytes=args.min_size_kb*1024)
        try:
            with Image.open(path) as im: record.update({"format":im.format,"width":im.width,"height":im.height})
        except Exception as exc: record["error"]=str(exc); issues.append("invalid_image")
        record["quality_issues"]=issues
        if issues: invalid.append(record)
        records.append(record)
    dup={k:v for k,v in groups.items() if len(v)>1}
    content_files=sorted(args.content.rglob("*.md")) if args.content.exists() else []
    refs=0; dangling=[]
    for content in content_files:
        ref=image_ref(content,args.image_field)
        if not ref: continue
        refs+=1; target=args.images.parent / ref.split("?",1)[0].lstrip("/")
        if not target.exists(): dangling.append({"content":str(content),"image":ref})
    report={"images_root":str(args.images),"content_root":str(args.content),"summary":{"image_files":len(files),"frontmatter_references":refs,"duplicate_groups":len(dup),"duplicate_files":sum(map(len,dup.values())),"invalid_images":len(invalid),"dangling_references":len(dangling)},"duplicate_groups":dup,"invalid_images":invalid,"dangling_references":dangling,"image_records":records}
    args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report["summary"],ensure_ascii=False,indent=2))
    return 0
if __name__ == "__main__": raise SystemExit(main())
