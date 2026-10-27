import tempfile
import unittest
from pathlib import Path
from PIL import Image
from studio.user_reference import read_reference

class UserReferenceTests(unittest.TestCase):
    def test_single_png(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'sprite.png';Image.new('RGBA',(128,128)).save(p)
            frames=read_reference(p)
            self.assertEqual(len(frames),1)
            self.assertEqual(frames[0][0].size,(128,128))
    def test_sheet_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'sheet.png';Image.new('RGBA',(256,128)).save(p)
            frames=read_reference(p,2,1)
            self.assertEqual(len(frames),2)
            self.assertEqual(frames[0][0].size,(128,128))
    def test_bad_sheet_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'sheet.png';Image.new('RGBA',(255,128)).save(p)
            with self.assertRaises(ValueError):read_reference(p,2,1)
