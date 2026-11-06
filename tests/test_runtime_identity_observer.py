"""The observer cannot become a normal plugin lifecycle or packaged feature."""
from pathlib import Path
import re

from my_career_training import native_launch


ROOT = Path(__file__).resolve().parents[1]


def test_observer_adapter_has_only_four_sdk_getters_and_no_background_lifecycle():
    source = (ROOT / "plugin/src/RuntimeIdentityObserver.cpp").read_text(encoding="utf-8")
    assert re.findall(r"gameWrapper->(\w+)\(", source) == [
        "GetBakkesModVersion", "GetPsyBuildID", "IsInOnlineGame", "IsInReplay",
    ]
    assert "void onUnload() override {}" in source
    for forbidden in ("RegisterDrawable", "HookEvent", "registerNotifier", "SetTimeout", "executeCommand",
                      "WriteProcessMemory", "SendInput", "CreateProcess", "NativeMovieHost", "MyCareerTraining::"):
        assert forbidden not in source
    assert source.index("Probe::fresh(lease, scope, now())") < source.index("Probe::observe(lease, scope")
    assert "CREATE_NEW" in source and "CREATE_ALWAYS" not in source
    assert '"plugin/src/RuntimeIdentityObserver.cpp"' in source


def test_observer_is_default_off_and_has_no_install_or_candidate_entry():
    cmake = (ROOT / "plugin/CMakeLists.txt").read_text(encoding="utf-8")
    assert 'option(MCT_BUILD_RUNTIME_IDENTITY_OBSERVER "Build the development-only one-shot identity observer" OFF)' in cmake
    assert "install(TARGETS MCTRuntimeIdentityObserver" not in cmake
    candidate = (ROOT / "scripts/build_native_candidate.py").read_text(encoding="utf-8")
    assert "MCTRuntimeIdentityObserver" not in candidate


def test_normal_launcher_old_identity_is_preserved():
    assert native_launch.SOURCE_EXE_SHA256 == "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"
    assert native_launch.SOURCE_EXE_SIZE == 39727616
