"""Read a user-provided visual animation reference, never project/export data."""
from PIL import Image, ImageSequence

def read_reference(path, sheet_columns=None, sheet_rows=None):
    frames=[]
    with Image.open(path) as source:
        if getattr(source,'n_frames',1)>1:
            for image in ImageSequence.Iterator(source):
                frames.append((image.convert('RGBA').copy(),max(20,int(image.info.get('duration',100)))))
        elif sheet_columns and sheet_rows:
            if source.width%sheet_columns or source.height%sheet_rows:
                raise ValueError('Sprite sheet dimensions must divide evenly into rows and columns.')
            w=source.width//sheet_columns;h=source.height//sheet_rows
            for row in range(sheet_rows):
                for col in range(sheet_columns):
                    frames.append((source.crop((col*w,row*h,(col+1)*w,(row+1)*h)).convert('RGBA'),100))
        else:frames.append((source.convert('RGBA').copy(),100))
    if not frames:raise ValueError('The reference has no frames.')
    return frames
