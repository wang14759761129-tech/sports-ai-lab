"""Import an explicit reviewed list into an already-running isolated local app."""
import argparse
import json
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest",type=Path)
    parser.add_argument("--base-url",required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    url=urlsplit(args.base_url)
    if url.scheme != "http" or url.hostname != "127.0.0.1" or url.username or url.password or url.path not in {"", "/"}:
        parser.error("Only an explicitly started isolated localhost QA service is supported")
    if args.report.exists():
        parser.error("Report already exists; choose a new name, do not overwrite evidence")
    with urllib.request.urlopen(args.base_url.rstrip("/") + "/api/diagnostics/database", timeout=10) as response:
        diagnostics = json.load(response)
    if diagnostics.get("environment") != "TEST":
        parser.error("The destination must explicitly report TEST isolation")
    payload=json.loads(args.manifest.read_text(encoding="utf-8"))
    request=urllib.request.Request(args.base_url.rstrip("/")+"/api/video-evidence/library/catalog/import",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(request,timeout=30) as response:
        report=json.load(response)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open("x",encoding="utf-8") as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False))


if __name__ == "__main__":
    main()
