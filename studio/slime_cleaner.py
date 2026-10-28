"""Slime Cleaner: independent, pixel-precise eraser for visible artwork layers."""
from PIL import Image


def erase_visible_pixels(parts, x, y, brush_size=1):
    """Clear the topmost visible nontransparent pixel under each brush pixel.

    Parts are edited in place; unrelated pixels and hidden layers are preserved.
    Callers should record one undo snapshot at the start of each brush stroke.
    """
    size=max(1,int(brush_size))
    start=-(size//2)
    changed=False
    for cy in range(int(y)+start,int(y)+start+size):
        for cx in range(int(x)+start,int(x)+start+size):
            for part in reversed(parts):
                if not part.get('visible',True):
                    continue
                px=cx-int(part.get('x',0));py=cy-int(part.get('y',0))
                image=part['image']
                if not (0<=px<image.width and 0<=py<image.height):
                    continue
                if image.getpixel((px,py))[3]==0:
                    continue
                if image.mode!='RGBA':
                    image=image.convert('RGBA').copy();part['image']=image
                image.putpixel((px,py),(0,0,0,0))
                changed=True
                break
    return changed
