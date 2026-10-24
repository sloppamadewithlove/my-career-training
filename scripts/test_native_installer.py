"""Install/reinstall/uninstall the exact native candidate on a clean hosted CI runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from my_career_training.career import new_career
from my_career_training.storage import Store, default_state
from smoke_package import run_smoke
from test_installer import wait_for_uninstaller_log_release
from windows_shortcuts import desktop_folders, programs_folders, read_shortcut

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "My Career Training"
REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{17F0F7CD-13B7-4DBA-82C7-20AFA00D376C}_is1"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def registrations() -> list[tuple[Path, Path]]:
    import winreg
    records = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                key = winreg.OpenKey(hive, REGISTRY_KEY, 0, winreg.KEY_READ | view)
            except FileNotFoundError:
                continue
            with key:
                location = winreg.QueryValueEx(key, "InstallLocation")[0]
                uninstaller = winreg.QueryValueEx(key, "UninstallString")[0]
            records.append((Path(location).resolve(), Path(uninstaller.strip('"')).resolve()))
    return records


def require_owned_registration(install: Path) -> None:
    # HKCU is shared between registry views; duplicate observations are normal.
    records = registrations()
    expected = (install.resolve(), (install / "unins000.exe").resolve())
    if not records or any(record != expected for record in records):
        raise RuntimeError("Installer registration does not exclusively belong to this test")


def check_shortcut(group: str, install: Path) -> set[Path]:
    paths = [item for folder in programs_folders() for item in (folder / group).glob("*.lnk")]
    if len(paths) != 1:
        raise RuntimeError("Expected one player shortcut")
    shortcut = read_shortcut(paths[0])
    if (Path(shortcut["target"]).resolve() != (install / "MyCareerTraining.exe").resolve()
            or shortcut["arguments"]):
        raise RuntimeError("Player shortcut has the wrong target or arguments")
    if any((folder / f"{APP_NAME}.lnk").exists() for folder in desktop_folders()):
        raise RuntimeError("An unrequested desktop shortcut was created")
    return set(paths)


def check_payload(install: Path, files: dict[str, str]) -> None:
    for relative, expected in files.items():
        if digest(install / relative) != expected:
            raise RuntimeError("Installed file differs from the tested bundle")
    actual = {item.relative_to(install).as_posix() for item in install.rglob("*") if item.is_file()}
    allowed = set(files) | {"unins000.exe", "unins000.dat", "unins000.msg"}
    if actual - allowed or (install / "MyCareerTrainingWorker.exe").exists():
        raise RuntimeError("Installer exposed an unexpected file or public Worker")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installer", type=Path)
    args = parser.parse_args()
    if (os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"):
        raise RuntimeError("Run this lifecycle test only on a disposable GitHub-hosted Windows runner")
    installer = args.installer.resolve(strict=True)
    build = json.loads(installer.with_suffix(".json").read_text(encoding="utf-8"))
    if digest(installer) != build["sha256"]:
        raise RuntimeError("Installer differs from its build receipt")
    smoke = json.loads((ROOT / "build/native-menu-candidate-smoke-receipt.json").read_text(encoding="utf-8"))
    if smoke.get("passed") is not True or not smoke.get("bundle_files"):
        raise RuntimeError("Exact package smoke evidence is required")
    if registrations():
        raise RuntimeError("Existing My Career registration must be preserved")
    if any((folder / APP_NAME).exists() for folder in programs_folders()):
        raise RuntimeError("Existing My Career Start Menu group must be preserved")
    if any((folder / f"{APP_NAME}.lnk").exists() for folder in desktop_folders()):
        raise RuntimeError("Existing My Career desktop shortcut must be preserved")
    if (Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_NAME).exists():
        raise RuntimeError("Existing default installation must be preserved")

    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    token = uuid.uuid4().hex
    root = runner_temp / ("mct-native-install-" + token)
    root.mkdir(exist_ok=False)
    if root.resolve().parent != runner_temp or root.is_symlink():
        raise RuntimeError("Test directory is outside the runner temporary directory")
    install = root / "Installed app é 球"
    profile = root / "AppData saves é 球"
    group = "My Career Training CI " + token[:12]
    if any((folder / group).exists() for folder in programs_folders()):
        raise RuntimeError("Unique test shortcut group already exists")
    with Store(profile) as store:
        state = default_state()
        state["career"] = new_career("Existing test player", seed=73)
        store.save(state)
    sentinel = profile / "career.json"
    original = sentinel.read_bytes()
    command = [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
               "/NOCLOSEAPPLICATIONS", "/TASKS=!desktopicon", f"/GROUP={group}",
               f"/DIR={install}", f"/LOG={root / 'install.log'}"]
    evidence = {"passed": False, "source_commit": build["source_commit"],
                "installer_sha256": build["sha256"], "gameplay_verified": False,
                "production_ready": False, "previous_release_upgrade_verified": False}
    stage = "install"
    try:
        subprocess.run(command, check=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
        require_owned_registration(install)
        check_payload(install, smoke["bundle_files"])
        shortcuts = check_shortcut(group, install)
        stage = "installed package smoke"
        run_smoke(install, profile)
        assert sentinel.read_bytes() == original, "Installed app changed the existing career"
        stage = "reinstall and obsolete helper cleanup"
        # This inert file simulates the former public helper; it is never run.
        (install / "MyCareerTrainingWorker.exe").write_bytes(b"inert migration test sentinel")
        subprocess.run(command, check=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
        require_owned_registration(install)
        check_payload(install, smoke["bundle_files"])
        assert check_shortcut(group, install) == shortcuts, "Reinstall duplicated shortcuts"
        assert sentinel.read_bytes() == original, "Reinstall changed the existing career"
        stage = "uninstall"
        require_owned_registration(install)
        if install.resolve().parent != root.resolve() or install.is_symlink():
            raise RuntimeError("Uninstaller target no longer belongs to this test")
        uninstall_log = root / "uninstall.log"
        subprocess.run([str(install / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                        "/NORESTART", f"/LOG={uninstall_log}"], check=True, timeout=180,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        wait_for_uninstaller_log_release(uninstall_log)
        assert not registrations(), "Uninstall left a registration"
        assert not (install / "MyCareerTraining.exe").exists(), "Uninstall left the player app"
        assert not any(path.exists() for path in shortcuts), "Uninstall left its shortcut"
        assert sentinel.read_bytes() == original, "Uninstall changed the existing career"
        assert digest(installer) == build["sha256"], "Installer changed during testing"
        evidence.update(passed=True, installer_lifecycle_verified=True,
                        checks=["silent install", "one player shortcut", "complete installed file hashes",
                                "installed package smoke", "same-version reinstall",
                                "obsolete public helper cleanup", "uninstall", "career bytes preserved"])
        print("Native installer lifecycle passed; gameplay remains unverified")
        return 0
    except Exception as error:
        evidence.update(failure_stage=stage, failure_type=type(error).__name__)
        print(f"Native installer lifecycle failed at {stage}; private runner state retained for diagnosis")
        return 1
    finally:
        destination = ROOT / "build/native-installer-lifecycle.json"
        destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
