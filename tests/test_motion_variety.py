import unittest
from studio.reference_animation import reference_frame
from studio.pet_suite_templates import TEMPLATES

class MotionVarietyTests(unittest.TestCase):
    def test_all_recipes_all_body_types_render(self):
        for name,steps in TEMPLATES.items():
            for body in ('Biped','Quadruped','Floating'):
                for i in range(len(steps)):
                    with self.subTest(name=name,body=body,frame=i):
                        img=reference_frame(name,i,body_type=body)
                        self.assertEqual(img.size,(128,128))
                        self.assertEqual(img.mode,'RGBA')
                        self.assertIsNotNone(img.getbbox())
    def test_distinct_quadruped_actions(self):
        a=reference_frame('Walking',1,body_type='Quadruped')
        b=reference_frame('Sleeping',1,body_type='Quadruped')
        self.assertNotEqual(a.tobytes(),b.tobytes())
    def test_distinct_floating_actions(self):
        a=reference_frame('Looking Around',1,body_type='Floating')
        b=reference_frame('Sleeping',1,body_type='Floating')
        self.assertNotEqual(a.tobytes(),b.tobytes())
    def test_repeatable_and_wrapped(self):
        for body in ('Biped','Quadruped','Floating'):
            n=len(TEMPLATES['Walking'])
            self.assertEqual(reference_frame('Walking',2,body_type=body).tobytes(),reference_frame('Walking',2+n,body_type=body).tobytes())

if __name__=='__main__': unittest.main()
