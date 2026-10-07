"""Checks for the silent-error guards in pipeline.py (no photos needed)."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline  # noqa: E402


class Checks(unittest.TestCase):
    def test_bubbles_outside_or_on_the_photo_border_are_not_visible(self):
        centres = np.array([[100., 100.], [100., 1995.], [100., 2050.], [5., 500.], [700., 1986.]])
        visible = pipeline.visible_bubbles(centres, (2000, 1400, 3))
        self.assertEqual(visible.tolist(), [True, False, False, False, True])


if __name__ == "__main__":
    unittest.main()
