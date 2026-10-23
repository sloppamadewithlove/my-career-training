"""Human-readable targets and lesson progress from observed events only."""

from copy import deepcopy


_STAGES = {
    "speed-flip": [
        ("Jump", "Accelerate and boost toward FINISH. Jump once.", ["first_jump"]),
        ("Diagonal dodge", "Release Jump, then jump again with diagonal direction.", ["diagonal_dodge"]),
        ("Cancel", "Reverse pitch after the diagonal dodge. Keep the movement controlled.", ["opposing_pitch"]),
        ("Finish and recover", "Cross the green FINISH rectangle and land on your wheels in the corridor.",
         ["target_crossed", "landed"]),
    ],
    "flip-reset": [
        ("Use your first flip", "Use your original flip so a newly gained reset can be observed.", ["dodge"]),
        ("Meet the ball", "Turn your wheels toward the raised ball, away from walls and floor.", ["ball_contact"]),
        ("Acquire a reset", "Meet the ball with your underside; the detector checks new flip availability.", ["reset_acquired"]),
    ],
    "dribble-flick": [
        ("Carry", "Balance the ball in the roof carry zone for two continuous seconds.", ["carry_sustained"]),
        ("Flick", "Jump and flick toward the goal target.", ["flick"]),
        ("Place", "Send the ball through the marked goal rectangle.", ["goal_target"]),
    ],
    "power-shots": [
        ("Contact", "Meet the incoming ball. Contact speed is measured after the touch.", ["ball_contact"]),
        ("Target", "Send the ball through the marked goal rectangle.", ["goal_target"]),
    ],
    "shot-placement": [
        ("Contact", "Approach the ball and aim at the highlighted goal zone.", ["ball_contact"]),
        ("Target", "Place the ball through the selected goal rectangle.", ["goal_target"]),
    ],
    "fast-aerial": [
        ("Take off", "Jump, pitch up, and boost.", ["first_jump"]),
        ("Second jump", "Release Jump, release pitch, then jump again without a dodge.", ["second_jump"]),
        ("Gate", "Fly through the aerial gate; two jumps remain a separate technique observation.", ["gate_0"]),
    ],
    "aerial-air-roll": [
        ("Gate 1", "Take off and fly through the first gate.", ["gate_0"]),
        ("Gate 2", "Control your orientation and approach the second gate.", ["gate_1"]),
        ("Gate 3", "Continue through the third gate.", ["gate_2"]),
        ("Recovery", "Return to the floor on your wheels.", ["landed"]),
    ],
    "flight-recovery": [
        ("Gate 1", "Boost through the first flight gate.", ["gate_0"]),
        ("Gate 2", "Stay controlled through the second flight gate.", ["gate_1"]),
        ("Recovery", "Land and drive forward through the recovery corridor.", ["recovered"]),
    ],
}


def lesson_coaching(lesson, events=(), *, state="active", outcome="unfinished"):
    """Instruction completion describes observations, never a perfect technique grade."""
    observed = {event.get("name") for event in events
                if event.get("confidence") in ("observed", "strong telemetry evidence")}
    uncertain = {event.get("name") for event in events if event.get("confidence") == "uncertain"}
    stages = []
    for title, instruction, required in _STAGES.get(lesson["id"], []):
        complete = all(name in observed for name in required)
        stages.append({"title": title, "instruction": instruction, "required_events": list(required),
                       "observed_events": [name for name in required if name in observed],
                       "complete": complete, "uncertain": any(name in uncertain for name in required)})
    next_index = next((index for index, stage in enumerate(stages) if not stage["complete"]), None)
    if state == "settling":
        message = "Resetting the car and ball. Wait for READY before pressing anything."
    elif state == "ready":
        message = "Confirming the starting setup. The next verified packet begins your attempt."
    elif state == "interrupted":
        message = "Attempt interrupted. Retry to establish a clean start."
    elif state == "finished":
        message = ("Drill target observed. Review your timing or retry."
                   if outcome == "success" else "Review the observed steps, then Retry to try again.")
    elif next_index is not None:
        message = stages[next_index]["instruction"]
    else:
        message = "Marked steps observed; await the attempt result. This is not a technique rating."
    targets = []
    for index, original in enumerate(lesson["targets"]):
        target = deepcopy(original)
        if target["type"] == "plane":
            label, purpose = "FINISH", "Drive through this green rectangle, then recover on your wheels."
        elif target["type"] == "gate":
            number = 1 + sum(t["type"] == "gate" for t in lesson["targets"][:index])
            label, purpose = f"GATE {number}", "Fly through the gates in numbered order."
        elif target["type"] == "goal":
            label, purpose = "SHOT TARGET", "Send the ball's center through this goal rectangle."
        elif target["type"] == "carry":
            label, purpose = "CARRY ZONE", "Keep the ball controlled above the car's roof."
        elif target["type"] == "ball_reset":
            label, purpose = "RESET CONTACT", "Meet the raised ball with your wheels in clear airspace."
        else:
            label, purpose = "RECOVERY", "Land in this corridor and continue driving forward."
        target.update({"label": label, "purpose": purpose})
        targets.append(target)
    return {
        "lesson_id": lesson["id"], "stages": stages, "next_stage": next_index,
        "message": message, "targets": targets,
        "observation_note": "Highlighted stages are packet observations; timing and technique remain separate from target outcome.",
        "workflow": ["Watch demonstration", "Try it", "Retry", "Replay my attempt", "Training settings"],
    }
