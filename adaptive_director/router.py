"""Topic-aware animation selection. Verifiable, deterministic and overrideable.

NOTE: Engines are ORIGINAL adapters inspired by the linked open-source skills;
not packaged copies of those full upstream tools or external paid APIs.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import re

STYLE_MAP = {
  'bang': {'title':'Bang Motion', 'best_for':['product_launch','software_demo','ai_tools'], 'grammar':'camera-rig UI, tracked cursor, connected transitions', 'skill':'https://github.com/bangtutorial/bang-motion'},
  'vox': {'title':'Vox Explainer', 'best_for':['news','investigation','economics','geopolitics'], 'grammar':'evidence desk, annotated sources, time/geo/data diagrams', 'skill':'https://github.com/CK42BB/vox-explainer-skill'},
  'huashu': {'title':'Huashu Art Motion', 'best_for':['science','history','culture','nature'], 'grammar':'moving illustrated worlds, rule-based motifs', 'skill':'https://github.com/alchaincyf/huashu-art-motion'},
  'drawing': {'title':'Claude Drawing', 'best_for':['engineering','tutorial','math','how_it_works'], 'grammar':'procedural pen traces, diagram unfolding', 'skill':'https://github.com/cloveric/claude-drawing-skill'},
  'stickman': {'title':'Stickman Director', 'best_for':['story','humor','tutorial','psychology','characters'], 'grammar':'pose/action graph, acting anticipation and squash/recoil', 'skill':'https://github.com/kaomei/stickman-video-director'},
}
RULES = {
 'bang': {'launch':5, 'product':5, 'app':4, 'demo':4, 'software':4, 'ui':4, 'interface':3, 'ai tools':5, 'startup':3, 'device':3},
 'vox': {'news':5, 'investigation':6, 'scandal':6, 'geopolitics':6, 'economics':5, 'research':4, 'report':5, 'data':4, 'evidence':5, 'timeline':4, 'company':3},
 'huashu': {'science':6, 'history':6, 'art':6, 'space':5, 'earth':5, 'physics':5, 'nature':5, 'biology':4, 'education':2},
 'drawing': {'tutorial':4, 'how':4, 'algorithm':6, 'circuit':6, 'engineering':6, 'mathematics':6, 'explain':2, 'code':4, 'architecture':5, 'diagram':6},
 'stickman': {'story':4, 'funny':6, 'humor':6, 'psychology':5, 'mistake':5, 'person':4, 'characters':5, 'habit':5, 'workflow':3, 'tutorial':2},
}
STYLE_ORDER = ['bang','vox','huashu','drawing','stickman']

class RenderGateError(ValueError): pass

@dataclass(frozen=True)
class Shot:
    start: float
    end: float
    module: str
    focus: str
    source_ids: tuple = ()
    motion: str = 'subject-action'

    def validate(self):
        if self.module not in STYLE_MAP: raise RenderGateError('Unknown engine: '+self.module)
        if self.end <= self.start:raise RenderGateError('Shot must have positive duration')


def score_topic(topic:str):
    t=topic.lower()
    tokens=set(re.findall(r'[\w]+',t))
    scores={k:0 for k in STYLE_MAP}
    for module, kws in RULES.items():
        for word, value in kws.items():
            if (word in t if ' ' in word else word in tokens): scores[module]+=value
    return scores

def choose_style(topic:str, override:Optional[str]=None, exclusions=()):
    if override:
        if override not in STYLE_MAP: raise RenderGateError(f'Unsupported engine {override}. Choices: {list(STYLE_MAP)}')
        return {'module':override, 'reason':'explicit editor override', 'scores':score_topic(topic)}
    scores=score_topic(topic)
    safe=[m for m in STYLE_ORDER if m not in exclusions]
    if not safe:raise RenderGateError('No remaining motion modules')
    winner=max(safe,key=lambda m:(scores[m],-STYLE_ORDER.index(m)))
    return {'module':winner,'reason':f'topic score {scores[winner]}, matched semantic cues','scores':scores}

def validate_brand(br):
    if br.get('width',1080)<1080 or br.get('height',1920)<1920:
        raise RenderGateError('All renders must be native 1080 x 1920 or larger')
    if br.get('subtitles',False):raise RenderGateError('CTRL PULSE prohibits on-video captions/subtitles')
    if br.get('language','en').lower()!='en':raise RenderGateError('English narration required')

def plan(topic, beats, override=None, brand=None):
    brand=brand or {}
    validate_brand(brand)
    out=[]
    last_end=0
    for i,b in enumerate(beats):
        module=choose_style(b.get('topic',topic),b.get('module',override))['module']
        shot=Shot(float(b['start']),float(b['end']),module,b.get('focus',''),tuple(b.get('source_ids',())),b.get('motion','subject-action'))
        shot.validate()
        if i>0 and abs(shot.start-last_end)>.03:raise RenderGateError('Timeline gaps/overlaps unsupported')
        last_end=shot.end
        out.append(shot)
    return {'topic':topic,'brand':{'width':brand.get('width',1080),'height':brand.get('height',1920),'subtitles':False,'language':'en'},'shots':[asdict(s) for s in out], 'total_seconds':last_end}