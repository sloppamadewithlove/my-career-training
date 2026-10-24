"""Build a private development RootMenu candidate from an owned menu movie.

The caller passes every source, output, and tool path. With no arguments the
process prints help and does not read a movie. Nothing here launches a game,
writes an installed package, or embeds a package key.

FFDec's AS3 pcode replace keeps the method body it is given and does not
recompute maxstack, localcount, or scope depths. This generator writes those
fields itself: local count and both scope depths stay at the pinned originals,
and maxstack is raised only when the new instructions need it.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import zlib

PINNED_SHA256 = "57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0"
CLASS_NAME = "menus.RootMenu"
PINNED_PRIVATE_NS = 'PrivateNamespace(null,"67")'
PINNED_CREATE_NS = 'ProtectedNamespace("tagame.menus:BranchingMenu")'
PINNED_SCOPE = (15, 16)
MAX_MOVIE_BYTES = 8 * 1024 * 1024
MAX_TAGS = 100_000
DOABC = 82
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

# body index, method index, original maxstack, original localcount
PINNED_METHODS = {
    "generateControls": (11257, 11397, 11, 5),
    "openPlayMenu": (11273, 11413, 2, 1),
    "tryOpenShopMainMenu": (11268, 11408, 2, 1),
    "openProfileMenu": (11274, 11414, 4, 1),
    "tryOpenRocketPassScreen": (11264, 11404, 2, 1),
    "processReturnEvents": (11258, 11398, 6, 2),
    "updateIcons": (11260, 11400, 4, 4),
    "updateItemShopBreadcrumb": (11261, 11401, 3, 1),
    "updateEsportEvents": (11253, 11393, 3, 5),
    "updateEsportLogoImage": (11262, 11402, 2, 1),
    "refreshEsportLogoImage": (11263, 11403, 4, 3),
    "updateClubButton": (11277, 11417, 3, 7),
    "syncLocalClub": (11279, 11419, 2, 1),
}

TRIGGER_CODES = {
    "openPlayMenu": "MCT_CAREER",
    "tryOpenShopMainMenu": "MCT_TRAINING",
    "openProfileMenu": "MCT_WORKSHOP",
    "tryOpenRocketPassScreen": "MCT_COMMUNITY",
}

NO_OP_REASONS = {
    "processReturnEvents": "auto-opens stock play, season, tournament, and training routes",
    "updateIcons": "decorates the repurposed buttons and queries online product state",
    "updateItemShopBreadcrumb": "decorates the training button when the shop catalogue changes",
    "updateEsportEvents": "loads live esports rows that the stock menu turns into a button",
    "updateEsportLogoImage": "downloads an esports image and attaches it to a menu button",
    "refreshEsportLogoImage": "paints that downloaded esports image onto a menu button",
    "updateClubButton": "invalidates the menu and would bring a club control back",
    "syncLocalClub": "asks the privileges manager to go online",
}

CONTROLS = (
    {
        "label": "My Career",
        "description": "MY CAREER",
        "suffix": "_career",
        "field": "m_playButton",
        "callback": ("property", "openPlayMenu"),
        "focus": True,
    },
    {
        "label": "Training",
        "description": "TRAINING",
        "suffix": "_training",
        "field": "m_itemShopButton",
        "callback": ("property", "tryOpenShopMainMenu"),
        "focus": False,
    },
    {
        "label": "Garage",
        "description": "GARAGE",
        "suffix": "_garage",
        "field": "m_garageButton",
        "callback": ("property", "openGarageSelectionMenu"),
        "focus": False,
    },
    {
        "label": "Workshop",
        "description": "WORKSHOP",
        "suffix": "_workshop",
        "field": "m_profileButton",
        "callback": ("property", "openProfileMenu"),
        "focus": False,
    },
    {
        "label": "Community",
        "description": "COMMUNITY",
        "suffix": "_community",
        "field": "m_rocketPassButton",
        "callback": ("property", "tryOpenRocketPassScreen"),
        "focus": False,
    },
    {
        "label": "Settings",
        "description": "SETTINGS",
        "suffix": "_settings",
        "field": "m_optionsButton",
        "callback": ("property", "openOptionsMenu"),
        "focus": False,
    },
    {
        "label": "Exit",
        "description": "EXIT",
        "suffix": "_exit",
        "field": "m_quitButton",
        "callback": ("exit", "ExitGame"),
        "focus": False,
    },
)

PRESERVED_METHODS = (
    "openGarageSelectionMenu",
    "openOptionsMenu",
    "openGarageMenu",
    "tryRegenerateControlsOnTimerComplete",
)

# Stock routes that remain in the movie and are not bound to the seven controls.
UNTOUCHED_ONLINE_METHODS = (
    "openShopMainMenu",
    "openRocketPassScreen",
    "openPlayNow",
    "openEsportsLink",
    "openClubMenu",
    "openCreateClubModal",
)

REQUIRED_MOVIE_IDENTIFIERS = (b"MenuStack", b"ButtonTriggered", b"ExitGame")
RETRY_DELAY_MS = 1000
RETRY_REPEAT_COUNT = 10

HELP = """\
Build a private seven-control RootMenu candidate.

