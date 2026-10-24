"""Run the Rfactory social preview renderer with editable JSON settings."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
try:
    from scripts import render_social_reels as renderer
except ImportError:
    import render_social_reels as renderer

def load_settings(path: Path) -> list[dict]:
    cfg=json.loads(path.read_text(encoding='utf-8'))
    if cfg.get('output',{}).get('fps')!=24:
        raise ValueError('Renderer currently supports 24 FPS output')
    presets=[]
    for raw in cfg['presets']:
        base=next((x for x in renderer.PRESETS if x['name']==raw['name']),None)
        if not base:raise ValueError(f"Unknown preset {raw['name']}")
        value=dict(base)
        translate={'background':'theme','subject':'primary','reaction':'badge',
                   'headline':'title','instruction':'subtitle','puzzle':'shape',
                   'motion':'move','revealAt':'reveal_at'}
        for k,v in raw.items():
            key=translate.get(k,k)
            if key=='theme':
                if not v.endswith('_vertical.webp'):
                    raise ValueError('Only pack vertical backgrounds are supported')
                v=v.removesuffix('_vertical.webp')
            if key in value:value[key]=v
        if not 4 <= value['duration'] <= 15 or not 0 < value['reveal_at'] < value['duration']:
            raise ValueError('Invalid duration or revealAt')
        if value['shape'] not in {'circle','wedge','eye_band'}:
            raise ValueError('Unknown puzzle shape')
        if value['move'] not in {'orbit','bounce','zigzag'}:
            raise ValueError('Unknown motion')
        presets.append(value)
    return presets

def main():
    p=argparse.ArgumentParser(add_help=False)
    p.add_argument('--settings',type=Path,default=Path('config/social_reels_preset_2026_10.json'))
    cfg,args=p.parse_known_args()
    renderer.PRESETS=load_settings(cfg.settings)
    sys.argv=[sys.argv[0],*args]
    renderer.main()

if __name__=='__main__':main()
