"""No visual reveal or hidden sound ticker at social-puzzle fit events."""
from __future__ import annotations
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import wave

import numpy as np
from PIL import Image

from scripts.render_social_reels import frame, make_audio
from scripts.social_motion import MotionPose, validate_schedule


class SocialMediaNoHintTests(unittest.TestCase):
    def test_match_flag_never_changes_exported_pixels(self):
        # Exactly identical pose/time/assets, different fit flags: exported
        # frame must not contain any solve-specific visual indicator.
        empty=Image.new("RGBA",(60,60),(0,0,0,0))
        subject=Image.new("RGBA",(60,60),(210,130,44,255))
        bg=Image.new("RGBA",(720,1280),(12,22,40,255))
        parts=(empty,subject,empty,empty,bg,None,subject)
        cfg={"duration":8,"sparkles":4}
        normal=(0,0,MotionPose(0,0,False,0,5,False))
        fit=(0,0,MotionPose(0,0,True,3,5,False))
        final=(0,0,MotionPose(0,0,True,5,5,True))
        output=[]
        for mock in (normal,fit,final):
            with patch("scripts.render_social_reels.motion_xy",return_value=mock):
                output.append(frame(cfg,4.0,parts,bg,(200,520)).tobytes())
        self.assertEqual(output[0],output[1])
        self.assertEqual(output[0],output[2])

    def test_sound_disabled_is_silent_and_enabled_hits_only(self):
        cfg={
            "duration":8,"fit_count":5,"hold_frames":0,"seed":581,
            "move":"orbit","speed":1,"first_fit":1.1,"last_fit":7.28,
            "enable_fit_sfx":False,
        }
        with tempfile.TemporaryDirectory() as temp:
            wav=Path(temp)/"silent.wav"
            make_audio(wav,8,0,cfg)
            with wave.open(str(wav),"rb") as audio:
                samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype="<i2")
            self.assertEqual(int(np.max(np.abs(samples))),0)
            cfg["enable_fit_sfx"]=True
            make_audio(wav,8,0,cfg)
            with wave.open(str(wav),"rb") as audio:
                samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype="<i2")
                rate=audio.getframerate()
            self.assertGreater(int(np.max(np.abs(samples))),500)
            # 0.5 seconds is NOT a scheduled match; old code beeped here.
            self.assertEqual(int(np.max(np.abs(samples[:rate//2]))),0)
            self.assertEqual(validate_schedule(cfg)["exact_fit_frames_per_event"],1)


if __name__=="__main__":
    unittest.main()
