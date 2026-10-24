"""Offline, pixel-perfect generic reference animations for beginner recipes.

These are schematic motion examples, not required anatomy or a pose validator.
"""
import math
from PIL import Image, ImageDraw
from .pet_suite_templates import TEMPLATES


def reference_frame(action, frame, size=128, body_type="Biped"):
    if body_type not in ("Biped", "Quadruped", "Floating"):
        raise ValueError("Unknown reference body type")
    if action not in TEMPLATES:
        raise KeyError(action)
    count = len(TEMPLATES[action])
    frame = int(frame) % count
    phase = 2 * math.pi * frame / count
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = size / 128
    def rect(box, color):
        draw.rectangle(tuple(round(v * scale) for v in box), fill=color)
    def line(points, color, width=3):
        draw.line([(round(x*scale),round(y*scale)) for x,y in points], fill=color, width=max(1,round(width*scale)))
    name = action.lower()
    # Reference-only movement vocabulary: inspiration, never a constraint on artwork.
    travel = any(t in name for t in ('walk', 'runn', 'hopp', 'happy', 'excit', 'startled'))
    resting = any(t in name for t in ('sleep', 'sitting', 'falling asleep'))
    attention = any(t in name for t in ('look', 'tilt', 'sniff', 'confused', 'turning'))
    celebration = any(t in name for t in ('wav', 'happy', 'excit'))
    eating = any(t in name for t in ('eating', 'drinking', 'yawn'))
    if body_type == "Quadruped":
        phase_shift=round((11 if travel else 2)*math.sin(phase))
        bob=round((5 if travel else 1 if resting else 3)*math.sin(phase))
        head_shift=round(7*math.sin(phase)) if attention else 0
        head_drop=(9 if resting else 5 if eating and frame in (1,2) else 0)
        rect((23, 61-bob, 100, 87-bob), '#92c6b2')
        rect((79+head_shift, 38-bob+head_drop, 112+head_shift, 69-bob+head_drop), '#b2dfbd')
        rect((82+head_shift, 30-bob+head_drop, 92+head_shift, 44-bob+head_drop), '#b2dfbd')
        rect((102+head_shift, 30-bob+head_drop, 112+head_shift, 44-bob+head_drop), '#b2dfbd')
        for x,offset in ((29,phase_shift),(46,-phase_shift),(79,-phase_shift),(94,phase_shift)):
            rect((x+offset, 83-bob, x+offset+9, 108-bob), '#75a6a0')
        rect((91+head_shift, 50-bob+head_drop, 96+head_shift, 55-bob+head_drop), '#28433e')
        rect((107+head_shift, 59-bob+head_drop, 113+head_shift, 62-bob+head_drop), '#e79aa9')
        line([(25,70-bob),(10,53-bob+round((12 if celebration else 5)*math.sin(phase)))], '#75a6a0',5)
        return image
    if body_type == "Floating":
        bob=round((11 if travel or celebration else 2 if resting else 7)*math.sin(phase))
        sway=round(9*math.sin(phase)) if attention else 0
        face_y=5 if resting else 0
        rect((37, 38-bob, 91, 85-bob), '#b2dfbd')
        rect((40, 25-bob, 52, 45-bob), '#b2dfbd')
        rect((77, 25-bob, 89, 45-bob), '#b2dfbd')
        rect((49+sway, 54-bob+face_y, 56+sway, 61-bob+face_y), '#28433e')
        rect((73+sway, 54-bob+face_y, 80+sway, 61-bob+face_y), '#28433e')
        rect((62+sway, 67-bob+face_y, 67+sway, 71-bob+face_y), '#e79aa9')
        line([(40,74-bob),(24,82-bob-round(10*math.sin(phase)) if celebration else 82-bob)],'#75a6a0',6)
        line([(88,74-bob),(104,82-bob)],'#75a6a0',6)
        return image
    movement = any(t in name for t in ('walk','runn','hopp','happy','excit','startled','picked up'))
    airborne = any(t in name for t in ('flying','hovering'))
    resting = any(t in name for t in ('sleep','sitting','falling asleep'))
    bob = round((7 if movement else 4 if airborne else 2) * math.sin(phase))
    if resting: bob = round(2*math.sin(phase))
    cy = 68-bob
    left_step = round(9*math.sin(phase)) if movement else 0
    right_step = -left_step
    # Stylized two-legged reference mascot, with no assumptions about user's anatomy.
    rect((42+left_step, 85-bob, 52+left_step, 108-bob), '#75a6a0')
    rect((75+right_step, 85-bob, 85+right_step, 108-bob), '#75a6a0')
    rect((42, 62-bob, 86, 92-bob), '#92c6b2')
    arm_offset = round(6*math.sin(phase)) if ('wav' in name or movement) else 0
    rect((31, 66-bob-arm_offset, 42, 88-bob-arm_offset), '#75a6a0')
    rect((86, 66-bob+arm_offset, 97, 88-bob+arm_offset), '#75a6a0')
    tilt = round(5*math.sin(phase)) if any(t in name for t in ('tilt','confused','looking','turning')) else 0
    hx = 64+tilt
    rect((hx-26, 27-bob, hx+26, 66-bob), '#b2dfbd')
    rect((hx-25, 17-bob, hx-12, 36-bob), '#b2dfbd')
    rect((hx+12, 17-bob, hx+25, 36-bob), '#b2dfbd')
    eyes_closed = ('sleep' in name and frame > 0) or ('blink' in name and frame%3==1)
    if eyes_closed:
        line([(hx-16,47-bob),(hx-8,47-bob)],'#28433e',2)
        line([(hx+8,47-bob),(hx+16,47-bob)],'#28433e',2)
    else:
        rect((hx-16, 43-bob, hx-10, 49-bob),'#28433e')
        rect((hx+10, 43-bob, hx+16, 49-bob),'#28433e')
    rect((hx-2, 53-bob, hx+2, 56-bob),'#e79aa9')
    if any(t in name for t in ('eating','yawn','drinking')) and frame in (1,2,3):
        rect((hx-5,58-bob,hx+5,64-bob),'#654454')
    if airborne:
        wing = round(14*math.sin(phase))
        line([(42,70-bob),(13,42-bob+wing),(5,57-bob+wing)],'#d3b7eb',6)
        line([(86,70-bob),(115,42-bob+wing),(123,57-bob+wing)],'#d3b7eb',6)
    if 'groom' in name or 'petted' in name:
        line([(35,76-bob),(hx-13,50-bob)],'#75a6a0',5)
    if 'waving' in name:
        line([(90,75-bob),(105+round(6*math.sin(phase)),37-bob)],'#75a6a0',6)
    return image
