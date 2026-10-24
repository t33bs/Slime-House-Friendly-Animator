"""Shared playback clock for the optional, non-prescriptive motion comparison."""

def comparison_position(durations, elapsed_ms, reference_steps, repeat=True):
    """Return (creature frame, reference step) from a single playback clock.

    The reference maps the fraction of the complete creature loop onto its own
    independent number of example steps; unequal frame counts stay in sync.
    """
    if reference_steps < 1:
        raise ValueError("A reference must have at least one step")
    durations = [max(1, int(d)) for d in durations]
    if not durations:
        return (None, 0)
    total = sum(durations)
    elapsed = max(0, float(elapsed_ms))
    position = elapsed % total if repeat else min(elapsed, max(0, total - 1e-6))
    cursor = position
    frame = len(durations) - 1
    for index, duration in enumerate(durations):
        if cursor < duration:
            frame = index
            break
        cursor -= duration
    step = min(reference_steps - 1, int(position / total * reference_steps))
    return frame, step
