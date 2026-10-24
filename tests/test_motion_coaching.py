import unittest
from studio.pose_guidance import technique_hint, TECHNIQUES
from studio.pet_suite_templates import TEMPLATES

class CoachingTests(unittest.TestCase):
 def test_all_recipes_have_specific_techniques(self):
  self.assertEqual(set(TECHNIQUES),set(TEMPLATES))
  for name,steps in TEMPLATES.items():
   for index,step in enumerate(steps):
    hint=technique_hint(name,index)
    self.assertIn(step,hint)
    self.assertIn('Optional',hint)
 def test_body_types_have_distinct_optional_guidance(self):
  hints={kind:technique_hint('Walking',1,kind) for kind in ('Biped','Quadruped','Floating','Custom')}
  self.assertEqual(len(set(hints.values())),4)
 def test_never_prescribes_anatomy_or_scores_art(self):
  for name in TEMPLATES:
   text=technique_hint(name,0)
   self.assertIn('your choice',text)
   self.assertNotIn('incorrect',text.lower())
 def test_invalid_inputs(self):
  with self.assertRaises(KeyError): technique_hint('Not a recipe',0)
  with self.assertRaises(ValueError): technique_hint('Walking',0,'Unrecognized')
 def test_legacy_interface(self):
  from studio.pose_guidance import pose_hint
  self.assertIn('Walking', 'Walking')
  self.assertIn('Contact left',pose_hint('Walking',0))
