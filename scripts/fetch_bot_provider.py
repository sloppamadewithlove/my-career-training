"""Build-time verification/recovery of the allowlisted learned-policy artifacts.

No code is downloaded or executed. Downloads are pinned to an upstream commit,
bounded, hash checked before atomic replacement, and retain their own license.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from my_career_training.bots.providers import (  # noqa: E402
    LICENSE_SHA256, MODELS, RESOURCE_DIR, SOURCE_REPOSITORY, SOURCE_REVISION,
)


def obtain(path, source_path, expected, verify_only=False):
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
        return
    if verify_only:
        raise RuntimeError(f"Missing or changed learned-policy artifact: {path.name}")
    url = f"https://raw.githubusercontent.com/Rolv-Arild/Necto/{SOURCE_REVISION}/{source_path}"
    request = urllib.request.Request(url, headers={"User-Agent": "MyCareerTraining-build"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"Upstream learned-policy artifact failed integrity verification: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".provider-", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Verify without network access or changes")
    args = parser.parse_args()
    obtain(RESOURCE_DIR / "LICENSE-Necto.txt", "LICENSE", LICENSE_SHA256, args.verify)
    receipt = {"source": SOURCE_REPOSITORY, "revision": SOURCE_REVISION,
               "license": "CC-BY-NC-SA-4.0", "license_sha256": LICENSE_SHA256, "models": []}
    for provider_id, model in MODELS.items():
        target = RESOURCE_DIR / model["filename"]
        obtain(target, model["source_path"], model["sha256"], args.verify)
        receipt["models"].append({"id": provider_id, "file": model["filename"],
                                  "sha256": model["sha256"], "size": target.stat().st_size})
    if not args.verify:
        (RESOURCE_DIR / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verified": True, **receipt}))


if __name__ == "__main__":
    main()
