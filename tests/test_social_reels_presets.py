"""Smoke-check three family-friendly social reel presets, no artwork required."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]

class SocialReelsPresetTests(unittest.TestCase):
    def test_metadata(self):
        data=json.loads((ROOT/'config'/'social_reels_preset_2026_10.json').read_text())
        self.assertEqual((data['output']['width'],data['output']['height']), (1080,1920))
        self.assertEqual(data['output']['fps'],24)
        reels=data['presets']
        self.assertEqual(len(reels),3)
        self.assertEqual(len(set(c['name'] for c in reels)),3)
        self.assertEqual({c['puzzle'] for c in reels},{'circle','wedge','eye_band'})
        self.assertEqual(data['motionVersion'],'single-frame-continuous-v3')
        for c in reels:
            self.assertTrue(4 <= c['duration'] <= 15)
            self.assertEqual(c['holdFrames'],0)
            self.assertIsInstance(c['seed'],int)
            self.assertIn(c['motion'],{'orbit','bounce','zigzag'})
            self.assertNotIn('{',c['headline'])
            self.assertIn('__',c['subject'])

if __name__=='__main__':unittest.main()
