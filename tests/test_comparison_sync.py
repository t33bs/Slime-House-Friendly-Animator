import unittest
from studio.comparison_sync import comparison_position

class SyncTests(unittest.TestCase):
    def test_start_and_variable_duration(self):
        self.assertEqual(comparison_position([100,300,100],0,5),(0,0))
        self.assertEqual(comparison_position([100,300,100],150,5),(1,1))
        self.assertEqual(comparison_position([100,300,100],450,5),(2,4))
    def test_loop(self):
        self.assertEqual(comparison_position([100,200],350,4),(0,0))
    def test_nonloop_holds_last(self):
        self.assertEqual(comparison_position([100,200],999,4,False),(1,3))
    def test_empty(self):
        self.assertEqual(comparison_position([],0,6),(None,0))
    def test_invalid(self):
        with self.assertRaises(ValueError):comparison_position([100],0,0)
    def test_reference_independent_of_frame_count(self):
        self.assertEqual(comparison_position([250,250],375,8),(1,6))
