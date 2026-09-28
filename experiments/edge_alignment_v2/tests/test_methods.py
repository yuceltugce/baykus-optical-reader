"""Synthetic checks for the v2 alignment methods (no image data needed).

    python -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import common, piecewise, tps  # noqa: E402


def grid(x0, y0, rows=40, cols=5, step=(21, 21)):
    return np.array([[x0 + c * step[0], y0 + r * step[1]] for r in range(rows) for c in range(cols)], float)


class Methods(unittest.TestCase):
    def test_projective_roundtrip(self):
        pts = np.array([[0., 0.], [100., 40.], [30., 150.]])
        H = np.array([[1.1, .02, 12.], [-.03, .9, -4.], [.0001, .0002, 1.]])
        back = common.warp_points(np.linalg.inv(H), common.warp_points(H, pts))
        np.testing.assert_allclose(back, pts, atol=1e-9)

    def test_tps_reproduces_affine_field_on_unseen_points(self):
        anchors = np.array([[0., 0.], [100., 0.], [0., 100.], [100., 100.], [50., 50.]])
        A, t = np.array([[.02, -.01], [.01, .03]]), np.array([2., -3.])
        query = np.array([[25., 20.], [75., 80.]])
        np.testing.assert_allclose(tps.residual_tps(anchors, anchors @ A + t, query), query @ A + t, atol=1e-8)

    def test_tps_rejects_collinear_controls(self):
        a = np.array([[0., 0.], [1., 0.], [2., 0.], [3., 0.]])
        with self.assertRaises(ValueError):
            tps.residual_tps(a, np.zeros_like(a), a)

    def test_associate_rejects_ambiguous_and_far(self):
        pred = np.array([[0., 0.], [100., 100.], [200., 200.]])
        cand = np.array([[-1., 0.], [1., 0.], [101., 100.], [230., 200.]])
        _, valid = common.associate(pred, cand)
        self.assertEqual(valid.tolist(), [False, True, False])

    def test_piecewise_recovers_separate_block_homographies(self):
        # Two blocks, each moved by its own perspective; global H is identity.
        ref = np.vstack([grid(0, 0), grid(200, 0)])
        subjects = np.array(["a"] * 200 + ["b"] * 200)
        questions = np.tile(np.repeat(np.arange(1, 41), 5), 2)
        Ha = np.array([[1, .002, 3], [0, 1, 2], [0, 1e-6, 1]])
        Hb = np.array([[1, 0, -4], [.003, 1, 5], [1e-6, 0, 1]])
        truth = np.vstack([common.warp_points(Ha, ref[:200]), common.warp_points(Hb, ref[200:])])
        ctx = dict(ref_points=ref, base=ref.copy(), obs=truth, ok=np.ones(400, bool),
                   subjects=subjects, subject_names=["a", "b"], train_rows=questions % 5 == 1, fits={})
        pred = piecewise.predict(ctx)["piecewise_H"]
        np.testing.assert_allclose(pred, truth, atol=1e-3)
        self.assertEqual({f["status"] for f in ctx["fits"]["piecewise_H"].values()}, {"fitted"})

    def test_piecewise_falls_back_when_too_few_anchors(self):
        ref = grid(0, 0)
        ok = np.zeros(200, bool)
        ok[:5] = True
        ctx = dict(ref_points=ref, base=ref.copy(), obs=ref + 3, ok=ok, subjects=np.array(["a"] * 200),
                   subject_names=["a"], train_rows=np.ones(200, bool), fits={})
        pred = piecewise.predict(ctx)["piecewise_H"]
        np.testing.assert_allclose(pred, ref)
        self.assertEqual(ctx["fits"]["piecewise_H"]["a"]["status"], "fallback_to_H")


if __name__ == "__main__":
    unittest.main()