With no arguments this prints help and does not read a movie, a package, or an
installed game. Every path is explicit. The candidate is a new file outside the
repository. It is not loaded into Rocket League.

  native_menu_patch.py plan --actionscript AS --pcode PCODE
  native_menu_patch.py build --source GFX --actionscript AS --pcode PCODE
      --output GFX --java JAVA --ffdec JAR --ffdec-home DIR --work-dir DIR

plan reads only the two local text exports and prints method ids and stack
peaks. build refuses an input whose SHA-256 is not the pinned movie, refuses
an in-place write, a reparse point, or a path inside an installed game, and
fails before creating the candidate when the menus.RootMenu body ids differ.
"""


class CandidateRejected(ValueError):
    """The candidate was not written because an identity or path check failed."""


def capabilities() -> dict:
    """Status flags. A constructed candidate is still not a runtime or production result."""
    return {
        "constructed": False,
        "runtime_verified": False,
        "production": False,
        "launches_game": False,
        "writes_installed_package": False,
    }


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0
    parser = argparse.ArgumentParser(prog="native_menu_patch.py", add_help=True)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="print method ids and stack peaks")
    plan.add_argument("--actionscript", required=True, type=Path)
    plan.add_argument("--pcode", required=True, type=Path)
    build = sub.add_parser("build", help="write one private candidate")
    build.add_argument("--source", required=True, type=Path)
    build.add_argument("--actionscript", required=True, type=Path)
    build.add_argument("--pcode", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--java", required=True, type=Path)
    build.add_argument("--ffdec", required=True, type=Path)
    build.add_argument("--ffdec-home", required=True, type=Path)
    build.add_argument("--work-dir", required=True, type=Path)
    parsed = parser.parse_args(arguments)
    if parsed.command == "plan":
        plans = plan_replacements(
            _read_text(parsed.actionscript),
            _read_text(parsed.pcode),
        )
        json.dump(_plan_summary(plans), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    manifest = build_candidate(
        source_gfx=parsed.source,
        actionscript=parsed.actionscript,
        pcode=parsed.pcode,
        output_gfx=parsed.output,
        java=parsed.java,
        ffdec_jar=parsed.ffdec,
        ffdec_home=parsed.ffdec_home,
        work_dir=parsed.work_dir,
    )
    json.dump(manifest, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def build_candidate(
    source_gfx,
    actionscript,
    pcode,
    output_gfx,
    java,
    ffdec_jar,
    ffdec_home,
    work_dir,
) -> dict:
    """Validate, replace the selected bodies, and write a private manifest.

    Identity or path failures raise before the candidate file is created.
    """
    source = Path(source_gfx)
    output = Path(output_gfx)
    script_path = Path(actionscript)
    pcode_path = Path(pcode)
    java_path = Path(java)
    jar_path = Path(ffdec_jar)
    home = Path(ffdec_home)
    work = Path(work_dir)
    reject_paths(source, output, work, java_path, jar_path, home)
    movie = _read_bytes(source)
    digest = hashlib.sha256(movie).hexdigest()
    if digest != PINNED_SHA256:
        raise CandidateRejected("source movie hash does not match the pinned MainMenu.gfx")
    for identifier in REQUIRED_MOVIE_IDENTIFIERS:
        if identifier not in movie:
            raise CandidateRejected(f"source movie is missing {identifier.decode('ascii')}")
    plans = plan_replacements(_read_text(script_path), _read_text(pcode_path))
    for tool in (java_path, jar_path):
        if not tool.is_file() or _is_reparse(tool):
            raise CandidateRejected(f"tool path is not an ordinary file: {tool.name}")
    _require_ordinary_ancestors(home)
    home.mkdir(parents=True, exist_ok=True)
    _require_ordinary_ancestors(work)
    work.mkdir(parents=True, exist_ok=True)
    pcode_dir = work / "method-pcode"
    pcode_dir.mkdir(parents=True, exist_ok=True)
    args_path = work / "ffdec-replace.txt"
    lines = []
    for name, plan in plans.items():
        method_path = pcode_dir / f"{name}.pcode"
        method_path.write_text(plan["pcode"], encoding="utf-8", newline="\n")
        lines.extend([CLASS_NAME, str(method_path), str(plan["body_index"])])
    args_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if _is_reparse(output) or output.is_symlink():
            raise CandidateRejected("output path is a reparse point")
        output.unlink()
    try:
        _run_ffdec(
            java_path,
            jar_path,
            home,
            ["-replace", str(source), str(output), str(args_path)],
        )
        if not output.is_file() or _is_reparse(output):
            raise CandidateRejected("FFDec did not leave an ordinary candidate file")
        comparison = compare_swf_tags(movie, _read_bytes(output))
        if not comparison["only_doabc_and_header_length_changed"]:
            raise CandidateRejected("candidate changed a SWF tag other than DoABC or the header length")
        as_dir = work / "verify-as"
        pcode_out = work / "verify-pcode"
        _export_script(java_path, jar_path, home, output, as_dir, "script:as", method_ids=True)
        _export_script(java_path, jar_path, home, output, pcode_out, "script:pcode", method_ids=False)
        actionscript_text = _find_export(as_dir, ".as")
        pcode_text = _find_export(pcode_out, ".pcode")
        verification = verify_exported_candidate(actionscript_text, pcode_text)
    except CandidateRejected:
        if output.exists() and not _same_file(source, output):
            output.unlink(missing_ok=True)
        raise
    manifest = {
        "constructed": True,
        "runtime_verified": False,
        "production": False,
        "class_name": CLASS_NAME,
        "input_sha256": digest,
        "output_sha256": hashlib.sha256(_read_bytes(output)).hexdigest(),
        "output_path": str(output),
        "methods": [_public_method(plan) for plan in plans.values()],
        "controls": [
            {
                "label": item["label"],
                "field": item["field"],
                "callback": item["callback"][1],
                "trigger": TRIGGER_CODES.get(item["callback"][1]),
            }
            for item in CONTROLS
        ],
        "noop_helpers": [{"name": name, "reason": reason} for name, reason in NO_OP_REASONS.items()],
        "preserved_methods": list(PRESERVED_METHODS),
        "untouched_online_methods": list(UNTOUCHED_ONLINE_METHODS),
        "swf": comparison,
        "verification": verification,
        "integration_blockers": list(INTEGRATION_BLOCKERS),
    }
    manifest_path = output.parent / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


INTEGRATION_BLOCKERS = (
    "The candidate file is not installed and has not been shown in Rocket League.",
    "MenuStack.ButtonTriggered is emitted for four new strings. The native host does not route them yet.",
    "Exit calls the existing Shell.ExitGame callback. It does not dispatch bridge quit_game.",
    "Garage and options still use their existing RootMenu bodies.",
    "handleAddedToStage still registers shop, pass, club, esports, news, ban, and tutorial listeners.",
    "Stock shop, pass, play-now, esports, and club methods remain in the movie and are not bound to these buttons.",
    "Other native online hotkeys are not disabled.",
    "Literal labels are not localized, and no controller or visual pass has been run.",
)


def plan_replacements(actionscript: str, pcode: str) -> dict:
    """Return rendered single-method pcode keyed by method name.

    Raises before any candidate bytes exist when the class or body ids do not match.
    """
    if _package_name(actionscript) != "menus" or _class_name(actionscript) != "RootMenu":
        raise CandidateRejected("actionscript is not menus.RootMenu")
    if _package_name(pcode) != "menus" or _class_name(pcode) != "RootMenu":
        raise CandidateRejected("pcode is not menus.RootMenu")
    if PINNED_PRIVATE_NS not in pcode or PINNED_CREATE_NS not in pcode:
        raise CandidateRejected("pcode namespaces do not match the pinned RootMenu movie")
    indexed = parse_method_index(actionscript)
    bodies = {}
    for name, (body_index, method_index, maxstack, localcount) in PINNED_METHODS.items():
        found = indexed.get(name)
        if found is None:
            raise CandidateRejected(f"{name} is missing from the actionscript export")
        if found != (body_index, method_index):
            raise CandidateRejected(f"{name} body id does not match the pinned movie")
        if sum(1 for item in indexed.values() if item[0] == body_index) != 1:
            raise CandidateRejected(f"{name} body id is not unique")
        extracted = extract_method(pcode, name)
        stats = extracted["stats"]
        if (stats["initscopedepth"], stats["maxscopedepth"]) != PINNED_SCOPE:
            raise CandidateRejected(f"{name} scope depth does not match the pinned movie")
        if stats["maxstack"] != maxstack or stats["localcount"] != localcount:
            raise CandidateRejected(f"{name} stack or local count does not match the pinned movie")
        instructions = method_instructions(name)
        peak = analyze_stack(instructions)
        if peak > 65535:
            raise CandidateRejected(f"{name} stack peak is not encodable")
        _reject_forbidden_operations(name, instructions)
        rendered_stack = max(maxstack, peak)
        bodies[name] = {
            "name": name,
            "body_index": body_index,
            "method_index": method_index,
            "original_maxstack": maxstack,
            "maxstack": rendered_stack,
            "stack_peak": peak,
            "localcount": localcount,
            "initscopedepth": stats["initscopedepth"],
            "maxscopedepth": stats["maxscopedepth"],
            "kind": _method_kind(name),
            "pcode": render_method(extracted, instructions, rendered_stack),
        }
    return bodies


def parse_method_index(actionscript: str) -> dict:
    """Map each function name to its unique `(body index, method index)` pair."""
    current = None
    found: dict[str, tuple[int, int]] = {}
    comment = re.compile(r"method body index:\s*(\d+)\s+method index:\s*(\d+)")
    for line in actionscript.splitlines():
        function = re.search(r"\bfunction\s+(\w+)\s*\(", line)
        if function:
            current = function.group(1)
        match = comment.search(line)
        if match is None or current is None:
            continue
        key = (int(match.group(1)), int(match.group(2)))
        if current in found and found[current] != key:
            raise CandidateRejected(f"{current} has more than one method body id")
        found[current] = key
        current = None
    selected = [found[name][0] for name in PINNED_METHODS if name in found]
    if len(selected) != len(set(selected)):
        raise CandidateRejected("selected method body ids are not unique")
    return found


def extract_method(pcode: str, name: str) -> dict:
    """Isolate one method's trait, signature, and body stats from an FFDec pcode export."""
    lines = pcode.splitlines()
    starts = [
        index for index, line in enumerate(lines) if re.search(rf"\bfunction\s+{re.escape(name)}\s*\(", line)
    ]
    if len(starts) != 1:
        raise CandidateRejected(f"{name} is not a single pcode method")
    trait = None
    for index in range(starts[0], len(lines)):
        if lines[index].strip().startswith("trait method "):
            trait = index
            break
        if index != starts[0] and re.search(r"\bfunction\s+\w+\s*\(", lines[index]):
            break
    if trait is None:
        raise CandidateRejected(f"{name} has no trait method header")
    end = None
    for index in range(trait, len(lines)):
        if lines[index].strip().startswith("end ; method"):
            end = index
            break
    if end is None:
        raise CandidateRejected(f"{name} method block does not close")
    block = lines[trait : end + 1]
    code_at = next((index for index, line in enumerate(block) if line.strip() == "code"), None)
    end_code = next(
        (index for index, line in enumerate(block) if line.strip().startswith("end ; code")),
        None,
    )
    if code_at is None or end_code is None or end_code < code_at:
        raise CandidateRejected(f"{name} has no isolated code section")
    prologue = block[:code_at]
    if any(line.strip().startswith("trait ") for line in prologue if "trait method" not in line):
        raise CandidateRejected(f"{name} has a body trait this candidate does not rewrite")
    stats = {}
    for key in ("maxstack", "localcount", "initscopedepth", "maxscopedepth"):
        values = [int(item) for item in re.findall(rf"(?m)^\s*{key}\s+(\d+)\s*$", "\n".join(prologue))]
        if len(values) != 1:
            raise CandidateRejected(f"{name} {key} is not unique")
        stats[key] = values[0]
    return {"header": block[: code_at + 1], "tail": block[end_code:], "stats": stats}


