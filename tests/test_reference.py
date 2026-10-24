import unittest
from studio.pet_suite_templates import TEMPLATES
from studio.reference_animation import reference_frame

class ReferenceTests(unittest.TestCase):
    def test_all_recipes_have_reference_frames(self):
        for action,steps in TEMPLATES.items():
            for i in range(len(steps)):
                image=reference_frame(action,i)
                self.assertEqual(image.size,(128,128))
                self.assertIsNotNone(image.getbbox())
    def test_loop_wrap(self):
        self.assertEqual(reference_frame('Walking',0).tobytes(),reference_frame('Walking',6).tobytes())
    def test_motion_varies(self):
        self.assertNotEqual(reference_frame('Walking',0).tobytes(),reference_frame('Walking',1).tobytes())

if __name__=='__main__':unittest.main()
