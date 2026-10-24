"""Render from editable social_reels_preset_2026_10.json settings."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
try:
    from scripts import render_social_reels as renderer
    from scripts.social_motion import validate_schedule
except ImportError:
    import render_social_reels as renderer
    from social_motion import validate_schedule

MAPPING = {'background':'theme','subject':'primary','reaction':'badge',
           'headline':'title','instruction':'subtitle','puzzle':'shape',
           'motion':'move','fitCount':'fit_count',
           'firstFit':'first_fit','lastFit':'last_fit','holdFrames':'hold_frames'}

def load_settings(path: Path) -> list[dict]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('output',{}).get('fps') != 24:
        raise ValueError('Renderer requires 24 FPS')
    presets=[]
    for raw in data['presets']:
        original=next((x for x in renderer.PRESETS if x['name']==raw['name']),None)
        if not original:raise ValueError(f'Unsupported preset: {raw["name"]}')
        cfg=dict(original)
        for key,value in raw.items():
            k=MAPPING.get(key,key)
            if k=='theme':
                if not value.endswith('_vertical.webp'):
                    raise ValueError('Expected a vertical background WebP filename')
                value=value.removesuffix('_vertical.webp')
            if k in cfg or k in ('fit_count','hold_frames','first_fit','last_fit','seed','enable_fit_sfx'):
                cfg[k]=value
        if not 5<=cfg['duration']<=15:
            raise ValueError('Invalid video duration')
        if cfg['shape'] not in {'circle','wedge','eye_band'} or cfg['move'] not in {'orbit','bounce','zigzag'}:
            raise ValueError('Unsupported shape or movement')
        validate_schedule(cfg,renderer.FPS)
        presets.append(cfg)
    return presets

def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--settings',type=Path,default=Path('config/social_reels_preset_2026_10.json'))
    known,rest=parser.parse_known_args()
    renderer.PRESETS=load_settings(known.settings)
    sys.argv=[sys.argv[0],*rest]
    renderer.main()

if __name__=='__main__':main()