def render_method(extracted: dict, instructions: list[tuple], maxstack: int) -> str:
    header = []
    replaced = False
    for line in extracted["header"]:
        if re.fullmatch(r"\s*maxstack\s+\d+\s*", line):
            indent = re.match(r"\s*", line).group(0)
            header.append(f"{indent}maxstack {maxstack}")
            replaced = True
        else:
            header.append(line)
    if not replaced:
        raise CandidateRejected("method header has no maxstack field")
    rendered = header + [format_instruction(op) for op in instructions] + list(extracted["tail"])
    text = "\n".join(rendered) + "\n"
    if "\ncode\n" not in "\n" + text:
        # The header keeps its original indentation; the code keyword is still present.
        if not any(line.strip() == "code" for line in rendered):
            raise CandidateRejected("rendered method lost its code section")
    return text


def method_instructions(name: str) -> list[tuple]:
    if name == "generateControls":
        return generate_controls_instructions()
    if name in TRIGGER_CODES:
        return trigger_instructions(TRIGGER_CODES[name])
    if name in NO_OP_REASONS:
        return noop_instructions()
    raise CandidateRejected(f"{name} has no candidate body")


def generate_controls_instructions() -> list[tuple]:
    """Seven native controls, plus the existing null-shell retry.

    handleAddedToStage refreshes through the parent menu, which destroys and
    regenerates controls. The shell reference can still be null there, so this
    body starts the movie's existing one-shot retry instead of building buttons.
    """
    private = PINNED_PRIVATE_NS
    ops = [
        ("getlocal0",),
        ("pushscope",),
        ("getlocal0",),
        ("getproperty", qname(private, "m_shell")),
        ("pushnull",),
        ("ifne", "shell_ready"),
        ("getlocal0",),
        ("getproperty", qname(private, "m_regenerateControlsTimer")),
        ("pushnull",),
        ("ifne", "timer_waiting"),
        ("getlocal0",),
        ("findpropstrict", qname(package("flash.utils"), "Timer")),
        ("pushshort", RETRY_DELAY_MS),
        ("pushbyte", RETRY_REPEAT_COUNT),
        ("constructprop", qname(package("flash.utils"), "Timer"), 2),
        ("initproperty", qname(private, "m_regenerateControlsTimer")),
        ("getlocal0",),
        ("getproperty", qname(private, "m_regenerateControlsTimer")),
        ("getlex", qname(package("flash.events"), "TimerEvent")),
        ("getproperty", qname(package(""), "TIMER_COMPLETE")),
        ("getlocal0",),
        ("getproperty", qname(private, "tryRegenerateControlsOnTimerComplete")),
        ("callpropvoid", qname(package(""), "addEventListener"), 2),
        ("getlocal0",),
        ("getproperty", qname(private, "m_regenerateControlsTimer")),
        ("callpropvoid", qname(package(""), "start"), 0),
        ("label", "timer_waiting"),
        ("returnvoid",),
        ("label", "shell_ready"),
    ]
    for control in CONTROLS:
        ops.extend(control_instructions(control))
        if control["focus"]:
            ops.extend(focus_instructions(control["field"]))
    ops.append(("returnvoid",))
    return ops


