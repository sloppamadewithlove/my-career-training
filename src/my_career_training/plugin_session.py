"""Bound BakkesMod's MyCareerTraining plugin files to one owned offline launch.

BakkesMod's primary documentation loads a plugin for the current console with
`plugin load <name>` and autoloads anything listed in cfg/plugins.cfg. There is
no documented external console or injector flag for a one-shot load, so this
session appends that autoload line only after saving the exact previous bytes
and removes just the owned change when Rocket League is not running.
"""
from __future__ import annotations

from functools import wraps
import hashlib
import json
from pathlib import Path
import stat

from .storage import Store


SCHEMA = 1
JOURNAL_DIRNAME = "plugin-session"
RECEIPT_NAME = "active.json"
REPORT_NAME = "last-report.json"
DLL_NAME = "MyCareerTraining.dll"
COMMAND = "plugin load MyCareerTraining"
OWNED_COMMAND = "plugin load mycareertraining"
DLL_BACKUP = "MyCareerTraining.dll.prior"
CONFIG_BACKUP = "plugins.cfg.prior"
MAX_CONFIG_BYTES = 1024 * 1024
MAX_DLL_BYTES = 32 * 1024 * 1024

_UNREADABLE = (
    "The My Career plugin session record is unreadable. BakkesMod files were not changed. "
    "The record was left in place."
)
_OUTSTANDING_GAME = (
    "Rocket League is still open from an unfinished My Career plugin session. "
    "My Career will not change BakkesMod files and will not start another session until that game is closed."
)
_CLOSE_GAME = "Close the existing Rocket League window before launching My Career offline."
_LEGACY_CONFIG = (
    "BakkesMod's plugins.cfg already loads MyCareerTraining. My Career did not remove that line "
    "because this session did not create it. Remove the MyCareerTraining load line from BakkesMod's "
    "cfg/plugins.cfg if the plugin should not autoload outside this career."
)


class PluginSessionError(RuntimeError):
    """A BakkesMod plugin session could not be applied or restored safely."""


