from pathlib import Path

import pytest

from my_career_training import bakkes_installation


def record(display_name="BakkesMod version 3.0", install_location=r"D:\Program Files\BakkesMod"):
    return {"DisplayName": display_name, "InstallLocation": install_location}


def test_resolves_bakkesmod_install_location_to_expected_executable():
    candidate = bakkes_installation.injector_candidate_from_record(record())

    assert candidate == Path(r"D:\Program Files\BakkesMod\BakkesMod.exe")


def test_accepts_quoted_install_directory_and_exact_injector_path():
    directory = bakkes_installation.injector_candidate_from_record(
        record(install_location='"D:\\Program Files\\BakkesMod\\"')
    )
    executable = bakkes_installation.injector_candidate_from_record(
        record(install_location='"D:\\Program Files\\BakkesMod\\BakkesMod.exe"')
    )

    assert directory == Path(r"D:\Program Files\BakkesMod\BakkesMod.exe")
    assert executable == Path(r"D:\Program Files\BakkesMod\BakkesMod.exe")


@pytest.mark.parametrize(
    "invalid_record",
    [
        {},
        {"DisplayName": "Steam", "InstallLocation": r"D:\BakkesMod"},
        record(display_name="BakkesModLauncher"),
        record(install_location=None),
        record(install_location=""),
        record(install_location="BakkesMod"),
        record(install_location=r"D:BakkesMod"),
        record(install_location=r"\BakkesMod"),
        record(install_location=r"\\server\share\BakkesMod"),
        record(install_location=r"\\?\D:\Program Files\BakkesMod"),
        record(install_location='"D:\\BakkesMod'),
        record(install_location=r"D:\OtherApp\launcher.exe"),
        record(install_location=r"D:\Program Files\BakkesMod\BakkesMod.exe:stream"),
        record(install_location='"D:\\BakkesMod\\BakkesMod.exe" /S'),
        record(install_location=r"D:\BakkesMod\BakkesMod.exe /S"),
        record(display_name="BakkesMod " + "x" * 1500, install_location="D:\\" + "x" * 600),
        {
            "DisplayName": "BakkesMod version 3.0",
            "UninstallString": '"D:\\BakkesMod\\uninstall.exe"',
        },
    ],
)
def test_rejects_missing_malformed_relative_or_unrelated_locations(invalid_record):
    assert bakkes_installation.injector_candidate_from_record(invalid_record) is None


def test_preserves_apostrophes_inside_unquoted_install_paths():
    candidate = bakkes_installation.injector_candidate_from_record(
        record(install_location=r"D:\Slava's Tools\BakkesMod")
    )

    assert candidate == Path(r"D:\Slava's Tools\BakkesMod\BakkesMod.exe")


def test_deduplicates_windows_paths_case_insensitively_and_without_slash_differences():
    records = [
        record(install_location=r"D:\Program Files\BakkesMod"),
        record(display_name="bakkesmod", install_location="d:/program files/bakkesmod/"),
    ]

    assert bakkes_installation.discover_bakkesmod_injectors(records_reader=lambda: records) == [
        Path(r"D:\Program Files\BakkesMod\BakkesMod.exe")
    ]


def test_injected_records_reader_avoids_registry_and_does_not_mutate_records(monkeypatch):
    source_record = record()
    before = source_record.copy()

    def unexpected_registry_read():
        pytest.fail("The injected reader should keep discovery independent from the system registry")

    monkeypatch.setattr(bakkes_installation, "_read_uninstall_records", unexpected_registry_read)
    candidates = bakkes_installation.discover_bakkesmod_injectors(
        records_reader=lambda: [source_record]
    )

    assert candidates == [Path(r"D:\Program Files\BakkesMod\BakkesMod.exe")]
    assert source_record == before