def control_instructions(control: dict) -> list[tuple]:
    private = PINNED_PRIVATE_NS
    create = qname(PINNED_CREATE_NS, "createControl")
    ops = [
        ("getlocal0",),
        ("findpropstrict", create),
        ("pushstring", "label"),
        ("pushstring", control["label"]),
        ("pushstring", "descLabel"),
        ("pushstring", control["description"]),
        ("pushstring", "name"),
        ("getlex", qname(package(""), "menuName")),
        ("pushstring", control["suffix"]),
        ("add",),
        ("newobject", 3),
    ]
    kind, target = control["callback"]
    if kind == "property":
        ops.extend(
            [
                ("getlocal0",),
                ("getproperty", qname(private, target)),
            ]
        )
    elif kind == "exit":
        ops.extend(
            [
                ("getlex", qname(package("tagame.api"), "Shell")),
                ("getproperty", qname(package(""), target)),
            ]
        )
    else:
        raise CandidateRejected(f"unknown control callback {kind}")
    ops.extend(
        [
            ("callproperty", create, 2),
            ("getlex", qname(package("tagame.controls"), "MenuButton")),
            ("astypelate",),
            ("initproperty", qname(private, control["field"])),
            ("getlocal0",),
            ("getproperty", qname(private, control["field"])),
            ("callpropvoid", qname(package(""), "validateNow"), 0),
        ]
    )
    return ops


