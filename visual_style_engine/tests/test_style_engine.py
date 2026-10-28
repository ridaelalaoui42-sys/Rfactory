"""Native tests for executable style rendering and deterministic content."""
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import pytest
from scripts.render_style import dimensions,node,events,ROOT


def test_output_dimensions():
    assert dimensions('vertical',540)==(540,960)
    assert dimensions('horizontal',960)==(960,540)
    assert dimensions('square',800)==(800,800)
    with pytest.raises(ValueError):dimensions('vertical',541)


def test_native_renderer_contract():
    data=json.loads(node('--probe').stdout)
    assert data['style']=='risograph_zine'
    assert len(data['beats'])==6
    assert data['length']==15
    assert len(events())>=12
    for beat in data['beats']:
        assert 0<=beat['start']<beat['end']<=data['length']


@pytest.mark.parametrize('format,width', [('vertical',360),('horizontal',640)])
def test_native_canvas_frame_is_deterministic(tmp_path,format,width):
    paths=[tmp_path/'frame1.png',tmp_path/'frame2.png']
    for p in paths:node('--format',format,'--width',width,'--single',7.7,'--poster',p)
    assert paths[0].read_bytes()==paths[1].read_bytes()
    assert len(paths[0].read_bytes())>1000


@pytest.mark.skipif(not (shutil.which('ffmpeg') and shutil.which('ffprobe')),reason='needs ffmpeg')
def test_mp4_with_audio(tmp_path):
    from argparse import Namespace
    from scripts.render_style import run
    dest=tmp_path/'output.mp4'
    result=run(Namespace(format='horizontal',width=320,fps=8,duration=1.5,output=str(dest),voiceover=None,silent=False))
    assert dest.is_file() and result['audio']
    assert result['deterministic'] and result['frames']==12
    assert (tmp_path/'output.qa.json').is_file()