def _file_errors(method):
    @wraps(method)
    def checked(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (OSError, ValueError, TypeError) as exc:
            raise PluginSessionError(
                f"The plugin file operation could not finish. Recovery records were kept. "
                f"Close Rocket League before retrying: {exc}") from exc
    return checked


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rocket_league_running() -> bool:
    from .platforms import game_processes
    return bool(game_processes())


def _lines(data: bytes) -> list[bytes]:
    lines = []
    start = 0
    index = 0
    while index < len(data):
        if data.startswith(b"\r\n", index):
            index += 2
            lines.append(data[start:index])
            start = index
        elif data[index] in (10, 13):
            index += 1
            lines.append(data[start:index])
            start = index
        else:
            index += 1
    if start < len(data):
        lines.append(data[start:])
    return lines


def _line_text(line: bytes) -> str | None:
    try:
        text = line.rstrip(b"\r\n").decode("utf-8")
    except UnicodeError:
        return None
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def _command_parts(text: str) -> list[str]:
    code = text.split("//", 1)[0].strip()
    if not code:
        return []
    return [" ".join(part.split()) for part in code.split(";") if part.strip()]


def _has_active_owned_command(data: bytes) -> bool:
    for line in _lines(data):
        text = _line_text(line)
        if text is not None and any(part.lower() == OWNED_COMMAND for part in _command_parts(text)):
            return True
    return False


def _sole_owned_indexes(data: bytes) -> list[int] | None:
    indexes = []
    for index, line in enumerate(_lines(data)):
        text = _line_text(line)
        if text is None:
            continue
        parts = _command_parts(text)
        if line == COMMAND.encode("utf-8") + b"\n":
            indexes.append(index)
        elif any(part.lower() == OWNED_COMMAND for part in parts):
            return None
    return indexes


def _insertion(prior: bytes) -> bytes:
    extra = b""
    if prior and not prior.endswith((b"\n", b"\r")):
        extra += b"\n"
    extra += COMMAND.encode("utf-8") + b"\n"
    return extra


def _remove_owned_line(current: bytes, prior: bytes, existed: bool) -> bytes | None:
    indexes = _sole_owned_indexes(current)
    if indexes is None or len(indexes) != 1:
        return None
    lines = _lines(current)
    updated = b"".join(lines[:indexes[0]] + lines[indexes[0] + 1:])
    if existed and not prior.endswith((b"\n", b"\r")) and updated == prior + b"\n":
        return prior
    return updated


class PluginSession:
    def __init__(self, directory=None, *, root=None, game_running=None):
        from .storage import data_dir
        self.base = Path(directory) if directory is not None else data_dir()
        self.journal = self.base / JOURNAL_DIRNAME
        self.receipt_path = self.journal / RECEIPT_NAME
        self.report_path = self.journal / REPORT_NAME
        self.root = None if root is None else Path(root)
        self.game_running = game_running or _rocket_league_running

    def outstanding(self) -> bool:
        return self.receipt_path.is_file()

    def notices(self) -> list[str]:
        if not self.report_path.is_file():
            return []
        try:
            data = json.loads(self.report_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        messages = data.get("remediation") if isinstance(data, dict) else None
        if not isinstance(messages, list):
            return []
        return [item for item in messages if isinstance(item, str) and item]

    @_file_errors
    def begin(self, source_dll) -> dict:
        if self.game_running():
            raise PluginSessionError(_OUTSTANDING_GAME if self.outstanding() else _CLOSE_GAME)
        if self.outstanding():
            self.recover()
        if self.root is None:
            raise PluginSessionError(
                "Install BakkesMod from https://bakkesmod.com, open it once, then launch My Career again.")
        root = self._prepare_root(self.root).resolve()
        source = Path(source_dll)
        if not source.is_file() or source.is_symlink():
            raise PluginSessionError(
                "The in-game plugin is not built here. Install the Windows package from this release.")
        source_bytes = self._read_limited(source, MAX_DLL_BYTES, "in-game plugin")
        if not source_bytes:
            raise PluginSessionError("The in-game plugin failed its integrity check. Reinstall this build.")

        dll_path = root / "plugins" / DLL_NAME
        config_path = root / "cfg" / "plugins.cfg"
        dll_current = self._read_limited(dll_path, MAX_DLL_BYTES, DLL_NAME) if dll_path.exists() else None
        config_current = self._read_limited(config_path, MAX_CONFIG_BYTES, "plugins.cfg") if config_path.exists() else None
        resources = []
        remediation = []
        if dll_current != source_bytes:
            resources.append(self._resource(
                "dll", dll_path, dll_current, source_bytes, DLL_BACKUP if dll_current is not None else None))
        config_state = "unchanged"
        if config_current is None:
            resources.append(self._resource("config", config_path, None, _insertion(b""), None))
            config_state = "created"
        elif not self._utf8(config_current):
            raise PluginSessionError(
                "BakkesMod's plugins.cfg is not UTF-8. My Career left that file unchanged and cannot "
                "add or remove a load line safely.")
        elif _has_active_owned_command(config_current):
            remediation.append(_LEGACY_CONFIG)
            config_state = "preexisting"
        else:
            resources.append(self._resource(
                "config", config_path, config_current, config_current + _insertion(config_current), CONFIG_BACKUP))
            config_state = "appended"
        if dll_current is None:
            dll_state = "installed"
        elif dll_current == source_bytes:
            dll_state = "unchanged"
        else:
            dll_state = "replaced"
        report = {"status": "prepared", "dll": dll_state, "config": config_state, "remediation": remediation}
        self._write_report(report)
        if not resources:
            return report

        created_dirs = []
        if any(item["kind"] == "config" for item in resources) and not config_path.parent.exists():
            created_dirs.append("cfg")
        self._write_backups(resources)
        receipt = {
            "schema": SCHEMA,
            "bakkes_root": str(root),
            "resources": [
                {key: value for key, value in item.items() if key not in ("session_bytes", "prior_bytes")}
                for item in resources],
            "remediation": remediation,
            "created_dirs": created_dirs,
        }
        self._write_receipt(receipt)
        try:
            if created_dirs:
                config_path.parent.mkdir()
            for item in resources:
                if self.game_running():
                    raise PluginSessionError(_OUTSTANDING_GAME)
                self._replace_if_unchanged(
                    Path(item["path"]), item["prior_bytes"] if item["existed"] else None, item["session_bytes"])
        except Exception:
            try:
                self.finish()
            except PluginSessionError:
                pass
            raise
        return report

    @_file_errors
    def recover(self) -> dict:
        if not self.outstanding():
            return {"status": "idle", "remediation": []}
        if self.game_running():
            raise PluginSessionError(_OUTSTANDING_GAME)
        return self._restore()

    @_file_errors
    def finish(self) -> dict:
        if not self.outstanding():
            return {"status": "idle", "remediation": self.notices()}
        if self.game_running():
            return {"status": "deferred", "remediation": self._receipt().get("remediation", [])}
        return self._restore()

    def _resource(self, kind, path: Path, prior: bytes | None, session: bytes, backup):
        inserted = _insertion(prior or b"") if kind == "config" else None
        return {
            "kind": kind,
            "path": str(path),
            "existed": prior is not None,
            "prior_sha256": _sha256(prior) if prior is not None else None,
            "session_sha256": _sha256(session),
            "backup": backup,
            "inserted_hex": None if inserted is None else inserted.hex(),
            "prior_bytes": prior,
            "session_bytes": session,
        }

    def _prepare_root(self, root: Path) -> Path:
        self._reject_link(root, "folder")
        if not root.is_dir():
            raise PluginSessionError(
                "Install BakkesMod from https://bakkesmod.com, open it once, then launch My Career again.")
        plugins = root / "plugins"
        self._reject_link(plugins, "plugins folder")
        if not plugins.is_dir():
            raise PluginSessionError(
                "Install BakkesMod from https://bakkesmod.com, open it once, then launch My Career again.")
        cfg = root / "cfg"
        if cfg.exists() or cfg.is_symlink():
            self._reject_link(cfg, "cfg folder")
            if not cfg.is_dir():
                raise PluginSessionError("BakkesMod's cfg folder is not a directory. My Career left it unchanged.")
        for path, label in ((plugins / DLL_NAME, "plugin file"), (cfg / "plugins.cfg", "plugins.cfg")):
            if path.exists() or path.is_symlink():
                self._reject_link(path, label)
                if path.is_dir():
                    raise PluginSessionError(f"BakkesMod {label} is a directory. My Career left it unchanged.")
            self._require_inside(root, path)
        return root

    def _reject_link(self, path: Path, label: str):
        if path.is_symlink() or (path.exists() and
                getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise PluginSessionError(f"BakkesMod {label} is a link. My Career left it unchanged.")

    def _require_inside(self, root: Path, path: Path):
        try:
            resolved_root = root.resolve()
            resolved = path.resolve()
        except OSError as exc:
            raise PluginSessionError(f"BakkesMod's plugin path could not be checked: {exc}") from exc
        if resolved != resolved_root and resolved_root not in resolved.parents:
            raise PluginSessionError("BakkesMod's plugin path is outside its folder. My Career left it unchanged.")

    def _read_limited(self, path: Path, limit: int, label: str) -> bytes:
        if path.is_symlink() or not path.is_file():
            raise PluginSessionError(f"BakkesMod {label} could not be read. My Career left it unchanged.")
        if path.stat().st_size > limit:
            raise PluginSessionError(
                f"BakkesMod {label} is too large for a safe temporary setup. My Career left it unchanged.")
        return path.read_bytes()

    def _utf8(self, data: bytes) -> bool:
        try:
            data.decode("utf-8")
        except UnicodeError:
            return False
        return True

    def _write_report(self, report: dict):
        self.journal.mkdir(parents=True, exist_ok=True)
        Store._atomic(self.report_path, json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"))

    def _write_receipt(self, receipt: dict):
        self.journal.mkdir(parents=True, exist_ok=True)
        Store._atomic(self.receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2).encode("utf-8"))

    def _write_backups(self, resources: list[dict]):
        self.journal.mkdir(parents=True, exist_ok=True)
        for record in resources:
            if not record["existed"]:
                continue
            backup = self.journal / record["backup"]
            Store._atomic(backup, record["prior_bytes"])
            if _sha256(backup.read_bytes()) != record["prior_sha256"]:
                raise PluginSessionError(
                    "Could not save the existing BakkesMod file before replacing it. Nothing else was switched over.")

    def _receipt(self) -> dict:
        try:
            data = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PluginSessionError(_UNREADABLE) from exc
        if (not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("bakkes_root"), str)
                or not Path(data["bakkes_root"]).is_absolute() or not isinstance(data.get("resources"), list)
                or not data["resources"]):
            raise PluginSessionError(_UNREADABLE)
        if data.get("created_dirs") not in (None, [], ["cfg"]):
            raise PluginSessionError(_UNREADABLE)
        root = Path(data["bakkes_root"])
        expected = {"dll": root / "plugins" / DLL_NAME, "config": root / "cfg" / "plugins.cfg"}
        seen = set()
        for record in data["resources"]:
            if not isinstance(record, dict):
                raise PluginSessionError(_UNREADABLE)
            kind = record.get("kind")
            if kind not in expected or kind in seen or Path(record.get("path", "")) != expected[kind]:
                raise PluginSessionError(
                    "The plugin session record points outside the BakkesMod folder. BakkesMod files were not changed.")
            seen.add(kind)
            if type(record.get("existed")) is not bool or not isinstance(record.get("session_sha256"), str):
                raise PluginSessionError(_UNREADABLE)
            if len(record["session_sha256"]) != 64:
                raise PluginSessionError(_UNREADABLE)
            if record["existed"]:
                if record.get("backup") != (DLL_BACKUP if kind == "dll" else CONFIG_BACKUP):
                    raise PluginSessionError(_UNREADABLE)
                if not isinstance(record.get("prior_sha256"), str) or len(record["prior_sha256"]) != 64:
                    raise PluginSessionError(_UNREADABLE)
            elif record.get("backup") is not None or record.get("prior_sha256") is not None:
                raise PluginSessionError(_UNREADABLE)
            if kind == "config":
                inserted = record.get("inserted_hex")
                if not isinstance(inserted, str) or not inserted or any(char not in "0123456789abcdef" for char in inserted):
                    raise PluginSessionError(_UNREADABLE)
                try:
                    bytes.fromhex(inserted)
                except ValueError as exc:
                    raise PluginSessionError(_UNREADABLE) from exc
        messages = data.get("remediation", [])
        if not isinstance(messages, list) or any(not isinstance(item, str) for item in messages):
            raise PluginSessionError(_UNREADABLE)
        return data

    def _restore(self) -> dict:
        receipt = self._receipt()
        root = Path(receipt["bakkes_root"])
        self._reject_link(root, "folder")
        if not root.is_dir():
            raise PluginSessionError(
                f"BakkesMod's folder from the unfinished session is not available. The backup was kept in {self.journal}.")
        unresolved = []
        errors = []
        for record in receipt["resources"]:
            try:
                self._restore_resource(root, record)
            except PluginSessionError as exc:
                unresolved.append(record)
                errors.append(exc)
        if errors:
            receipt["resources"] = unresolved
            self._write_receipt(receipt)
            raise errors[0]
        self.receipt_path.unlink()
        for name in (DLL_BACKUP, CONFIG_BACKUP):
            backup = self.journal / name
            if backup.is_file() and not backup.is_symlink():
                backup.unlink()
        if receipt.get("created_dirs") == ["cfg"]:
            cfg = root / "cfg"
            if cfg.is_dir() and not cfg.is_symlink() and not any(cfg.iterdir()):
                cfg.rmdir()
        return {"status": "restored", "remediation": [item for item in receipt.get("remediation", []) if item]}

    def _restore_resource(self, root: Path, record: dict):
        path = Path(record["path"])
        self._reject_link(path, "plugin file" if record["kind"] == "dll" else "plugins.cfg")
        self._require_inside(root, path)
        prior = self._prior_bytes(record)
        if record["kind"] == "config" and bytes.fromhex(record["inserted_hex"]) != _insertion(prior):
            raise PluginSessionError(
                "The plugin session record does not match the owned plugins.cfg edit. "
                f"BakkesMod files were left unchanged. The previous copy is in {self.journal}.")
        current = path.read_bytes() if path.is_file() else None
        if current is not None and _sha256(current) == record["session_sha256"]:
            replacement = prior if record["existed"] else None
            self._replace_if_unchanged(path, current, replacement)
            return
        if record["existed"] and current is not None and _sha256(current) == record["prior_sha256"]:
            return
        if not record["existed"] and current is None:
            return
        if record["kind"] == "config" and current is not None:
            updated = _remove_owned_line(current, prior, record["existed"])
            if updated is None:
                if not _has_active_owned_command(current):
                    return
                raise PluginSessionError(
                    "plugins.cfg changed during the session and still loads MyCareerTraining in a line this session "
                    f"does not own. The file was left unchanged. The previous copy is in {self.journal}.")
            if updated == current:
                return
            if record["existed"] and updated == prior:
                self._replace_if_unchanged(path, current, prior)
                return
            if not record["existed"] and updated == b"":
                self._replace_if_unchanged(path, current, None)
                return
            self._replace_if_unchanged(path, current, updated)
            return
        if current is None:
            raise PluginSessionError(
                f"{path.name} was removed during the session. My Career did not recreate it. "
                f"The previous copy is in {self.journal}.")
        raise PluginSessionError(
            f"{path.name} changed to a different file during the session. My Career left that file in place. "
            f"The previous copy is in {self.journal}.")

    def _prior_bytes(self, record: dict) -> bytes:
        if not record["existed"]:
            return b""
        backup = self.journal / record["backup"]
        if backup.is_symlink() or not backup.is_file() or backup.parent.resolve() != self.journal.resolve():
            raise PluginSessionError(
                f"The saved BakkesMod backup no longer matches its session record. The backup was kept in {self.journal}.")
        data = backup.read_bytes()
        if _sha256(data) != record["prior_sha256"]:
            raise PluginSessionError(
                f"The saved BakkesMod backup no longer matches its session record. The backup was kept in {self.journal}.")
        return data

    def _replace_if_unchanged(self, path: Path, expected: bytes | None, replacement: bytes | None):
        current = path.read_bytes() if path.is_file() else None
        if current != expected:
            raise PluginSessionError(
                "BakkesMod files changed while My Career was restoring them. Those files were left untouched.")
        if path.is_symlink():
            raise PluginSessionError("BakkesMod plugin path is a link. My Career left it unchanged.")
        if replacement is None:
            if path.is_file():
                if path.read_bytes() != expected:
                    raise PluginSessionError(
                        "BakkesMod files changed while My Career was restoring them. Those files were left untouched.")
                path.unlink()
            return
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise PluginSessionError(
                "BakkesMod's folder changed during recovery. The backup was kept and nothing was written.")
        Store._atomic(path, replacement)
        if path.is_symlink() or path.read_bytes() != replacement:
            raise PluginSessionError(
                "BakkesMod files changed while My Career was writing them. The session journal was kept.")
