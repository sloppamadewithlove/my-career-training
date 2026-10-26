"""Pure training API; the isolated RLBot adapter applies normalized reset/render events."""

from .catalog import ASSISTANCE_DEFAULTS, assistance_preferences, catalog, configure_lesson, lesson
from .coach import (COACHING_DEFAULTS, GhostPlayback, GhostPractice, PRACTICE_FORWARD_OFFSET,
                    coaching_preferences, practice_context, practice_support, recording_provenance,
                    reference_availability)
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
    relative_placement,
    validate_recording,
)

__all__ = [
    "ASSISTANCE_DEFAULTS",
    "COACHING_DEFAULTS",
    "PLAYSTATION_BINDINGS",
    "PRACTICE_FORWARD_OFFSET",
    "GhostPlayback",
    "GhostPractice",
    "coaching_preferences",
    "controller_bindings",
    "controller_display",
    "lesson_coaching",
    "practice_context",
    "practice_support",
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
    "relative_placement",
    "validate_recording",
]
