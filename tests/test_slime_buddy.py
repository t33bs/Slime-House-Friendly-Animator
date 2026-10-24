import unittest
from studio.slime_buddy import STATIONS,station_guide,motion_tip
from studio.pet_suite_templates import TEMPLATES
class BuddyTests(unittest.TestCase):
 def test_all_stations_have_help(self):
  for station in STATIONS:
   text=station_guide(station)
   self.assertIn('How:',text)
   self.assertIn('Creative freedom:',text)
 def test_every_recipe_and_frame_has_optional_idea(self):
  for action,steps in TEMPLATES.items():
   for i in range(len(steps)):
    self.assertIn('not a rule',motion_tip(action,i))
 def test_no_anatomy_enforcement(self):
  for station in STATIONS:
   self.assertNotIn('must have legs',station_guide(station).lower())
 def test_unknown_station(self):
  with self.assertRaises(KeyError): station_guide('No station')
if __name__=='__main__':unittest.main()