class FakeKey:
    def __init__(self, hive, path, access):
        self.hive = hive
        self.path = path
        self.access = access

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeRegistry:
    KEY_READ = 0x1
    KEY_WOW64_64KEY = 0x100
    KEY_WOW64_32KEY = 0x200
    HKEY_LOCAL_MACHINE = "HKLM"
    HKEY_CURRENT_USER = "HKCU"

    def __init__(self, denied=None):
        self.root_opens = []
        self.value_reads = []
        self.denied = set(denied or ())
        self.records = {
            "bakkes": {
                "DisplayName": "BakkesMod version 3.0",
                "InstallLocation": r"D:\Program Files\BakkesMod",
                "UninstallString": "must not be read",
            },
            "unrelated": {
                "DisplayName": "Steam",
                "InstallLocation": r"C:\Program Files\Steam",
                "UninstallString": "must not be read",
            },
        }

    def OpenKey(self, key, subkey, _reserved, access):
        if isinstance(key, FakeKey):
            return FakeKey(key.hive, subkey, access)
        self.root_opens.append((key, subkey, access))
        if (key, access) in self.denied:
            raise PermissionError("access denied")
        return FakeKey(key, subkey, access)

    @staticmethod
    def QueryInfoKey(_key):
        return 2, 0, 0

    @staticmethod
    def EnumKey(_key, index):
        return ("bakkes", "unrelated")[index]

    def QueryValueEx(self, key, name):
        self.value_reads.append((key.path, name))
        value = self.records[key.path].get(name)
        if value is None:
            raise FileNotFoundError(name)
        return value, 1


def test_registry_reader_checks_supported_views_and_only_needed_values():
    registry = FakeRegistry()
    candidates = bakkes_installation.discover_bakkesmod_injectors(
        records_reader=lambda: bakkes_installation._read_uninstall_records(registry)
    )
    expected_hives = {registry.HKEY_LOCAL_MACHINE, registry.HKEY_CURRENT_USER}
    expected_access = {
        registry.KEY_READ,
        registry.KEY_READ | registry.KEY_WOW64_64KEY,
        registry.KEY_READ | registry.KEY_WOW64_32KEY,
    }

    assert {(hive, access) for hive, _, access in registry.root_opens} == {
        (hive, access) for hive in expected_hives for access in expected_access
    }
    assert all(path == bakkes_installation._UNINSTALL_KEY for _, path, _ in registry.root_opens)
    assert set(registry.value_reads) == {
        ("bakkes", "DisplayName"),
        ("bakkes", "InstallLocation"),
        ("unrelated", "DisplayName"),
    }
    assert candidates == [Path(r"D:\Program Files\BakkesMod\BakkesMod.exe")]


def test_registry_reader_skips_views_with_access_denied():
    denied = {
        (FakeRegistry.HKEY_LOCAL_MACHINE, FakeRegistry.KEY_READ),
        (FakeRegistry.HKEY_LOCAL_MACHINE, FakeRegistry.KEY_READ | FakeRegistry.KEY_WOW64_64KEY),
        (FakeRegistry.HKEY_LOCAL_MACHINE, FakeRegistry.KEY_READ | FakeRegistry.KEY_WOW64_32KEY),
    }
    registry = FakeRegistry(denied=denied)
    candidates = bakkes_installation.discover_bakkesmod_injectors(
        records_reader=lambda: bakkes_installation._read_uninstall_records(registry)
    )

    assert candidates == [Path(r"D:\Program Files\BakkesMod\BakkesMod.exe")]
    assert sum(hive == registry.HKEY_LOCAL_MACHINE for hive, _, _ in registry.root_opens) == 3
    assert sum(hive == registry.HKEY_CURRENT_USER for hive, _, _ in registry.root_opens) == 3


def test_registry_reader_bounds_entries_per_view():
    class LargeRegistry(FakeRegistry):
        def __init__(self):
            super().__init__()
            self.enum_calls = 0

        @staticmethod
        def QueryInfoKey(_key):
            return bakkes_installation._MAX_REGISTRY_ENTRIES_PER_VIEW + 20, 0, 0

        def EnumKey(self, _key, _index):
            self.enum_calls += 1
            return "unrelated"

    registry = LargeRegistry()
    records = bakkes_installation._read_uninstall_records(registry)

    assert records == []
    assert registry.enum_calls == bakkes_installation._MAX_REGISTRY_ENTRIES_PER_VIEW * len(registry.root_opens)
