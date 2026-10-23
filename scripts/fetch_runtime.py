"""Fetch the exact redistributable RLBot core; never execute downloaded content."""
from __future__ import annotations

import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v5.0.0-rc18"
URL = f"https://github.com/RLBot/core/releases/download/{VERSION}/RLBotServer.exe"
SHA256 = "454986c71bacebfcb923a8eeddba7ea62ecc6c42d28b4cab89f653e2eab1ccd1"


def main() -> int:
    destination = ROOT / "runtime" / "RLBotServer.exe"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == SHA256:
        print(f"RLBot core {VERSION}: existing hash verified")
        return 0
    request = urllib.request.Request(URL, headers={"User-Agent": "my-career-training-build"})
    with urllib.request.urlopen(request, timeout=120) as response:
        content = response.read(100 * 1024 * 1024 + 1)
    if len(content) > 100 * 1024 * 1024 or not content.startswith(b"MZ"):
        raise RuntimeError("The core download is not an expected Windows executable")
    if hashlib.sha256(content).hexdigest() != SHA256:
        raise RuntimeError("RLBot core checksum mismatch; refusing this download")
    temporary = destination.with_suffix(".download")
    temporary.write_bytes(content)
    temporary.replace(destination)
    print(f"RLBot core {VERSION}: downloaded and hash verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
