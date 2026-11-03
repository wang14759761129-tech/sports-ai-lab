import unittest
from vision.motion_twin_contract import validate_pose, angle_degrees, validate_rally, replay_action, evidence_limited_observation
class MotionContractTest(unittest.TestCase):
 def setUp(self):
  self.p={'schema':'ptti.pose-evidence/1','source':'MODEL_INFERENCE','coordinate_space':'NORMALIZED_IMAGE_2D','video_sha256':'a'*64,'topology':'MEDIAPIPE_POSE_33','model':{'name':'test','sha256':'b'*64},'duration_seconds':12,'frames':[{'time_seconds':0,'landmarks':[None]*33}]}
 def test_33_and_missing(self): self.assertIs(validate_pose(self.p),self.p)
 def test_topology_cannot_forge_33(self):
  self.p['topology']='HALPE_26'
  with self.assertRaises(ValueError): validate_pose(self.p)
 def test_reject_fake_or_bad_times(self):
  self.p['source']='SIMULATED'
  with self.assertRaises(ValueError): validate_pose(self.p)
  self.p['source']='MODEL_INFERENCE';self.p['frames'][0]['time_seconds']=13
  with self.assertRaises(ValueError): validate_pose(self.p)
 def test_angles_and_confidence(self):
  a={'x':1,'y':0,'confidence':1}; v={'x':0,'y':0,'confidence':1}; b={'x':0,'y':1,'confidence':1}
  self.assertAlmostEqual(angle_degrees(a,v,b,1920,1080),90)
  b['confidence']=0.2;self.assertIsNone(angle_degrees(a,v,b,1920,1080));self.assertIn('暂不能判断',evidence_limited_observation([b]))
 def test_rally_bounds_and_stop(self):
  r={'video_sha256':'a'*64,'start_seconds':0,'end_seconds':4,'source':'MANUAL_USER_RECORDED'}
  self.assertEqual(validate_rally(r,12,'a'*64),(0,4));self.assertEqual(replay_action(4,0,4),'PAUSE')
  with self.assertRaises(ValueError): validate_rally(r,12,'b'*64)
  r['end_seconds']=13
  with self.assertRaises(ValueError): validate_rally(r,12,'a'*64)
if __name__=='__main__': unittest.main()
