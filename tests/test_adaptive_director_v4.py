"""Tests for the optional, topic-aware CTRL PULSE V4 motion module."""
import unittest
from adaptive_director.router import choose_style,plan,RenderGateError

class AdaptiveDirectorTests(unittest.TestCase):
    def test_topic_selection(self):
        x=['AI software product launch','investigation news evidence','science history art','circuit algorithm tutorial','funny psychology story']
        self.assertEqual([choose_style(t)['module'] for t in x],['bang','vox','huashu','drawing','stickman'])
    def test_override(self):
        self.assertEqual(choose_style('software product',override='vox')['module'],'vox')
    def test_unknown_style(self):
        with self.assertRaises(RenderGateError):choose_style('testing',override='slide-deck')
    def test_minimum_resolution(self):
        with self.assertRaises(RenderGateError):plan('a',[{'start':0,'end':2}],brand={'width':720,'height':1280})
    def test_no_subtitles(self):
        with self.assertRaises(RenderGateError):plan('a',[{'start':0,'end':2}],brand={'subtitles':True})
    def test_timeline_contiguous(self):
        with self.assertRaises(RenderGateError):plan('a',[{'start':0,'end':2},{'start':3,'end':5}])
    def test_native_frame(self):
        try:import PIL
        except ImportError:self.skipTest('optional Pillow renderer not installed')
        from adaptive_director.visuals import draw_frame,draw_module_frame
        self.assertEqual(draw_frame(2).size,(1080,1920))
        self.assertEqual(draw_module_frame('vox',0.5).size,(1080,1920))
    def test_temporal_motion(self):
        try:import PIL
        except ImportError:self.skipTest('optional Pillow renderer not installed')
        from adaptive_director.visuals import draw_module_frame
        for style in ['bang','vox','huashu','drawing','stickman']:
            a=draw_module_frame(style,1).resize((100,178))
            b=draw_module_frame(style,1.45).resize((100,178))
            self.assertNotEqual(a.tobytes(),b.tobytes())

if __name__=='__main__':unittest.main()
