"""Synthetic checks for reading.py (no photos needed).

    .venv/bin/python -m unittest discover -s app/tests
"""
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reading  # noqa: E402

PINK = (180, 120, 230)            # BGR of the printed form ink


def sheet(paper=235, shadow=False, marks=(), mark_gray=60, n=200):
    """n bubbles on a grid with pink rings and letters; marks = indices filled with pencil."""
    im = np.full((900, 700, 3), paper, np.uint8)
    centres = np.array([[60 + 30 * (i % 20), 60 + 40 * (i // 20)] for i in range(n)], float)
    for i, (x, y) in enumerate(centres.astype(int)):
        cv2.circle(im, (x, y), 10, PINK, 2)
        cv2.putText(im, "ABCDE"[i % 5], (x - 5, y + 5), cv2.FONT_HERSHEY_SIMPLEX, .45, PINK, 1)
        if i in marks:
            cv2.circle(im, (x, y), 9, (mark_gray,) * 3, -1)
    if paper < 235:                                      # dark photo: everything (ink too) gets darker
        im = (im.astype(float) * paper / 235).astype(np.uint8)
    if shadow:                                           # sharp-edged shadow falls on top of everything
        yy, xx = np.mgrid[:900, :700]
        im = (im * np.where(xx + yy > 500, .6, 1.)[..., None]).astype(np.uint8)
    return im, centres


class Reading(unittest.TestCase):
    def read(self, im, centres):
        """Every 5 consecutive bubbles are one question (A..E). Returns per-bubble marked flag and contrast."""
        scores = reading.bubble_scores(im, centres)
        questions = [scores[i:i + 5] for i in range(0, len(scores), 5)]
        t, weak_below, info = reading.sheet_threshold(questions)
        contrast = np.concatenate([reading.row_contrast(q) for q in questions])
        return contrast >= t, contrast, t, weak_below, info

    def test_printed_pink_letters_are_not_marks_even_on_a_dark_photo(self):
        marks = set(range(0, 200, 7))
        for paper in (235, 170):                         # normal and very dark photo
            im, c = sheet(paper=paper, marks=marks)
            marked, *_ = self.read(im, c)
            self.assertEqual(set(np.where(marked)[0]), marks, f"paper={paper}")

    def test_shadow_does_not_create_or_hide_marks(self):
        marks = set(range(3, 200, 9))
        im, c = sheet(shadow=True, marks=marks)
        marked, *_ = self.read(im, c)
        self.assertEqual(set(np.where(marked)[0]), marks)

    def test_light_pencil_is_found_and_reported_weak(self):
        dark, light = set(range(0, 100, 6)), set(range(101, 200, 6))
        im, c = sheet(marks=dark)
        for i in light:                                  # add light gray marks
            x, y = c[i].astype(int)
            cv2.circle(im, (x, y), 9, (175, 175, 175), -1)
        marked, scores, t, weak_below, _ = self.read(im, c)
        self.assertEqual(set(np.where(marked)[0]), dark | light)
        self.assertTrue(all(scores[i] < weak_below for i in light))
        self.assertTrue(all(scores[i] >= weak_below for i in dark))

    def test_camera_that_darkens_empty_bubbles_does_not_hide_gray_pencil(self):
        """Redmi photos: empty bubbles look darker (and unevenly so), pencil stays gray. The old per-sheet
        threshold (median + 6 MAD) missed these gray marks; the row contrast finds them."""
        marks = set(range(1, 200, 5))
        im, c = sheet(marks=marks, mark_gray=150)
        for i in set(range(200)) - marks:                # gray haze in every empty bubble, darker down the sheet
            x, y = c[i].astype(int)
            cv2.circle(im, (x, y), 9, (int(185 + 45 * y / 900),) * 3, -1)
        marked, *_ = self.read(im, c)
        self.assertEqual(set(np.where(marked)[0]), marks)

    def test_blank_sheet_reads_nothing(self):
        im, c = sheet(marks=())
        marked, *_ = self.read(im, c)
        self.assertFalse(marked.any())

    def test_two_equal_marks_are_ambiguous_one_faint_extra_is_not(self):
        t, weak = .2, .4
        self.assertEqual(reading.decide(np.array([.05, .6, .05, .6, .05]), t, weak)[:2], ("ambiguous", "BD"))
        self.assertEqual(reading.decide(np.array([.05, .6, .05, .22, .05]), t, weak)[:2], ("single", "B"))
        self.assertEqual(reading.decide(np.array([.05, .05, .05, .05, .05]), t, weak)[:2], ("blank", None))


if __name__ == "__main__":
    unittest.main()