def focus_instructions(field: str) -> list[tuple]:
    current = qname(package(""), "currentFocus")
    return [
        ("getlex", current),
        ("pushnull",),
        ("ifne", "focus_done"),
        ("findproperty", current),
        ("getlocal0",),
        ("getproperty", qname(PINNED_PRIVATE_NS, field)),
        ("initproperty", current),
        ("label", "focus_done"),
    ]


def trigger_instructions(code: str) -> list[tuple]:
    if code not in TRIGGER_CODES.values():
        raise CandidateRejected("trigger code is not one of the four candidate strings")
    return [
        ("getlocal0",),
        ("pushscope",),
        ("getlex", qname(package("tagame.api"), "MenuStack")),
        ("pushstring", code),
        ("callpropvoid", qname(package(""), "ButtonTriggered"), 1),
        ("returnvoid",),
    ]


def noop_instructions() -> list[tuple]:
    return [("getlocal0",), ("pushscope",), ("returnvoid",)]


def analyze_stack(instructions: list[tuple]) -> int:
    """Return the peak operand-stack depth. Rejects underflow and a dirty return."""
    depth = 0
    peak = 0
    for op in instructions:
        pops, delta = stack_effect(op)
        if op[0] == "label":
            continue
        if depth < pops:
            raise CandidateRejected(f"stack underflow at {op[0]}")
        depth += delta
        peak = max(peak, depth)
        if op[0] == "returnvoid" and depth != 0:
            raise CandidateRejected("returnvoid leaves values on the stack")
    if depth != 0:
        raise CandidateRejected("method does not end with an empty stack")
    return peak


def stack_effect(op: tuple) -> tuple[int, int]:
    """Return `(values popped, net depth change)`."""
    kind = op[0]
    if kind == "label":
        return 0, 0
    if kind in {"getlocal0", "pushnull", "pushstring", "findpropstrict", "findproperty", "getlex"}:
        return 0, 1
    if kind in {"pushbyte", "pushshort", "pushint"}:
        return 0, 1
    if kind == "pushscope":
        return 1, -1
    if kind == "getproperty":
        return 1, 0
    if kind == "initproperty":
        return 2, -2
    if kind == "add":
        return 2, -1
    if kind == "astypelate":
        return 2, -1
    if kind == "newobject":
        count = op[1]
        return 2 * count, 1 - (2 * count)
    if kind == "callpropvoid":
        argc = op[2]
        return argc + 1, -(argc + 1)
    if kind in {"callproperty", "constructprop"}:
        argc = op[2]
        return argc + 1, -argc
    if kind in {"ifne", "ifeq"}:
        return 2, -2
    if kind in {"iffalse", "iftrue"}:
        return 1, -1
    if kind in {"jump", "returnvoid"}:
        return 0, 0
    raise CandidateRejected(f"unsupported candidate instruction {kind}")


def format_instruction(op: tuple) -> str:
    kind = op[0]
    if kind == "label":
        return f"{op[1]}:"
    if kind == "pushstring":
        return f'pushstring "{_escape_pcode_string(op[1])}"'
    if kind in {"getproperty", "initproperty", "getlex", "findpropstrict", "findproperty"}:
        return f"{kind} {op[1]}"
    if kind in {"pushbyte", "pushshort", "pushint"}:
        return f"{kind} {int(op[1])}"
    if kind in {"callproperty", "callpropvoid", "constructprop"}:
        return f"{kind} {op[1]}, {int(op[2])}"
    if kind == "newobject":
        return f"newobject {int(op[1])}"
    if kind in {"ifne", "ifeq", "iffalse", "iftrue", "jump"}:
        return f"{kind} {op[1]}"
    if kind in {"getlocal0", "pushscope", "pushnull", "returnvoid", "add", "astypelate"}:
        return kind
    raise CandidateRejected(f"cannot format {kind}")


