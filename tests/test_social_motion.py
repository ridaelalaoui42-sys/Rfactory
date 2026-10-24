"""Regression: moving source pixel piece must fit repeatedly, not only at the end."""
import unittest
from scripts.social_motion import fit_frames, pose_at_frame, validate_schedule

class SocialMotionTest(unittest.TestCase):
 def test_five_accurate_matches_per_video(self):
  for mode,duration in [('orbit',8),('bounce',9),('zigzag',10)]:
   cfg={'duration':duration,'move':mode,'speed':1.2,'fit_count':5,'hold_frames':5}
   with self.subTest(mode=mode):
    times=fit_frames(cfg)
    self.assertEqual(len(times),5)
    self.assertEqual(validate_schedule(cfg)['fit_count'],5)
    for number,center in enumerate(times,1):
     for frame in range(center-2,center+3):
      pose=pose_at_frame(frame,cfg)
      self.assertEqual((pose.dx,pose.dy),(0,0))
      self.assertTrue(pose.fit)
      self.assertEqual(pose.fit_number,number)
    for a,b in zip(times,times[1:]):
     self.assertGreater(max(abs(pose_at_frame(f,cfg).dx)+abs(pose_at_frame(f,cfg).dy)
                            for f in range(a+3,b-3)),70)
 def test_bad_fit_schedule_rejected(self):
  with self.assertRaises(ValueError):
   fit_frames({'duration':6,'fit_count':12})
  with self.assertRaises(ValueError):
   fit_frames({'duration':8,'fit_count':5,'first_fit':7,'last_fit':7.5})

if __name__=='__main__':unittest.main()