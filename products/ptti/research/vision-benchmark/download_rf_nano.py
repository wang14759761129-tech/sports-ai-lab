"""Stream the official Apache core Nano checkpoint; verify upstream digest before loading."""
import hashlib
import json
from pathlib import Path
import urllib.request

URL = "https://storage.googleapis.com/rfdetr/nano_coco/checkpoint_best_regular.pth"
EXPECTED_MD5 = "fb6504cce7fbdc783f7a46991f07639f"
EXPECTED_BYTES = 366287238
CODE_COMMIT = "7433d5919d0f7e72cc6cb78663e0a731afd499e0"


def main():
    root = Path.home() / "AppData/Local/PTTI-Dev/technology-foundation/rf-detr-model"
    root.mkdir(parents=True, exist_ok=True)
    target = root / "rf-detr-nano.pth"
    partial = target.with_suffix(".part")
    if not target.exists():
        offset = partial.stat().st_size if partial.exists() else 0
        request = urllib.request.Request(URL, headers={"Range": f"bytes={offset}-"} if offset else {})
        with urllib.request.urlopen(request, timeout=45) as response:
            if offset and response.status != 206:
                raise ValueError("SERVER_REFUSED_RESUME_PARTIAL_RETAINED")
            total = int(response.headers["Content-Length"]) + offset
            if total != EXPECTED_BYTES:
                raise ValueError("UNEXPECTED_CHECKPOINT_SIZE")
            with partial.open("ab" if offset else "xb") as stream:
                while block := response.read(1024*1024):
                    stream.write(block)
                    offset += len(block)
                    if offset % (32*1024*1024) < len(block):
                        print(f"checkpoint {offset}/{total} bytes", flush=True)
        if partial.stat().st_size != EXPECTED_BYTES:
            raise ValueError("CHECKPOINT_INCOMPLETE")
        check = partial
    else:
        check = target
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with check.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            sha.update(block)
            md5.update(block)
    if md5.hexdigest() != EXPECTED_MD5 or check.stat().st_size != EXPECTED_BYTES:
        raise ValueError("CHECKPOINT_DIGEST_MISMATCH_REFUSE_LOAD")
    if check == partial:
        partial.replace(target)
    provenance = {"model": "RF-DETR Nano COCO", "version": "1.11.2", "code_commit": CODE_COMMIT,
                  "repo": "https://github.com/roboflow/rf-detr", "source": URL,
                  "license": "Apache-2.0", "weights_license": "Apache-2.0 core Nano",
                  "upstream_md5": EXPECTED_MD5, "sha256": sha.hexdigest(), "bytes": EXPECTED_BYTES,
                  "validation": "UPSTREAM_MD5_AND_SIZE_VERIFIED; SHA256_RECORDED",
                  "architecture": "RFDETRNano; DINOv2; resolution384", "training": "NONE",
                  "model_path": str(target)}
    (root / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps(provenance), flush=True)


if __name__ == "__main__":
    main()