def compare_swf_tags(original: bytes, candidate: bytes) -> dict:
    """Report whether the candidate differs only by DoABC payloads and the header length."""
    left = _parse_swf(original)
    right = _parse_swf(candidate)
    type_match = [item["type"] for item in left["tags"]] == [item["type"] for item in right["tags"]]
    other_same = type_match
    changed = []
    if type_match:
        for before, after in zip(left["tags"], right["tags"]):
            if before["payload"] != after["payload"]:
                changed.append(before["type"])
                if before["type"] != DOABC:
                    other_same = False
    else:
        other_same = False
        changed = sorted(
            set([item["type"] for item in left["tags"]] + [item["type"] for item in right["tags"]])
        )
    frame_same = left["frame"] == right["frame"] and left["signature"] == right["signature"]
    length_changed = left["declared_length"] != right["declared_length"]
    raw_signature_same = original[:3] == candidate[:3]
    only = (
        other_same
        and frame_same
        and raw_signature_same
        and left["version"] == right["version"]
        and set(changed) == {DOABC}
        and sum(1 for item in right["tags"] if item["type"] == DOABC) == 1
    )
    return {
        "signature": candidate[:3].decode("ascii", "replace"),
        "header_length_changed": length_changed,
        "frame_header_same": frame_same,
        "changed_tag_types": changed,
        "non_doabc_identical": other_same and frame_same and left["version"] == right["version"],
        "only_doabc_and_header_length_changed": only,
    }


def reject_paths(*paths: Path) -> None:
    """Refuse in-place output, links, and anything under an installed game tree.

    The first path is the source movie and the second is the candidate output.
    """
    if len(paths) < 2:
        raise CandidateRejected("source and output paths are required")
    source, output = Path(paths[0]), Path(paths[1])
    for path in paths:
        if not Path(path).is_absolute():
            raise CandidateRejected("candidate paths must be absolute")
        if _installed_game_path(Path(path)):
            raise CandidateRejected("path is inside an installed game tree")
        _require_ordinary_ancestors(Path(path))
    if not source.is_file() or source.is_symlink() or _is_reparse(source):
        raise CandidateRejected("source movie is not an ordinary file")
    if _same_file(source, output):
        raise CandidateRejected("refusing to replace the source movie in place")
    if output.exists() and (output.is_symlink() or _is_reparse(output)):
        raise CandidateRejected("output path is a reparse point")


def function_source(actionscript: str, name: str) -> str:
    matches = list(re.finditer(rf"\bfunction\s+{re.escape(name)}\s*\(", actionscript))
    if len(matches) != 1:
        raise CandidateRejected(f"{name} is not a single actionscript method")
    start = matches[0].start()
    later = re.search(r"\bfunction\s+\w+\s*\(", actionscript[matches[0].end() :])
    end = len(actionscript) if later is None else matches[0].end() + later.start()
    return actionscript[start:end]


def qname(namespace: str, name: str) -> str:
    return f'QName({namespace},"{name}")'


def package(name: str) -> str:
    return f'PackageNamespace("{name}")'


def _reject_forbidden_operations(name: str, instructions: list[tuple]) -> None:
    rendered = "\n".join(format_instruction(op) for op in instructions)
    forbidden = (
        "TryToPlayOnline",
        "ExternalInterface",
        "SHELL_CallUnrealFunction",
        "navigateToURL",
        "fscommand",
        "MovieMenuStack",
        "openShopMainMenu",
        "openRocketPassScreen",
        "openPlayNow",
        "openEsportsLink",
        "handleClubButtonClicked",
        "syncLocalClub",
        "PLAY_MENU",
        "ShopPrimeMenu",
        "RocketPassMenu",
        "MTXGarage",
    )
    for token in forbidden:
        if re.search(rf"(?<![\w]){re.escape(token)}(?![\w])", rendered):
            raise CandidateRejected(f"{name} still references {token}")
    if name == "generateControls":
        for code in TRIGGER_CODES.values():
            if code in rendered:
                raise CandidateRejected("generateControls embeds a host trigger string")
        for control in CONTROLS:
            if f'pushstring "{control["label"]}"' not in rendered:
                raise CandidateRejected(f"generateControls is missing {control['label']}")
    if name in TRIGGER_CODES:
        own = TRIGGER_CODES[name]
        if own not in rendered or "ButtonTriggered" not in rendered or "MenuStack" not in rendered:
            raise CandidateRejected(f"{name} does not call MenuStack.ButtonTriggered")
        for other in TRIGGER_CODES.values():
            if other != own and other in rendered:
                raise CandidateRejected(f"{name} maps to the wrong trigger")


def _require_controls(code: str) -> None:
    for control in CONTROLS:
        if f'"{control["label"]}"' not in code or control["field"] not in code:
            raise CandidateRejected(f"candidate lost the {control['label']} control")
        if control["callback"][1] not in code:
            raise CandidateRejected(f"candidate lost the {control['label']} callback")
    for token in ("openPlayNow", "openEsportsLink", "openShopMainMenu", "syncLocalClub", "PLAY_MENU"):
        if re.search(rf"(?<![\w]){token}(?![\w])", code):
            raise CandidateRejected(f"generateControls still references {token}")
    if code.count("validateNow") < len(CONTROLS) or "currentFocus" not in code:
        raise CandidateRejected("generateControls does not validate and focus the native buttons")
    if "ExitGame" not in code:
        raise CandidateRejected("Exit does not use Shell.ExitGame")


