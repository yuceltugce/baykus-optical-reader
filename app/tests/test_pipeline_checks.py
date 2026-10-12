"""Checks for the silent-error guards in pipeline.py (no photos needed)."""
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline  # noqa: E402


class Checks(unittest.TestCase):
    def test_bubbles_outside_or_on_the_photo_border_are_not_visible(self):
        centres = np.array([[100., 100.], [100., 1995.], [100., 2050.], [5., 500.], [700., 1986.]])
        visible = pipeline.visible_bubbles(centres, (2000, 1400, 3))
        self.assertEqual(visible.tolist(), [True, False, False, False, True])

    def test_faint_marker_is_found_next_to_a_black_table(self):
        """One marker printed light and unevenly (one half ~36 %, the other ~25 % darker than paper, like the
        bottom-right one on some sheets), a black table strip in the photo, and small dark boxes that must not be
        taken for markers. The table pins the old threshold at 35 %, so only half the faint square survived."""
        common = pipeline.common
        im = np.full((2000, 1400, 3), 235, np.uint8)
        im[:, 1340:] = 20                                               # black table along the right edge
        for x, y in [(100, 100), (1200, 100), (100, 1800)]:
            cv2.rectangle(im, (x, y), (x + 24, y + 24), (60, 60, 60), -1)   # normal markers
        cv2.rectangle(im, (1200, 1800), (1211, 1824), (150, 150, 150), -1)  # faint marker, darker half
        cv2.rectangle(im, (1212, 1800), (1224, 1824), (175, 175, 175), -1)  # faint marker, lighter half
        for x in range(300, 900, 40):
            cv2.rectangle(im, (x, 1000), (x + 13, 1013), (60, 60, 60), -1)  # small boxes, ~14 px
        found = {}
        for method in ("base", "relative"):
            common.MARKER_METHOD, common.EXPECTED_MARKER_SIDE = method, 24.0
            found[method] = common.detect_markers(im)
        common.MARKER_METHOD = "relative"
        faint = lambda pts: bool(len(pts)) and np.linalg.norm(pts - [1212, 1812], axis=1).min() < 3
        self.assertFalse(faint(found["base"]))            # the old threshold loses it ...
        self.assertTrue(faint(found["relative"]))         # ... the relative one finds it
        self.assertEqual(len(found["relative"]), 4)       # and the small boxes are not markers


if __name__ == "__main__":
    unittest.main()
