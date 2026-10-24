"""Geometry and advanced continuous-motion regression tests; no API access."""
import unittest
import numpy as np

from services.engine.puzzle_geometry import (
    GEOMETRIES, cut_exact_fragment, cut_multiple_fragments,
)
from services.engine.motion_profiles import (
    MOTION_PROFILES, continuous_motion_pose,
)
from services.engine.snap_timeline import build_crossing_timeline


class AdvancedGeometryTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(328)
        self.source=rng.integers(0,256,(310,420,4),dtype=np.uint8)
        self.source[:,:,-1]=255

    def test_eight_masks_restore_canonical_image_pixel_for_pixel(self):
        for name in GEOMETRIES:
            with self.subTest(name=name):
                frag=cut_exact_fragment(self.source,(135,90,140,120),name,seed=97)
                self.assertEqual(frag.mask.dtype,np.uint8)
                self.assertTrue(set(np.unique(frag.mask)).issubset({0,255}))
                self.assertTrue(np.array_equal(frag.reconstruct(),self.source))
                self.assertEqual(frag.piece_rgba[0,0,3],0)
                self.assertGreater(np.count_nonzero(frag.mask),100)

    def test_reference_hash_prevents_cross_asset_contamination(self):
        fragment=cut_exact_fragment(self.source,(130,100,120,110),"jigsaw")
        replaced=self.source.copy();replaced[5,5,0]^=1
        with self.assertRaises(ValueError):
            fragment.validate_against(replaced)

    def test_multi_piece_three_subject_regions_restore_original(self):
        base,fragments=cut_multiple_fragments(self.source,[
            ((15,25,100,110),"jigsaw",12),
            ((152,65,120,140),"organic",13),
            ((305,180,100,100),"ring_sector",14),
        ])
        self.assertEqual(len(fragments),3)
        restored=base.copy()
        for frag in fragments:
            x,y,w,h=frag.bounds_xywh
            restored[y:y+h,x:x+w][frag.mask>0]=frag.piece_rgba[frag.mask>0]
        self.assertTrue(np.array_equal(restored,self.source))

    def test_overlapping_targets_fail_closed(self):
        with self.assertRaises(ValueError):
            cut_multiple_fragments(self.source,[
                ((140,120,140,120),"ellipse",0),
                ((145,125,140,120),"organic",1),
            ])

    def test_traversal_and_invalid_geometry_rejected(self):
        with self.assertRaises(ValueError):
            cut_exact_fragment(self.source,(390,300,120,120))
        with self.assertRaises(ValueError):
            cut_exact_fragment(self.source,(50,50,80,80),"invalid")
        with self.assertRaises(ValueError):
            cut_multiple_fragments(self.source,[])


class SixteenMotionFamiliesTests(unittest.TestCase):
    def test_16_distinct_profiles_all_cross_exactly(self):
        self.assertGreaterEqual(len(MOTION_PROFILES),16)
        sigs=set()
        for name in MOTION_PROFILES:
            with self.subTest(name=name):
                exact=continuous_motion_pose(name,0.5,travel_px=270,seed=89)
                self.assertTrue(exact.identity)
                self.assertTrue(exact.locked)
                before=continuous_motion_pose(name,.497,270,seed=89)
                after=continuous_motion_pose(name,.503,270,seed=89)
                self.assertFalse(before.identity)
                self.assertFalse(after.identity)
                start=continuous_motion_pose(name,0.0,270,seed=89)
                end=continuous_motion_pose(name,1.0,270,seed=89)
                self.assertEqual(start,end)
                probe=continuous_motion_pose(name,0.15,270,seed=89)
                key=(probe.dx,probe.dy,probe.angle_deg,probe.scale_x,probe.scale_y)
                self.assertNotIn(key,sigs,"Profiles must be visually distinct")
                sigs.add(key)

    def test_video_timeline_avoids_solved_hold(self):
        time=build_crossing_timeline(total_frames=360,fps=30,count=5,seed=912)
        for part in time.passes:
            fit=part.first_locked_frame
            self.assertEqual(fit,part.last_locked_frame)
            self.assertFalse(time.is_locked(fit-1))
            self.assertTrue(time.is_locked(fit))
            self.assertFalse(time.is_locked(fit+1))

    def test_motion_parameters_reject_nan(self):
        for bad in (float("nan"),float("inf"),float("-inf"),0,-2):
            with self.assertRaises(ValueError):
                continuous_motion_pose("helix",0.24,travel_px=bad)