def _require_trigger(name: str, code: str) -> None:
    own = TRIGGER_CODES[name]
    if f'"{own}"' not in code or "ButtonTriggered" not in code or "MenuStack" not in code:
        raise CandidateRejected(f"{name} trigger was not exported")
    for token in ("TryToPlayOnline", "openShopMainMenu", "openRocketPassScreen", "PLAY_MENU", "openMenu"):
        if re.search(rf"(?<![\w]){token}(?![\w])", code):
            raise CandidateRejected(f"{name} still calls a stock route")


def _require_noop(code: str) -> None:
    opcodes = []
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.endswith(":"):
            continue
        if stripped == "getlocal 0":
            opcodes.append("getlocal0")
            continue
        opcodes.append(stripped.split()[0])
    ignored = {"debug", "debugline", "debugfile", "nop"}
    opcodes = [item for item in opcodes if item not in ignored]
    if opcodes != ["getlocal0", "pushscope", "returnvoid"]:
        raise CandidateRejected("helper no-op body was not exported")


def _public_method(plan: dict) -> dict:
    return {
        "name": plan["name"],
        "body_index": plan["body_index"],
        "method_index": plan["method_index"],
        "kind": plan["kind"],
        "maxstack": plan["maxstack"],
        "stack_peak": plan["stack_peak"],
        "localcount": plan["localcount"],
        "initscopedepth": plan["initscopedepth"],
        "maxscopedepth": plan["maxscopedepth"],
    }


def _method_kind(name: str) -> str:
    if name == "generateControls":
        return "seven_controls"
    if name in TRIGGER_CODES:
        return "menu_stack_trigger"
    return "noop"


def _plan_summary(plans: dict) -> dict:
    return {
        "class_name": CLASS_NAME,
        "runtime_verified": False,
        "production": False,
        "methods": [_public_method(plan) for plan in plans.values()],
    }


def _export_script(java, jar, home, movie, out_dir, script_format, *, method_ids: bool) -> None:
    if out_dir.exists():
        for child in sorted(out_dir.rglob("*"), reverse=True):
            if child.is_file() and not _is_reparse(child):
                child.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    config = "showMethodBodyId=true,autoDeobfuscate=0" if method_ids else "autoDeobfuscate=0"
    _run_ffdec(
        java,
        jar,
        home,
        [
            "-config",
            config,
            "-format",
            script_format,
            "-selectclass",
            CLASS_NAME,
            "-export",
            "script",
            str(out_dir),
            str(movie),
        ],
    )


def _find_export(directory: Path, suffix: str) -> str:
    matches = [path for path in directory.rglob(f"*{suffix}") if path.name.startswith("RootMenu")]
    if len(matches) != 1:
        raise CandidateRejected(f"expected one RootMenu{suffix} export")
    return _read_text(matches[0])


def _run_ffdec(java: Path, jar: Path, home: Path, arguments: list[str]) -> None:
    command = [
        str(java),
        f"-Duser.home={home}",
        "-Djava.awt.headless=true",
        "-jar",
        str(jar),
        *arguments,
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = " ".join(detail[-8:])[:500]
        raise CandidateRejected(f"FFDec failed ({completed.returncode}): {tail}")


def _parse_swf(movie: bytes) -> dict:
    if len(movie) < 12 or len(movie) > MAX_MOVIE_BYTES:
        raise CandidateRejected("movie size is outside the candidate bounds")
    data = _uncompressed_swf(movie)
    signature = data[:3].decode("ascii")
    version = data[3]
    declared = struct.unpack_from("<I", data, 4)[0]
    if declared != len(data):
        raise CandidateRejected("SWF header length does not match the file")
    nbits = data[8] >> 3
    rect_len = (5 + 4 * nbits + 7) // 8
    frame_end = 8 + rect_len + 4
    if frame_end > len(data):
        raise CandidateRejected("SWF frame header is outside the file")
    tags = []
    pos = frame_end
    while pos + 2 <= len(data) and len(tags) < MAX_TAGS:
        head = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        tag_type, length = head >> 6, head & 63
        if length == 63:
            if pos + 4 > len(data):
                raise CandidateRejected("truncated SWF tag length")
            length = struct.unpack_from("<I", data, pos)[0]
            pos += 4
        if length < 0 or pos + length > len(data):
            raise CandidateRejected("SWF tag is outside the file")
        tags.append({"type": tag_type, "payload": data[pos : pos + length]})
        pos += length
        if tag_type == 0:
            break
    if len(tags) >= MAX_TAGS or not tags or tags[-1]["type"] != 0:
        raise CandidateRejected("SWF tag list is not a closed bounded movie")
    return {
        "signature": signature,
        "version": version,
        "declared_length": declared,
        "frame": data[8:frame_end],
        "tags": tags,
    }


def _uncompressed_swf(movie: bytes) -> bytes:
    signature = movie[:3]
    if signature in {b"GFX", b"FWS"}:
        return movie
    if signature not in {b"CFX", b"CWS"}:
        raise CandidateRejected("movie signature is not a SWF or GFX")
    declared = struct.unpack_from("<I", movie, 4)[0]
    if declared > MAX_MOVIE_BYTES:
        raise CandidateRejected("compressed movie declares an oversized file")
    payload = zlib.decompress(movie[8:])
    if len(payload) + 8 != declared:
        raise CandidateRejected("decompressed movie length does not match its header")
    rewritten = b"GFX" if signature == b"CFX" else b"FWS"
    return rewritten + movie[3:8] + payload


def _package_name(text: str) -> str:
    match = re.search(r"(?m)^package\s+([A-Za-z0-9_.]*)", text)
    if match is None:
        raise CandidateRejected("export has no package declaration")
    return match.group(1)


def _class_name(text: str) -> str:
    match = re.search(r"\bclass\s+(\w+)", text)
    if match is None:
        raise CandidateRejected("export has no class declaration")
    return match.group(1)


def _installed_game_path(path: Path) -> bool:
    text = str(path).lower().replace("/", "\\")
    if "\\steamapps\\common\\" in text or "\\cookedpcconsole\\" in text:
        return True
    parts = {part.lower() for part in path.parts}
    if "program files" in parts or "program files (x86)" in parts:
        return True
    cursor = path if path.is_dir() else path.parent
    for parent in (cursor, *cursor.parents):
        if (parent / "RocketLeague.exe").exists():
            return True
        if (parent / "TAGame").is_dir() and (parent / "Binaries").is_dir():
            return True
    return False


def _require_ordinary_ancestors(path: Path) -> None:
    cursor = path if path.exists() else path.parent
    for parent in (cursor, *cursor.parents):
        if parent.is_symlink() or _is_reparse(parent):
            raise CandidateRejected("path contains a reparse point")
        if parent.parent == parent:
            break


def _is_reparse(path: Path) -> bool:
    if os.name != "nt":
        try:
            return path.is_symlink()
        except OSError:
            return False
    get_attributes = ctypes.windll.kernel32.GetFileAttributesW
    get_attributes.argtypes = [ctypes.c_wchar_p]
    get_attributes.restype = ctypes.c_uint32
    attrs = get_attributes(str(path))
    if attrs == INVALID_FILE_ATTRIBUTES:
        return False
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)


