"""Phase 4 complete regression edge cases."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from studio.pet_suite_model import PetSuiteModel

class ExportRegressions(unittest.TestCase):
    def make_model(self):
        model = PetSuiteModel((16, 16))
        img = Image.new('RGBA', (3, 3), (255, 0, 0, 255))
        model.import_part('blob', img)
        first = model.snapshot()
        second = model.snapshot()
        second[0]['x'] = 8
        return model, [first, second]

    def test_sanitized_names_do_not_overwrite(self):
        model, poses = self.make_model()
        model.animations['run/walk'] = poses
        model.animations['run?walk'] = poses
        model.animations['RUN_WALK'] = poses
        with tempfile.TemporaryDirectory() as folder:
            outputs = model.export_animations(folder)
            self.assertEqual(len(outputs), 6)
            self.assertEqual(len({p.name.casefold() for p in outputs}), 6)
            self.assertTrue(all(p.exists() and p.stat().st_size for p in outputs))

    def test_no_saved_poses_gives_clear_error(self):
        model, _ = self.make_model()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'save at least one animation pose'):
                model.export_animations(folder)

    def test_apng_only_and_gif_only(self):
        model, poses = self.make_model()
        model.animations['idle'] = poses
        with tempfile.TemporaryDirectory() as folder:
            apng = model.export_animations(folder, gif=False)
            self.assertEqual([p.suffix for p in apng], ['.png'])
            gif = model.export_animations(folder, apng=False)
            self.assertEqual([p.suffix for p in gif], ['.gif'])
            for path in apng + gif:
                with Image.open(path) as img:
                    self.assertEqual(img.n_frames, 2)

if __name__ == '__main__': unittest.main()
