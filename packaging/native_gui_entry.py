"""The isolated native candidate opens its native session on a normal double-click."""
import sys

from my_career_training.__main__ import main


def native_arguments(arguments):
    result = list(arguments)
    separate_modes = {"--worker", "--manage", "--self-test", "--smoke-test", "--help", "-h"}
    if "--native-menu-trial" not in result and not separate_modes.intersection(result):
        result.append("--native-menu-trial")
    return result


if __name__ == "__main__":
    sys.argv[1:] = native_arguments(sys.argv[1:])
    raise SystemExit(main())
