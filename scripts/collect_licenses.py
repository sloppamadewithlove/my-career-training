"""Collect installed dependency notices into the binary distribution."""
from __future__ import annotations

from importlib import metadata
import json
import hashlib
import tarfile
import sys
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "packaging" / "licenses"
SOURCES = ROOT / "build" / "upstream-sources"
# Immutable commits corresponding to the exact bundled release versions.
UPSTREAM = {
    "qtbase": ("qt/qtbase", "025bdad181de241e81bf853c8a2d7bf3d19261a9"),
    "qtsvg": ("qt/qtsvg", "883a58532078d003cefef0a549bfe9f885ce41f5"),
    "qtdeclarative": ("qt/qtdeclarative", "4332fbbb4c340463dc8cee36dda0c85d932122d8"),
    "qtshadertools": ("qt/qtshadertools", "bccd516b990a6396900051470ac86cc27a7042ea"),
    "pyside-setup": ("pyside/pyside-setup", "f50facb83fc3dc5f3240c854668c7a6dd93871b2"),
    "pygame-ce": ("pygame-community/pygame-ce", "a17caaef2ae155713b0f6de77cbb4998446e8b2e"),
}


def collect_upstream() -> None:
    SOURCES.mkdir(parents=True, exist_ok=True)
    sources = []
    for name, (repository, commit) in UPSTREAM.items():
        url = f"https://codeload.github.com/{repository}/tar.gz/{commit}"
        archive = SOURCES / f"{name}-{commit}.tar.gz"
        if not archive.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "my-career-training-build"})
            temporary = archive.with_suffix('.download')
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output)
            temporary.replace(archive)
        with tarfile.open(archive, 'r:gz') as source:
            for member in source:
                if not member.isfile():
                    continue
                relative = Path(*Path(member.name).parts[1:])
                if '..' in relative.parts or relative.is_absolute():
                    raise RuntimeError('Unsafe upstream source path')
                lower = str(relative).lower()
                wanted = (any(token in relative.name.lower()
                              for token in ('license', 'copying', 'notice', 'copyright'))
                          or 'licenses/' in lower or relative.name == 'qt_attribution.json'
                          or ('3rdparty/' in lower and relative.suffix in ('.txt', '.md', '.json')))
                if wanted:
                    target = DESTINATION / 'upstream' / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as input_file, target.open('wb') as output:
                        shutil.copyfileobj(input_file, output)
        with archive.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        sources.append({'component': name, 'repository': repository, 'commit': commit,
                        'source_url': url, 'archive': archive.name, 'sha256': digest})
    (SOURCES / 'SOURCE_MANIFEST.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    (DESTINATION / 'SOURCE_MANIFEST.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    for candidate in (Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'LICENSE'):
        if candidate.is_file():
            shutil.copyfile(candidate, DESTINATION / 'Python-LICENSE.txt')
            break



def main() -> int:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    collect_upstream()
    packages = []
    for distribution in sorted(metadata.distributions(), key=lambda item: item.metadata['Name'].lower()):
        name = distribution.metadata['Name']
        output = DESTINATION / name
        copied = []
        for item in distribution.files or []:
            # Include .dist-info/licenses, license files distributed inside Qt/PySide,
            # Python-package notices and SDL/pygame notices; retain their path.
            if any(part.lower().startswith(('license', 'copying', 'notice', 'copyright'))
                   for part in item.parts):
                source = Path(distribution.locate_file(item))
                if source.is_file() and source.suffix not in ('.py', '.pyc'):
                    relative = Path(*[part for part in item.parts if part not in ('..', '.')])
                    target = output / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    copied.append(str(relative))
        packages.append({'name': name, 'version': distribution.version,
                         'license': distribution.metadata.get('License-Expression') or
                                    distribution.metadata.get('License', ''),
                         'notices': copied})
    # Core is not a Python distribution. Preserve its exact MIT license separately.
    url = 'https://raw.githubusercontent.com/RLBot/core/v5.0.0-rc18/LICENSE'
    with urllib.request.urlopen(url, timeout=30) as response:
        text = response.read().decode('utf-8')
    if 'MIT License' not in text or 'RLBot Contributors' not in text:
        raise RuntimeError('Unexpected RLBot core license; review before packaging')
    (DESTINATION / 'RLBot-core-LICENSE.txt').write_text(text, encoding='utf-8')
    (DESTINATION / 'dependency-manifest.json').write_text(
        json.dumps(packages, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Collected license material from {len(packages)} distributions')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
