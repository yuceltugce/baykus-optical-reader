"""Small geometry checks for E1, runnable without image data."""
import unittest
import numpy as np
from edge_refinement import associate, residual_tps, warp

class GeometryChecks(unittest.TestCase):
 def test_projective_mapping(self):
  pts=np.array([[0.,0.],[100.,40.],[30.,150.]])
  H=np.array([[1.1,.02,12.],[-.03,.9,-4.],[.0001,.0002,1.]])
  projected=warp(H,pts)
  np.testing.assert_allclose(warp(np.linalg.inv(H),projected),pts,atol=1e-9)
 def test_residual_field_generalizes_to_unseen_points(self):
  anchors=np.array([[0.,0.],[100.,0.],[0.,100.],[100.,100.],[50.,50.]])
  query=np.array([[25.,20.],[75.,80.]])
  A=np.array([[.02,-.01],[.01,.03]])
  delta=anchors@A+np.array([2.,-3.])
  np.testing.assert_allclose(residual_tps(anchors,delta,query),query@A+[2.,-3.],atol=1e-8)
 def test_ambiguous_and_out_of_range_rejected(self):
  predicted=np.array([[0.,0.],[100.,100.],[200.,200.]])
  candidates=np.array([[-1.,0.],[1.,0.],[101.,100.],[230.,200.]])
  observed,valid=associate(predicted,candidates)
  self.assertEqual(valid.tolist(),[False,True,False])
  self.assertTrue(np.isnan(observed[0]).all())
 def test_no_duplicate_assignments(self):
  _,valid=associate(np.array([[0.,0.],[1.,0.]]),np.array([[0.,0.]]))
  self.assertEqual(valid.sum(),1)
 def test_degenerate_control_points_rejected(self):
  a=np.array([[0.,0.],[1.,0.],[2.,0.],[3.,0.]])
  with self.assertRaises(ValueError):residual_tps(a,np.zeros_like(a),a)

if __name__=='__main__':unittest.main()
