"""Friendly Animator's editable asset/pose model.

Frame poses contain per-frame geometry. Source PNGs are preserved separately.
"""
import base64
import io
import json
import math
import hashlib
from copy import deepcopy
from pathlib import Path
from PIL import Image
from .creature_rig import CreatureRig

class PetSuiteModel(CreatureRig):
    def __init__(self, size=(128, 128)):
        super().__init__(size)
        self.originals = []
        self.current = 'Idle / Breathing'
        self.frame_durations = {}  # milliseconds per frame, keyed by animation
        self.anchors = {}  # part index -> local anchor (x, y) in source pixels
        self.angles = {}  # part index -> degrees counterclockwise around joint
        self.attachments = {}  # child index -> {parent, offset_x, offset_y}; offsets are pixel coordinates

    def import_part(self, name, image, width=None, height=None):
        original = image.convert('RGBA').copy()
        w, h = width or original.width, height or original.height
        self.add_part(name, original.resize((int(w), int(h)), Image.Resampling.NEAREST))
        self.originals.append(original)

    def set_anchor(self, index, x, y):
        """Set an easy-to-see joint marker on a part in its current pixel coordinates."""
        if not 0 <= index < len(self.parts):
            raise ValueError("Choose a body part first.")
        part = self.parts[index]
        self.anchors[index] = [max(0, min(part["image"].width, int(x))),
                               max(0, min(part["image"].height, int(y)))]

    def rotate_part(self, index, degrees):
        """Set a non-destructive rotation in degrees about this part's joint dot."""
        if not 0 <= index < len(self.parts):
            raise ValueError('Choose a body part first.')
        self.angles[index] = float(degrees) % 360

    def render_part(self, index, state):
        """Render a part on a full transparent canvas so its joint stays stationary."""
        source = self._decode_source(state['source_png']) if state.get('source_png') else self.originals[index]
        w = max(1, int(state.get('width', self.parts[index]['image'].width)))
        h = max(1, int(state.get('height', self.parts[index]['image'].height)))
        part = source.resize((w, h), Image.Resampling.NEAREST)
        layer = Image.new('RGBA', self.size)
        x, y = int(state['x']), int(state['y'])
        layer.paste(part, (x, y), part)
        angle = float(state.get('angle', self.angles.get(index, 0)))
        if angle % 360:
            ax, ay = self.anchors.get(index, [w // 2, h // 2])
            # Joint coordinates are stored relative to the current resized part.
            layer = layer.rotate(angle, Image.Resampling.NEAREST,
                                 center=(x + ax, y + ay), expand=False)
        return layer

    def anchor_position(self, index):
        part = self.parts[index]
        ax, ay = self.anchors.get(index, [part["image"].width // 2, part["image"].height // 2])
        return part["x"] + ax, part["y"] + ay

    def attach(self, child, parent):
        """Attach a part to another part at its current position (no visual jump)."""
        if child == parent or not (0 <= child < len(self.parts) and 0 <= parent < len(self.parts)):
            raise ValueError('Choose two different, existing body parts.')
        ancestor = parent
        visited = set()
        while True:
            if ancestor == child or ancestor in visited:
                raise ValueError('That connection would create a loop.')
            visited.add(ancestor)
            if ancestor not in self.attachments:
                break
            ancestor = int(self.attachments[ancestor]['parent'])
            if not 0 <= ancestor < len(self.parts):
                raise ValueError('An attachment references a missing body part.')
        c, p = self.parts[child], self.parts[parent]
        self.attachments[child] = {'parent': parent, 'offset_x': c['x']-p['x'], 'offset_y': c['y']-p['y']}

    def detach(self, child):
        self.attachments.pop(child, None)

    def move_with_children(self, index, dx, dy):
        """Move a parent and descendants together; moving a child changes its attachment offset."""
        if not 0 <= index < len(self.parts):
            return
        def move(node, visited):
            if node in visited:
                raise ValueError('Circular creature attachment detected.')
            visited.add(node)
            self.parts[node]['x'] += int(dx)
            self.parts[node]['y'] += int(dy)
            for child, link in self.attachments.items():
                if link['parent'] == node:
                    move(child, visited)
            visited.remove(node)
        # Validate before mutating anything, so malformed saved rigs cannot half-move.
        def validate(node, seen):
            if node in seen:
                raise ValueError('Circular creature attachment detected.')
            seen.add(node)
            for child, link in self.attachments.items():
                if link['parent'] == node:
                    if not 0 <= child < len(self.parts):
                        raise ValueError('An attachment references a missing body part.')
                    validate(child, seen)
            seen.remove(node)
        validate(index, set())
        move(index, set())
        if index in self.attachments:
            self.attachments[index]['offset_x'] += int(dx)
            self.attachments[index]['offset_y'] += int(dy)

    def resize_part(self, index, width, height):
        source = self.originals[index]
        self.parts[index]['image'] = source.resize((max(1, int(width)), max(1, int(height))), Image.Resampling.NEAREST)

    def flip_part(self, index, axis):
        """Flip the selected PNG source, retaining its current displayed dimensions."""
        if not 0 <= index < len(self.parts):
            raise ValueError('Select an asset before flipping.')
        if axis not in ('horizontal', 'vertical'):
            raise ValueError('Flip direction must be horizontal or vertical.')
        source = self.originals[index]
        w, h = self.parts[index]['image'].size
        method = Image.Transpose.FLIP_LEFT_RIGHT if axis == 'horizontal' else Image.Transpose.FLIP_TOP_BOTTOM
        self.originals[index] = source.transpose(method)
        self.resize_part(index, w, h)
        if index in self.anchors:
            x, y = self.anchors[index]
            self.anchors[index] = [w - x if axis == 'horizontal' else x,
                                   h - y if axis == 'vertical' else y]

    def reset_part_size(self, index):
        """Restore imported pixel dimensions without changing position."""
        if not 0 <= index < len(self.parts):
            raise ValueError('Select an asset before resetting its size.')
        self.resize_part(index, *self.originals[index].size)

    def center_part(self, index, axis='both'):
        """Center the selected part on the creature canvas, in pixel coordinates."""
        if not 0 <= index < len(self.parts):
            raise ValueError('Select an asset before centering.')
        if axis not in ('horizontal', 'vertical', 'both'):
            raise ValueError('Invalid alignment axis.')
        part = self.parts[index]
        if axis in ('horizontal', 'both'):
            part['x'] = (self.size[0] - part['image'].width) // 2
        if axis in ('vertical', 'both'):
            part['y'] = (self.size[1] - part['image'].height) // 2

    def insert_frame(self, animation, index, pose=None):
        """Insert an independent editable pose at the requested frame position."""
        frames = self.animations.setdefault(animation, [])
        index = max(0, min(int(index), len(frames)))
        frames.insert(index, deepcopy(self.snapshot() if pose is None else pose))
        self._sync_durations(animation, count=len(frames)-1)
        self.frame_durations[animation].insert(index, self.frame_durations[animation][index-1] if index > 0 and index-1 < len(self.frame_durations[animation]) else 125)
        return index

    def copy_frame(self, animation, index):
        frames = self.animations.get(animation, [])
        if not 0 <= index < len(frames):
            raise IndexError('Choose a saved pose to copy.')
        return self.insert_frame(animation, index + 1, frames[index])

    def delete_frame(self, animation, index):
        frames = self.animations.get(animation, [])
        if not 0 <= index < len(frames):
            raise IndexError('Choose a saved pose to remove.')
        self._sync_durations(animation)
        self.frame_durations[animation].pop(index)
        return frames.pop(index)

    def move_frame(self, animation, index, direction):
        frames = self.animations.get(animation, [])
        destination = index + direction
        if not (0 <= index < len(frames) and 0 <= destination < len(frames)):
            return index
        frames[index], frames[destination] = frames[destination], frames[index]
        self._sync_durations(animation)
        times = self.frame_durations[animation]
        times[index], times[destination] = times[destination], times[index]
        return destination

    def _sync_durations(self, animation, count=None):
        count = len(self.animations.get(animation, [])) if count is None else count
        times = self.frame_durations.setdefault(animation, [])
        while len(times) < count:
            times.append(125)
        del times[count:]
        return times

    def set_frame_duration(self, animation, index, milliseconds):
        times = self._sync_durations(animation)
        if not 0 <= index < len(times):
            raise IndexError('Choose a saved pose first.')
        times[index] = max(40, min(2000, int(milliseconds)))

    def frame_duration(self, animation, index):
        times = self._sync_durations(animation)
        return times[index] if 0 <= index < len(times) else 125

    def playback_frame_at(self, animation, elapsed_ms):
        times = self._sync_durations(animation)
        if not times:
            return 0
        position = int(elapsed_ms) % sum(times)
        for index, duration in enumerate(times):
            if position < duration:
                return index
            position -= duration
        return len(times) - 1

    def save_pose_at(self, animation, index):
        """Save only the selected pose; other poses and animations remain unchanged."""
        frames = self.animations.setdefault(animation, [])
        if not 0 <= index < len(frames):
            raise IndexError('Choose an existing pose to edit.')
        frames[index] = deepcopy(self.snapshot())
        return frames[index]

    def edit_pose_at(self, animation, index, changes):
        """Apply per-part geometry to one pose without changing any other pose.

        This is deliberately anatomy-agnostic: parts may be any shape or size.
        """
        frames = self.animations.get(animation, [])
        if not 0 <= index < len(frames):
            raise IndexError('Choose an existing pose to edit.')
        pose = deepcopy(frames[index])
        for part_index, geometry in changes.items():
            if not 0 <= part_index < len(pose):
                raise IndexError('Choose an existing part.')
            for key, value in geometry.items():
                if key not in ('x','y','width','height','angle','visible'):
                    raise ValueError('Unknown pose property: ' + key)
                if key in ('width','height') and int(value) < 1:
                    raise ValueError('A part must be at least one pixel in size.')
                pose[part_index][key] = value
        frames[index] = pose
        return deepcopy(pose)

    @staticmethod
    def _encode_source(image):
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode('ascii')

    @staticmethod
    def _decode_source(encoded):
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
            return image.convert('RGBA').copy()

    def snapshot(self):
        return [dict(source_png=self._encode_source(self.originals[i]), name=p['name'], x=int(p['x']), y=int(p['y']),
                     width=p['image'].width, height=p['image'].height, angle=self.angles.get(i, 0),
                     visible=p.get('visible', True)) for i, p in enumerate(self.parts)]

    def replace_frame_image(self, animation, index, image):
        """Replace one frame with an editable, transparent full-canvas PNG layer.

        Other frames keep their original snapshots. The new layer is only visible
        in the target frame; it is hidden in the live state of older poses.
        """
        frames=self.animations.get(animation,[])
        if not 0<=index<len(frames):
            raise IndexError('Choose a saved pose first.')
        if image.size!=tuple(self.size):
            raise ValueError('Replacement PNG must match the creature canvas size.')
        # Import as a new part rather than overwriting any shared source asset.
        self.import_part(f'Frame {index+1} PNG edit',image)
        new_index=len(self.parts)-1
        state=self.snapshot()[new_index]
        # The replacement is a full frame: old layers must not show through.
        pose=deepcopy(frames[index])
        for old in pose:old['visible']=False
        pose.append(state)
        frames[index]=pose
        return new_index

    def apply_pose(self, pose):
        # Newly imported parts must not leak into earlier, shorter pose snapshots.
        for i in range(len(pose),len(self.parts)):
            self.parts[i]["visible"]=False
        for i, state in enumerate(pose):
            if i >= len(self.parts):
                break
            p = self.parts[i]
            if state.get('source_png'):
                self.originals[i] = self._decode_source(state['source_png'])
            p['x'], p['y'] = int(state['x']), int(state['y'])
            p['visible'] = state.get('visible', True)
            self.resize_part(i, state.get('width', p['image'].width), state.get('height', p['image'].height))
            self.angles[i] = float(state.get('angle', 0))

    def resolved_pose(self, pose=None):
        """Return positions and angles with parent transforms applied, without edits."""
        states = deepcopy(pose if pose is not None else self.snapshot())
        n = min(len(states), len(self.parts))
        original_angles = [float(states[i].get('angle', 0)) for i in range(n)]
        pivots = []
        for i in range(n):
            state = states[i]
            w = int(state.get('width', self.parts[i]['image'].width))
            h = int(state.get('height', self.parts[i]['image'].height))
            ax, ay = self.anchors.get(i, [w // 2, h // 2])
            pivots.append((float(state['x']) + ax, float(state['y']) + ay, ax, ay))

        def point_through(node, x, y, visited=None):
            visited = set() if visited is None else visited
            if node in visited:
                raise ValueError('Circular creature attachment detected.')
            visited.add(node)
            px, py, _, _ = pivots[node]
            angle = math.radians(original_angles[node])
            dx, dy = x - px, y - py
            x = px + dx * math.cos(angle) + dy * math.sin(angle)
            y = py - dx * math.sin(angle) + dy * math.cos(angle)
            link = self.attachments.get(node)
            if link is not None:
                parent = int(link['parent'])
                if not 0 <= parent < n:
                    raise ValueError('An attachment references a missing body part.')
                return point_through(parent, x, y, visited)
            return x, y

        def parent_angle(index, visited=None):
            visited = set() if visited is None else visited
            if index in visited:
                raise ValueError('Circular creature attachment detected.')
            visited.add(index)
            angle = original_angles[index]
            link = self.attachments.get(index)
            if link is not None:
                parent = int(link['parent'])
                if not 0 <= parent < n:
                    raise ValueError('An attachment references a missing body part.')
                angle += parent_angle(parent, visited)
            return angle

        for i in range(n):
            px, py, ax, ay = pivots[i]
            link = self.attachments.get(i)
            if link is not None:
                parent = int(link['parent'])
                if not 0 <= parent < n:
                    raise ValueError('An attachment references a missing body part.')
                px, py = point_through(parent, px, py)
            states[i]['x'] = round(px - ax)
            states[i]['y'] = round(py - ay)
            states[i]['angle'] = parent_angle(i)
        return states[:n]

    def render(self, pose=None):
        canvas = Image.new('RGBA', self.size)
        for i, state in enumerate(self.resolved_pose(pose)):
            if not state.get('visible', True):
                continue
            canvas.alpha_composite(self.render_part(i, state))
        return canvas

    def save_project(self, path):
        path = Path(path)
        folder = path.with_suffix('')
        folder.mkdir(parents=True, exist_ok=True)
        for i, image in enumerate(self.originals):
            image.save(folder / f'original_{i:03d}.png')
        data = dict(version=2, size=list(self.size), parts=self.snapshot(),
                    animations=self.animations, frame_durations=self.frame_durations, current=self.current, attachments=self.attachments, anchors=self.anchors, angles=self.angles)
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    @classmethod
    def load_project(cls, path):
        path = Path(path)
        data = json.loads(path.read_text(encoding='utf-8'))
        model = cls(data['size'])
        for i, state in enumerate(data['parts']):
            folder = path.with_suffix('')
            original_path = folder / f'original_{i:03d}.png'
            if not original_path.exists():
                original_path = folder / f'part_{i:03d}.png'  # v0.1 compatibility
            with Image.open(original_path) as image:
                model.import_part(state['name'], image,
                                  state.get('width', image.width), state.get('height', image.height))
            model.parts[-1]['x'] = int(state['x'])
            model.parts[-1]['y'] = int(state['y'])
            model.parts[-1]['visible'] = state.get('visible', True)
        model.animations = data.get('animations', {})
        model.frame_durations = data.get('frame_durations', {})
        for animation in model.animations: model._sync_durations(animation)
        model.current = data.get('current', 'Idle / Breathing')
        model.attachments = {int(k): v for k, v in data.get('attachments', {}).items()}
        model.anchors = {int(k): v for k, v in data.get('anchors', {}).items()}
        model.angles = {int(k): float(v) for k, v in data.get('angles', {}).items()}
        return model


    def content_fingerprint(self):
        """Stable digest of editable content, including original PNG pixels."""
        payload = dict(size=self.size, parts=self.snapshot(), animations=self.animations,
                       frame_durations=self.frame_durations, current=self.current,
                       anchors=self.anchors, angles=self.angles, attachments=self.attachments)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode('utf-8'))
        for original in self.originals:
            digest.update(str(original.size).encode('ascii'))
            digest.update(original.tobytes())
        return digest.hexdigest()

    def export(self, folder, basename='creature', columns=4, spacing=0):
        """Export a transparent atlas with real per-pose timing and pixel rectangles.

        This overrides CreatureRig.export, whose generic 125ms timing is not
        suitable for authored animation timelines. No live project data changes.
        """
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        frames, entries = [], []
        for animation, poses in self.animations.items():
            for index, pose in enumerate(poses):
                frames.append(self.render(pose).convert('RGBA'))
                entries.append({'animation': animation, 'frame': index,
                                'duration_ms': self.frame_duration(animation, index)})
        if not frames:
            frames = [self.render().convert('RGBA')]
            entries = [{'animation': 'Idle', 'frame': 0, 'duration_ms': 125}]
        columns = max(1, min(int(columns), len(frames)))
        spacing = max(0, int(spacing))
        width, height = self.size
        rows = math.ceil(len(frames) / columns)
        atlas = Image.new('RGBA', (columns * width + (columns - 1) * spacing,
                                   rows * height + (rows - 1) * spacing))
        for index, frame in enumerate(frames):
            x = (index % columns) * (width + spacing)
            y = (index // columns) * (height + spacing)
            atlas.alpha_composite(frame, (x, y))
            entries[index]['rect'] = {'x': x, 'y': y, 'w': width, 'h': height}
        png_path = folder / f'{basename}_sheet.png'
        json_path = folder / f'{basename}_sheet.json'
        atlas.save(png_path)
        json_path.write_text(json.dumps({'version': 1, 'frame_size': [width, height],
                                         'sheet_size': list(atlas.size), 'frames': entries},
                                        indent=2), encoding='utf-8')
        return png_path

    def export_animations(self, folder, basename='creature', gif=True, apng=True):
        """Export each saved animation as an actual timed, looping GIF and/or APNG."""
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        exported = []
        used_names = set()
        for animation, poses in self.animations.items():
            if not poses:
                continue
            frames = [self.render(pose).convert('RGBA') for pose in poses]
            durations = [self.frame_duration(animation, i) for i in range(len(poses))]
            safe = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in animation).strip('_') or 'animation'
            # Different animation labels can sanitize to the same filename.
            # Keep every export instead of silently overwriting an earlier one.
            candidate = safe
            suffix = 2
            while candidate.casefold() in used_names:
                candidate = f'{safe}_{suffix}'
                suffix += 1
            used_names.add(candidate.casefold())
            prefix = folder / f'{basename}_{candidate}'
            if gif:
                # GIF supports one-bit transparency and centisecond (10 ms) timing.
                # Build a shared palette so colors don't flicker between poses.
                from .gif_export import encode_gif
                output = prefix.with_suffix('.gif')
                encode_gif(frames, durations, output)
                exported.append(output)
            if apng:
                output = prefix.with_suffix('.png')
                from .apng_export import encode_apng
                encode_apng(frames, durations, output)
                exported.append(output)
        if not exported:
            raise ValueError('Add and save at least one animation pose before exporting.')
        return exported

    def reorder_part(self, index, offset):
        target = index + offset
        if not (0 <= index < len(self.parts) and 0 <= target < len(self.parts)):
            return False
        self.parts[index], self.parts[target] = self.parts[target], self.parts[index]
        self.originals[index], self.originals[target] = self.originals[target], self.originals[index]
        for frames in self.animations.values():
            for pose in frames:
                if index < len(pose) and target < len(pose):
                    pose[index], pose[target] = pose[target], pose[index]
        def remap(i):
            return target if i == index else index if i == target else i
        self.attachments = {remap(child): {**link, 'parent': remap(link['parent'])}
                            for child, link in self.attachments.items()}
        self.anchors = {remap(i): anchor for i, anchor in self.anchors.items()}
        self.angles = {remap(i): angle for i, angle in self.angles.items()}
        return True
