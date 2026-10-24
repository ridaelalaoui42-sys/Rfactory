"""Rfactory social motion must pass exact slots without EVER pausing/revealing."""
import unittest

from scripts.social_motion import fit_frames, pose_at_frame, validate_schedule


class SocialMotionTest(unittest.TestCase):
    def test_five_single_frame_exact_matches_and_continuous_departure(self):
        for style,duration in (("orbit",8),("bounce",9),("zigzag",10)):
            config={"duration":duration,"move":style,"speed":1.20,
                    "fit_count":5,"hold_frames":0,"seed":38719+duration,
                    "first_fit":1.08,"last_fit":duration-.72}
            with self.subTest(style=style):
                scheduled=fit_frames(config)
                report=validate_schedule(config)
                self.assertEqual(report["fit_frames"],scheduled)
                self.assertEqual(len(scheduled),5)
                self.assertEqual(report["hold_frames"],0)
                self.assertEqual(report["exact_fit_frames_per_event"],1)
                self.assertTrue(report["continuous_motion"])
                self.assertTrue(report["no_visual_match_indicators"])
                self.assertFalse(report["final_frame_solved"])
                observed=[]
                for frame in range(duration*24):
                    pose=pose_at_frame(frame,config)
                    if pose.fit: observed.append(frame)
                    self.assertFalse(pose.final)
                    if frame not in scheduled:
                        self.assertNotEqual((pose.dx,pose.dy),(0,0))
                self.assertEqual(observed,scheduled)
                for index,at in enumerate(scheduled):
                    self.assertEqual((pose_at_frame(at,config).dx,
                                      pose_at_frame(at,config).dy),(0,0))
                    self.assertFalse(pose_at_frame(at-1,config).fit)
                    self.assertFalse(pose_at_frame(at+1,config).fit)
                    self.assertGreater(abs(pose_at_frame(at-1,config).dx)+
                                       abs(pose_at_frame(at-1,config).dy),2)
                    self.assertGreater(abs(pose_at_frame(at+1,config).dx)+
                                       abs(pose_at_frame(at+1,config).dy),2)
                self.assertNotEqual((pose_at_frame(duration*24-1,config).dx,
                                     pose_at_frame(duration*24-1,config).dy),(0,0))

    def test_deterministic_seed_and_irregular_intervals(self):
        c={"duration":10,"move":"orbit","speed":1.2,"fit_count":5,
           "first_fit":1.0,"last_fit":9.0,"hold_frames":0,"seed":48152}
        a=fit_frames(c)
        self.assertEqual(a,fit_frames(c))
        self.assertGreater(len(set(b-a for a,b in zip(a,a[1:]))),1)
        changed=dict(c,seed=48153)
        self.assertNotEqual(a,fit_frames(changed))

    def test_old_five_frame_hold_is_rejected_not_silently_preserved(self):
        with self.assertRaisesRegex(ValueError,"forbidden"):
            fit_frames({"duration":8,"fit_count":5,"hold_frames":5})
        with self.assertRaises(ValueError):
            fit_frames({"duration":6,"fit_count":12})
        with self.assertRaises(ValueError):
            fit_frames({"duration":8,"fit_count":5,"first_fit":7,"last_fit":7.5})
        with self.assertRaises(ValueError):
            pose_at_frame(0,{"duration":8,"speed":float("nan")})


if __name__=="__main__":
    unittest.main()
