"""Pure training API; the isolated RLBot adapter applies normalized reset/render events."""

from .catalog import ASSISTANCE_DEFAULTS, assistance_preferences, catalog, configure_lesson, lesson
from .engine import TrainingEngine
from .recordings import (
    Recorder,
    compare_attempts,
    compatible_recordings,
    ghost_lines,
    import_recording,
    interpolate_pose,
    personal_best,
    validate_recording,
)

__all__ = [
    "ASSISTANCE_DEFAULTS",
    "TrainingEngine",
    "Recorder",
    "assistance_preferences",
    "catalog",
    "configure_lesson",
    "lesson",
    "compare_attempts",
    "compatible_recordings",
    "ghost_lines",
    "import_recording",
    "interpolate_pose",
    "personal_best",
    "validate_recording",
]
