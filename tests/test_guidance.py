import unittest
from studio.pose_guidance import pose_hint
from studio.reference_animation import reference_frame
from studio.pet_suite_templates import TEMPLATES
class GuideTests(unittest.TestCase):
 def test_all_recipes_have_guidance(self):
  for action,steps in TEMPLATES.items():
   for i in range(len(steps)):
    self.assertIn(steps[i],pose_hint(action,i))
 def test_optional_asset_tip(self):
  self.assertIn('your choice',pose_hint('Walking',0,[]))
  self.assertNotIn('import a separate',pose_hint('Walking',0,['Left Paw']))
 def test_reference_shapes_are_distinct(self):
  images=[reference_frame('Walking',1,body_type=t) for t in ('Biped','Quadruped','Floating')]
  self.assertEqual(len({i.tobytes() for i in images}),3)
 def test_reference_invalid_type(self):
  with self.assertRaises(ValueError): reference_frame('Walking',0,body_type='Unknown')
if __name__=='__main__': unittest.main()
