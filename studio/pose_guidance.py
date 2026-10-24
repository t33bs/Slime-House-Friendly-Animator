"""Optional technique coaching for every animation recipe and reference body type.

Never validates or scores anatomy, artistic style, or fidelity to reference art.
"""
from .pet_suite_templates import TEMPLATES

TECHNIQUES = {
 'Idle / Breathing': ('tiny repeated offsets', 'a slow return to the first pose'),
 'Walking': ('alternating contact moments', 'an optional weight shift'),
 'Running': ('quicker spacing between poses', 'an optional airborne beat'),
 'Sleeping': ('longer holds', 'subtle repeated motion'),
 'Eating': ('a brief pause before an action', 'small repeating changes'),
 'Happy / Celebrating': ('a buildup before a big motion', 'a held peak pose'),
 'Grooming': ('small repeated movements', 'a pause between gestures'),
 'Flying / Hovering': ('a rise-and-fall cycle', 'offset movement between pieces'),
 'Custom': ('contrasting poses', 'different timing experiments'),
 'Sitting Down': ('slower settling frames', 'a final held pose'),
 'Yawning': ('a gradual buildup', 'a slow recovery'),
 'Drinking': ('a small repeating cycle', 'a pause at the end'),
 'Stretching': ('a gradual extension', 'a relaxed return'),
 'Curious Head Tilt': ('an asymmetric change', 'a brief hold'),
 'Hopping': ('a quick launch', 'a longer airborne interval'),
 'Being Petted': ('a small reaction', 'a comfortable settling pose'),
 'Confused': ('a hesitant pause', 'a contrasting reaction'),
 'Excited': ('quick alternating poses', 'a short anticipation'),
 'Sad / Lonely': ('longer still moments', 'small deliberate changes'),
 'Angry / Pouting': ('sharp timing contrast', 'a held reaction'),
 'Shy / Blushing': ('a pause before reacting', 'a small retreat'),
 'Startled': ('a sudden large change', 'a slower recovery'),
 'Bored': ('long pauses', 'tiny interruptions'),
 'Affectionate': ('a gentle approach', 'a short held moment'),
 'Turning Around': ('intermediate silhouettes', 'consistent frame spacing'),
 'Sniffing': ('short repeating gestures', 'an inquisitive pause'),
 'Looking Around': ('contrasting directions', 'a return to center'),
 'Getting Picked Up': ('an upward transition', 'a suspended hold'),
 'Waving Hello': ('a repeated alternating gesture', 'a clear start and finish'),
 'Falling Asleep': ('gradually longer holds', 'progressively smaller movement'),
 'Pooping': ('a held middle pose', 'a relaxed return'),
}
BODY_OPTIONS = {
 'Biped': 'If useful, experiment with different upper/lower piece timing.',
 'Quadruped': 'If useful, stagger the timing of separate pieces.',
 'Floating': 'If useful, try offsetting the whole sprite by a pixel or two.',
 'Custom': 'Any number of independent pieces can move in any direction.',
}

def technique_hint(action, frame, body_type='Custom', part_names=()):
    if action not in TEMPLATES: raise KeyError(action)
    if body_type not in BODY_OPTIONS: raise ValueError(body_type)
    steps=TEMPLATES[action]
    index=int(frame)%len(steps)
    first, second=TECHNIQUES[action]
    technique=(first,second)[index%2]
    return (f'Pose {index+1}/{len(steps)} — {steps[index]}. '
            f'Optional technique: explore {technique}. '
            f'{BODY_OPTIONS[body_type]} '
            'The reference is not a rule; your design and movement are entirely your choice.')

def pose_hint(action, frame, part_names=()):
    """Backward-compatible non-prescriptive hint."""
    return technique_hint(action,frame,part_names=part_names)
