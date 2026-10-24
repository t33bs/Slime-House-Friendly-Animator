"""Offline availability checks for built-in guidance and animation recipes."""

def bundled_resource_report():
    from .pet_suite_templates import TEMPLATES
    from .slime_buddy import STATIONS, station_guide
    from .reference_animation import reference_frame
    problems = []
    if not TEMPLATES:
        problems.append('Animation recipes are missing')
    if not STATIONS:
        problems.append('Slime Buddy stations are missing')
    for name in STATIONS:
        try:
            if not station_guide(name):
                problems.append(f'Empty Slime Buddy guidance: {name}')
        except Exception as exc:
            problems.append(f'Slime Buddy station {name}: {exc}')
    if TEMPLATES:
        try:
            frame = reference_frame(next(iter(TEMPLATES)), 0)
            if frame.width <= 0 or frame.height <= 0:
                problems.append('Reference animation returned an empty image')
        except Exception as exc:
            problems.append(f'Reference animation unavailable: {exc}')
    return problems
