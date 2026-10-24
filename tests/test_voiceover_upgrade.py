"""Neural narration integration: never relabel offline speech as neural."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import unittest
import numpy as np
from scripts.upgrade_social_voiceovers import SPEECH, SR, fit_clip, mix


class NarrationUpgradeTests(unittest.TestCase):
    def test_three_distinct_voices_and_short_scripts(self):
        self.assertEqual(len(SPEECH),3)
        self.assertEqual(len({v['voice'] for v in SPEECH.values()}),3)
        for name,cfg in SPEECH.items():
            self.assertEqual(len(cfg['lines']),3)
            self.assertEqual(len(cfg['styles']),3)
            self.assertEqual(len(cfg['start']),3)
            self.assertTrue(cfg['start'][0]>=0)
            self.assertLess(cfg['start'][-1],cfg['duration']-1)
            self.assertTrue(all(cfg['start'][i]<cfg['start'][i+1] for i in range(2)))
            self.assertTrue(all(len(line)<90 for line in cfg['lines']))

    def test_prevent_speech_truncation(self):
        with self.assertRaisesRegex(ValueError,'shorten script'):
            fit_clip(np.ones(3*SR,dtype=np.float32),1)

    def test_audio_segment_and_five_cues_are_finite(self):
        cfg=SPEECH['04_dino_donut_dash']
        clips=[np.full(int(.55*SR), .13, dtype=np.float32) for _ in range(3)]
        mixed, spans=mix(cfg,clips,[1.3,3.3,5.4,7.3,9.2])
        self.assertEqual(len(mixed),SR*cfg['duration'])
        self.assertEqual(len(spans),3)
        self.assertTrue(np.all(np.isfinite(mixed)))
        self.assertLess(np.max(np.abs(mixed)),1)
        self.assertGreater(np.max(np.abs(mixed)),.02)

    def test_no_gemini_key_means_explicit_failure_not_automated_fallback(self):
        script=Path(__file__).resolve().parents[1]/'scripts'/'upgrade_social_voiceovers.py'
        env={k:v for k,v in os.environ.items() if k not in ('GEMINI_API_KEY','GOOGLE_API_KEY')}
        p=subprocess.run([sys.executable,str(script),'--provider','gemini','--allow-paid-tts'],
                         capture_output=True,text=True,env=env)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('GEMINI_API_KEY',p.stderr)


if __name__=='__main__':
    unittest.main()
