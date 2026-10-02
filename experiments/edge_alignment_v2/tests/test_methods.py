"""Synthetic checks for the v2 alignment methods (no image data needed).

    python -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from src import common, homography, piecewise, tps  # noqa: E402

# Marker layout of the real reference form (2000 px working height).
MARKERS = np.array([[1051.5, 99.], [114., 109.5], [342.5, 193.5], [1048.5, 415.], [344.5, 451.5],
                    [652.5, 1010.5], [117.5, 1016.5], [680.5, 1094.5], [1362.5, 1891.5], [705., 1893.5]])
H_TRUE = np.array([[.9, .01, -8.], [-.005, .92, 15.], [2e-6, -1e-6, 1.]])


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

    def test_associate_missing_ring_does_not_steal_neighbours(self):
        # A column of 5 bubbles 28 px apart; bubble 0 (top) is pencil-filled so its ring was not detected.
        # A spare candidate lies 300 px below the column, i.e. closer to the bottom bubble than to the top
        # one. Plain Hungarian then prefers the chain 0<-1<-2<-3<-4<-spare (total ~408 px) over giving
        # the spare to bubble 0 (~419 px), and bubbles 1-4 all lose their own ring.
        pred = np.array([[100., 100. + 28 * k] for k in range(5)])
        candidates = np.vstack([pred[1:] + [1.5, -1.], [[100., pred[-1, 1] + 300.]]])
        _, valid = common.associate(pred, candidates)
        self.assertEqual(valid.tolist(), [False, True, True, True, True])

    def test_associate_rejects_ambiguous_and_far(self):
        pred = np.array([[0., 0.], [100., 100.], [200., 200.]])
        cand = np.array([[-1., 0.], [1., 0.], [101., 100.], [230., 200.]])
        _, valid = common.associate(pred, cand)
        self.assertEqual(valid.tolist(), [False, True, False])

    def test_guard_keeps_ransac_when_one_marker_is_grossly_wrong(self):
        dst = common.warp_points(H_TRUE, MARKERS)
        dst[3] += [80., -60.]                      # e.g. a stain detected as a marker
        _, H, inl, info = homography.fit_checked(MARKERS, dst)
        self.assertEqual(info["used"], "ransac")
        self.assertFalse(inl[3])
        np.testing.assert_allclose(common.warp_points(H, MARKERS[[0, 8]]),
                                   common.warp_points(H_TRUE, MARKERS[[0, 8]]), atol=.5)

    def test_guard_falls_back_on_the_real_shadowed_phone_photo(self):
        # Markers detected in app/uploads/20260928-170100-603280 (reference marker 6 not found).
        ids = [0, 1, 2, 3, 4, 5, 7, 8, 9]
        dst = np.array([[947., 125.], [95.5, 107.], [303.5, 206.], [946., 438.5], [307., 471.5],
                        [587., 1041.], [610.5, 1123.], [1230., 1916.], [636.5, 1916.5]])
        H_all, H, inl, info = homography.fit_checked(MARKERS[ids], dst)
        self.assertEqual(info["used"], "all_markers")
        np.testing.assert_allclose(H, H_all)
        self.assertTrue(inl.all())
        residual = np.linalg.norm(common.warp_points(H, MARKERS[ids]) - dst, axis=1)
        self.assertLess(residual.max(), 10)         # RANSAC's own H was off by up to 119 px here

    def test_guard_keeps_a_well_spread_ransac_subset(self):
        # Curved paper: markers genuinely disagree, but RANSAC's subset is spread over the page.
        dst = common.warp_points(H_TRUE, MARKERS)
        dst[[1, 2, 4, 6]] += [[9., -7.], [-8., 6.], [7., 8.], [-9., -6.]]
        _, _, inl, info = homography.fit_checked(MARKERS, dst)
        self.assertEqual(info["used"], "ransac")
        self.assertLessEqual(int(inl[[1, 2, 4, 6]].sum()), 1)   # most shifted markers dropped, H still trusted

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
