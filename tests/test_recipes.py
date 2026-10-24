import unittest
from studio.pet_suite_templates import TEMPLATES

class RecipeTests(unittest.TestCase):
    def test_all_31_everyday_recipes(self):
        self.assertEqual(len(TEMPLATES),31)
        for name,frames in TEMPLATES.items():
            self.assertTrue(name)
            self.assertGreaterEqual(len(frames),3)
            self.assertTrue(all(isinstance(frame,str) and frame.strip() for frame in frames))