def _same_file(left: Path, right: Path) -> bool:
    if os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right)):
        return True
    if left.exists() and right.exists():
        try:
            return os.path.samefile(left, right)
        except OSError:
            return False
    return False


def _read_text(path: Path) -> str:
    if not path.is_file() or path.is_symlink() or _is_reparse(path):
        raise CandidateRejected(f"text export is not an ordinary file: {path.name}")
    return path.read_text(encoding="utf-8")


def _read_bytes(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or _is_reparse(path):
        raise CandidateRejected(f"movie is not an ordinary file: {path.name}")
    data = path.read_bytes()
    if len(data) > MAX_MOVIE_BYTES:
        raise CandidateRejected("movie exceeds the candidate size cap")
    return data


def _escape_pcode_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _code_lines_from_export(pcode: str, name: str) -> str:
    extracted = extract_method(pcode, name)
    lines = pcode.splitlines()
    # Re-find the code body in the original text. extract_method dropped it, so
    # scan the same function span for the instruction block.
    starts = [
        index for index, line in enumerate(lines) if re.search(rf"\bfunction\s+{re.escape(name)}\s*\(", line)
    ]
    if len(starts) != 1:
        raise CandidateRejected(f"{name} export is not unique")
    code_at = None
    end_code = None
    for index in range(starts[0], len(lines)):
        if code_at is None and lines[index].strip() == "code":
            code_at = index + 1
            continue
        if code_at is not None and lines[index].strip().startswith("end ; code"):
            end_code = index
            break
        if code_at is None and index != starts[0] and re.search(r"\bfunction\s+\w+\s*\(", lines[index]):
            break
    if code_at is None or end_code is None:
        raise CandidateRejected(f"{name} export has no code section")
    del extracted
    return "\n".join(lines[code_at:end_code])


def verify_exported_candidate(actionscript: str, pcode: str) -> dict:
    """Confirm the reexported class still has the seven labels and the preserved bodies."""
    exported = parse_method_index(actionscript)
    for name, (body_index, method_index, _stack, _locals) in PINNED_METHODS.items():
        if exported.get(name) != (body_index, method_index):
            raise CandidateRejected(f"reexport changed the body id of {name}")
    for name in PINNED_METHODS:
        code = _code_lines_from_export(pcode, name)
        if name == "generateControls":
            _require_controls(code)
        elif name in TRIGGER_CODES:
            _require_trigger(name, code)
        else:
            _require_noop(code)
    garage = _code_lines_from_export(pcode, "openGarageSelectionMenu")
    options = _code_lines_from_export(pcode, "openOptionsMenu")
    if "GARAGE_MAIN" not in garage or "MCT_" in garage:
        raise CandidateRejected("openGarageSelectionMenu was not preserved")
    if "SetSharedUIState" not in options or '"Options"' not in options:
        raise CandidateRejected("openOptionsMenu was not preserved")
    actionscript_controls = function_source(actionscript, "generateControls")
    for control in CONTROLS:
        if control["label"] not in actionscript_controls:
            raise CandidateRejected(f"reexported actionscript lost the {control['label']} label")
    return {
        "seven_labels": True,
        "trigger_callbacks": True,
        "helpers_noop": True,
        "garage_preserved": True,
        "options_preserved": True,
        "body_ids_preserved": True,
    }


if __name__ == "__main__":
    sys.exit(main())
