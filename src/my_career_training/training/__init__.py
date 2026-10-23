"""Pure training API; the isolated RLBot adapter applies normalized reset/render events."""

from .catalog import ASSISTANCE_DEFAULTS, assistance_preferences, catalog, configure_lesson, lesson
from .coach import COACHING_DEFAULTS, GhostPlayback, coaching_preferences, recording_provenance, reference_availability
from .coaching import lesson_coaching
from .controller import PLAYSTATION_BINDINGS, controller_bindings, controller_display
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
    "COACHING_DEFAULTS",
    "PLAYSTATION_BINDINGS",
    "GhostPlayback",
    "coaching_preferences",
    "controller_bindings",
    "controller_display",
    "lesson_coaching",
    "recording_provenance",
    "reference_availability",
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
