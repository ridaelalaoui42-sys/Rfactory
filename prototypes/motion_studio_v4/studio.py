"""Rfactory / Motion Studio V4 -- procedurally modeled 3D technical explainer.

Uses real VTK offscreen/EGL 3D meshes, depth, lighting and a deterministic camera;
Pillow draws editorial, layout-guarded typography in native resolution. FFmpeg
encodes video; a deterministic sound director adds scene-specific sound effects.
No upstream Three.js/Remotion runtime is claimed. This is a concrete local adapter
prototype to test our visual/QA contracts before attaching production backends.

Demo: "How your phone finds you with no mobile signal" (16.5 sec visual sample).
"""
from __future__ import annotations
import argparse, dataclasses, json, math, os, pathlib, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import vtk
from vtk.util.numpy_support import vtk_to_numpy

BASE = pathlib.Path(__file__).resolve().parent
FPS = 30
DURATION = 16.0
TAU=2*math.pi

# Styled with a restrained technical palette, not arbitrary AI-neon.
INK=(7,13,22); SLATE=(18,28,40); PAPER=(240,245,241)
CORAL=(255,137,82); ICE=(112,227,239); MINT=(183,241,202)
MUTED=(136,155,168)
# Resolve the licensed system Inter typeface in containers/Ubuntu CI without
# bundling or redistributing font files. A missing editorial font fails closed.
def _inter_font(style, local):
    if os.path.isfile(local):
        return local
    try:
        resolved = subprocess.check_output(
            ['fc-match', '-f', '%{file}', 'Inter:style=' + style],
            text=True, timeout=5).strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        resolved = ''
    if os.path.isfile(resolved) and 'inter' in resolved.lower():
        return resolved
    raise RuntimeError('Inter font is missing; install the OS fonts-inter package')

FONT_DISPLAY = _inter_font('Black', '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf')
FONT_MEDIUM = _inter_font('Medium', '/usr/share/fonts/opentype/inter/InterDisplay-Medium.otf')
FONT_MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'


def clamp(v,a=0.,b=1.):return min(b,max(a,v))
def smooth(x):x=clamp(x);return x*x*(3-2*x)
def ease_out(x):return 1-(1-clamp(x))**3
def overshoot(x):
    x=clamp(x);return 1+(2.9+1)*(x-1)**3+2.9*(x-1)**2

@dataclasses.dataclass(frozen=True)
class Cue:
    key:str
    begin:float
    end:float
    meaning:str
    title:tuple[str,...]
    label:str
    sound:str

CUES=(
 Cue('hook',0,3.7,'No cell connection need not stop GPS',('NO BARS.','STILL LOCATED.'),'SATELLITE POSITIONING','tap,signal'),
 Cue('teardown',3.7,8.2,'Phone contains a receiver, not a location transmitter',('THE RECEIVER','IS INSIDE.'),'DEVICE TEARDOWN','mechanical,click'),
 Cue('broadcast',8.2,12.3,'Navigation satellites broadcast time and positions',('TIMING','FROM SPACE.'),'SIGNALS ARRIVE','sweep,signals'),
 Cue('resolve',12.3,DURATION,'Four or more signals allow a position fix',('FOUR SIGNALS.','ONE FIX.'),'POSITION IS COMPUTED','confirmation'),
)


def actor_of(src, center=(0,0,0), col=(.4,.4,.4), metallic=.12, rough=.28, opacity=1):
    mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(src.GetOutputPort())
    actor=vtk.vtkActor();actor.SetMapper(mapper);actor.SetPosition(*center)
    p=actor.GetProperty();p.SetColor(*col);p.SetOpacity(opacity)
    p.SetInterpolationToPhong();p.SetAmbient(.16);p.SetDiffuse(.77)
    p.SetSpecular(.36+.40*metallic);p.SetSpecularPower(max(10,(1-rough)*115))
    return actor

def box(scene, dim, center, col, metallic=.1,rough=.28,opacity=1):
    s=vtk.vtkCubeSource();s.SetXLength(dim[0]);s.SetYLength(dim[1]);s.SetZLength(dim[2]);
    a=actor_of(s,center,col,metallic,rough,opacity);scene.AddActor(a);return a

def cylinder(scene, radius,height,center,col,res=60,metal=.3,opacity=1):
    s=vtk.vtkCylinderSource();s.SetRadius(radius);s.SetHeight(height);s.SetResolution(res)
    a=actor_of(s,center,col,metal,.15,opacity);scene.AddActor(a);return a

def sphere(scene,r,center,col,opacity=1):
    s=vtk.vtkSphereSource();s.SetRadius(r);s.SetThetaResolution(24);s.SetPhiResolution(18)
    a=actor_of(s,center,col,.08,.18,opacity);scene.AddActor(a);return a

def polyline(scene,points,color,r=.025,opacity=1):
    pts=vtk.vtkPoints();cells=vtk.vtkCellArray()
    for i,pt in enumerate(points):pts.InsertNextPoint(*pt)
    p=vtk.vtkPolyLine();p.GetPointIds().SetNumberOfIds(len(points))
    for i in range(len(points)):p.GetPointIds().SetId(i,i)
    cells.InsertNextCell(p)
    data=vtk.vtkPolyData();data.SetPoints(pts);data.SetLines(cells)
    tub=vtk.vtkTubeFilter();tub.SetInputData(data);tub.SetRadius(r);tub.SetNumberOfSides(9);tub.CappingOn()
    a=actor_of(tub,(0,0,0),color,.2,.2,opacity);scene.AddActor(a);return a

def ring(scene, radius, y, color, width=.016, opacity=.85, center_x=0, center_z=0, tilt=0):
    pts=[]
    for i in range(121):
        k=i*TAU/120
        z=center_z+math.sin(k)*radius
        x=center_x+math.cos(k)*radius
        pts.append((x,y+(x-center_x)*tilt,z))
    return polyline(scene,pts,color,width,opacity)

class Stage:
 def __init__(self,w,h):
    self.w=w;self.h=h
    self.renderer=vtk.vtkRenderer();self.renderer.SetBackground(.025,.045,.075)
    self.renderer.SetBackground2(.055,.08,.12);self.renderer.GradientBackgroundOn()
    self.window=vtk.vtkRenderWindow();self.window.SetOffScreenRendering(1)
    self.window.AddRenderer(self.renderer);self.window.SetSize(w,h);self.window.SetMultiSamples(0)
    self.window.SetAlphaBitPlanes(1)
    self.camera=self.renderer.GetActiveCamera();self.camera.SetViewUp(0,1,0)
    self.camera.SetViewAngle(38)
    self.camera.SetClippingRange(.1,100)
    self.lights()
    self.build()
    self.w2i=vtk.vtkWindowToImageFilter();self.w2i.SetInput(self.window);self.w2i.SetInputBufferTypeToRGB();self.w2i.ReadFrontBufferOff()

 def lights(self):
    for center,col,intensity in [((5,8,10),(1.,.86,.72),2.4),((-7,6,-2),(.38,.75,1.),1.4),((2,5,-8),(.7,1.,.91),1.0)]:
      l=vtk.vtkLight();l.SetPosition(*center);l.SetFocalPoint(0,0,0);l.SetColor(*col);l.SetIntensity(intensity)
      l.SetLightTypeToSceneLight();self.renderer.AddLight(l)

 def build(self):
    r=self.renderer
    # Object-lab plinth: radial edges, physically lit surface, engineering stage.
    cylinder(r,3.40,.16,(0,-1.20,0),(.095,.115,.14),res=100)
    cylinder(r,3.27,.05,(0,-1.10,0),(.15,.19,.21),res=100)
    self.plinth_ring=ring(r,3.12,-1.068,(.22,.7,.73),.025,.9)
    for rad in (2.70,2.1,1.45):ring(r,rad,-1.05,(.08,.24,.28),.008,.2)
    # phone chassis, board, black screen, original procedural mesh—not static imagery
    self.chassis=box(r,(2.55,.18,4.62),(0,-.73,0),(.035,.055,.074),.75)
    self.edge=box(r,(2.62,.07,4.70),(0,-.63,0),(.22,.29,.32),.77)
    self.board=box(r,(2.28,.065,4.36),(0,-.41,0),(.030,.11,.115),.28)
    self.board_outline=box(r,(2.31,.018,4.39),(0,-.367,0),(.055,.18,.17),.4)
    self.cover=box(r,(2.54,.11,4.60),(0,-.22,0),(.045,.065,.084),.75)
    self.glass=box(r,(2.42,.045,4.47),(0,-.132,0),(.035,.095,.13),.65,opacity=.90)
    # glass reflection rail as mesh edge and camera island.
    self.camera_module=box(r,(.63,.052,.68),(.75,-.08,-1.61),(.10,.16,.19),.75)
    self.lenses=[cylinder(r,.135,.065,(.54+i*.20,-.022,-1.66),(.025,.04,.055),metal=.42) for i in range(3)]
    self.chip=box(r,(.96,.15,1.02),(.0,-.285,-.4),(.045,.072,.102),.45)
    self.chipcap=box(r,(.64,.016,.67),(.0,-.197,-.4),(.24,.35,.37),.75)
    self.chipglow=box(r,(.57,.012,.60),(.0,-.178,-.4),(.11,.52,.48),.5)
    self.antenna=box(r,(1.52,.035,.24),(0,-.355,1.56),(.68,.38,.16),.65)
    # Board traces are actual 3D copper geometry; deterministic topology.
    for i in range(13):
      x=-1.01+(i%7)*.31;z=-1.95+int(i/7)*.25
      polyline(r,[(x,-.355,z),(x,-.351,z+.60),(x+.12,-.35,z+.76)],(.62,.39,.21),.013,.88)
    for i in range(13):
      x=-1.00+(i%7)*.31;z=.65+int(i/7)*.17
      polyline(r,[(x,-.353,z),(x,-.35,z+.34),(x+.15,-.351,z+.49)],(.72,.44,.22),.014,.9)
    for i in range(26):
      x=-1.03+((i*7)%11)*.193;z=-1.50+((i*9)%13)*.22
      box(r,(.095,.075,.105),(x,-.30,z),(.07,.095,.10),.25)
    # On-board receiver contact vias and RF traces.
    for i in range(12):
      z=-.86+i*.080
      polyline(r,[(.48,-.33,z),(.81,-.34,z),(.96,-.35,z+.08)],(.70,.51,.23),.01,.85)
      polyline(r,[(-.48,-.33,z),(-.78,-.34,z),(-.98,-.35,z-.06)],(.66,.48,.22),.01,.85)
    self.receiver_ring=ring(r,.65,-.15,(.10,.72,.69),.020,.5,0,-.4)
    self.pulses=[]
    for i in range(4):self.pulses.append(sphere(r,.09,(0,4,0),(.26,.91,.95),.95))
    # Satellites 3D rigid groups; four anchor locations in world space.
    self.sat_centers=[(-4.2,1.6,-2.0),(4.2,1.85,-1.2),(-4.0,1.95,2.1),(4.2,1.7,2.4)]
    self.sat_actors=[]
    for idx,c in enumerate(self.sat_centers):
      group=[]
      # cubes actual geometry; rotate group about y globally by user transform
      group.append(box(r,(.62,.40,.54),c,(.66,.67,.62),.74))
      for sign in (-1,1):
       group.append(box(r,(1.28,.055,.54),(c[0]+sign*.92,c[1],c[2]),(.10,.31,.49),.4))
       group.append(box(r,(.03,.065,.52),(c[0]+sign*.95,c[1]+.03,c[2]),(.22,.61,.73),.6))
      group.append(cylinder(r,.14,.30,(c[0],c[1]-.35,c[2]),(.58,.63,.60),40,.5))
      self.sat_actors.append(group)
    self.beams=[]
    for idx,c in enumerate(self.sat_centers):
      a=polyline(r,[c,(0,-.20,-.42)],(.13,.73,.76),.014,.0)
      self.beams.append(a)
    self.solve_rings=[ring(r,.6+i*.28,-.13,(.22,.94,.75),.018,.0,0,-.4) for i in range(4)]
    self.pin_stem=cylinder(r,.05,.8,(0,-.12,-.4),(.97,.49,.28),48,.3);self.pin_head=sphere(r,.24,(0,.4,-.4),(.99,.50,.26),0)
    # dot floor in 3D.
    for n in range(-10,11):
      q=n*.5
      polyline(r,[(q,-1.39,-5),(q,-1.39,5)],(.10,.18,.21),.005,.2)
      polyline(r,[(-5,-1.39,q),(5,-1.39,q)],(.10,.18,.21),.005,.2)

 def change(self,t):
    # One coherent object world; physically interpolated exploded assembly.
    openp=smooth((t-3.55)/2.25)
    self.cover.SetPosition(1.65*openp,-.22+openp*1.35,-.75*openp)
    self.glass.SetPosition(1.65*openp,-.132+openp*1.62,-.75*openp)
    self.camera_module.SetPosition(.75+1.65*openp,-.08+openp*1.85,-1.61-.75*openp)
    cover_visibility=1-smooth((t-7.15)/1.05)
    self.cover.GetProperty().SetOpacity(cover_visibility)
    self.glass.GetProperty().SetOpacity(.90*cover_visibility)
    self.camera_module.GetProperty().SetOpacity(cover_visibility)
    for i,lens in enumerate(self.lenses):
      lens.SetPosition(.54+i*.20+1.65*openp,-.022+openp*1.85,-1.66-.75*openp)
      lens.GetProperty().SetOpacity(cover_visibility)
    self.chip.SetPosition(0,-.285+openp*.45,-.4)
    self.chipcap.SetPosition(0,-.197+openp*.46,-.4)
    self.chipglow.SetPosition(0,-.178+openp*.47,-.4)
    self.receiver_ring.GetProperty().SetOpacity(.1+.8*openp)
    broadcast=smooth((t-8.0)/1.1)
    for idx,group in enumerate(self.sat_actors):
      visible=clamp((t-(8.25+idx*.31))/.55)
      # Actor offsets anchored in local coordinates with z movement reveal.
      orig=self.sat_centers[idx]
      for a in group:a.GetProperty().SetOpacity(visible*.97)
      self.beams[idx].GetProperty().SetOpacity(.7*visible*(.68+.32*math.sin(t*5+idx)))
      phase=(t-8.25-idx*.37)*.49
      frac=(phase%1.0)
      sx,sy,sz=orig
      forstep=(0,-.25,-.4)
      self.pulses[idx].SetPosition((1-frac)*sx+frac*forstep[0],(1-frac)*sy+frac*forstep[1],(1-frac)*sz+frac*forstep[2])
      self.pulses[idx].GetProperty().SetOpacity(visible*(.7+.25*math.sin(t*10+idx)))
    solve=smooth((t-12.1)/1.1)
    for idx,ra in enumerate(self.solve_rings):
      ra.GetProperty().SetOpacity(clamp(solve-idx*.17)*.8)
    self.pin_head.GetProperty().SetOpacity(solve)
    self.pin_stem.GetProperty().SetOpacity(solve)
    self.pin_stem.SetPosition(0,-.12+solve*.54,-.4)
    self.pin_head.SetPosition(0,.4+solve*.65,-.4)
    # Camera move has a reason: wide product -> macro internals -> capture space -> solve.
    if t<4:
      p=smooth(t/4);pos=(7.1-1.0*p,6.4-.45*p,10.1-1.1*p);look=(0,-.20,0)
    elif t<8:
      p=smooth((t-4)/4);pos=(6.1-1.8*p,5.95-.9*p,9-2.2*p);look=(0,.05,-.2)
    elif t<12.1:
      p=smooth((t-8)/4.1);pos=(5.25+1.4*p,6.05+1.35*p,8.7+2.2*p);look=(0,.55,0)
    else:
      p=smooth((t-12.1)/3.9);pos=(6.2+.6*p,6.9+.4*p,10.1+1.2*p);look=(0,.35,0)
    self.camera.SetPosition(*pos);self.camera.SetFocalPoint(*look);self.camera.SetViewUp(0,1,0)

 def frame(self,t):
    self.change(t)
    self.window.Render()
    self.w2i.Modified();self.w2i.Update()
    img=self.w2i.GetOutput();w,h,_=img.GetDimensions()
    arr=vtk_to_numpy(img.GetPointData().GetScalars()).reshape((h,w,3))
    return np.ascontiguousarray(np.flipud(arr))

 @staticmethod
 def reference_2d(stage,pt):
    stage.renderer.SetWorldPoint(*pt,1)
    stage.renderer.WorldToDisplay(); x,y,_=stage.renderer.GetDisplayPoint()
    return x,stage.h-y


@dataclasses.dataclass
class LabelBox:
 text:str;box:tuple[int,int,int,int];begin:float;end:float;purpose:str

class TextGuard:
 """Check drawn text rectangles (not merely layout containers) at each sampled frame.

 Some intentional parent/child relationships, such as a word inside its own
 underlining box, are backgrounds and do not count as glyph collisions.
 """
 def __init__(self,w,h):
  self.w=w;self.h=h;self.records=[];self.violations=[]
 def label(self,label):
  x0,y0,x1,y1=label.box
  # platform safe zones: 55px at 1080 logical design; safe top 120,bottom 185
  mx=self.w*.065;top=self.h*.085;bottom=self.h*.9
  if x0<mx or x1>self.w-mx or y0<top or y1>bottom:
    self.violations.append({'type':'unsafe','text':label.text,'time':label.begin,'box':label.box})
  for other in self.records:
    if abs(other.begin-label.begin)<.001 and other.end>=label.begin and label.end>=other.begin:
      ax0,ay0,ax1,ay1=other.box
      ix=max(0,min(ax1,x1)-max(ax0,x0));iy=max(0,min(ay1,y1)-max(ay0,y0))
      if ix*iy>80:
       self.violations.append({'type':'overlap','a':other.text,'b':label.text,'time':label.begin,'overlap_px':ix*iy})
  self.records.append(label)
 def snapshot(self):
  return {'labels':len(self.records),'violations':self.violations[:40]}

class Graphics:
 def __init__(self,w,h):
    self.w=w;self.h=h;self.k=w/1080
    self.font_cache={};self.guard=TextGuard(w,h)
 def font(self,size,display=True):
    key=(int(size*self.k),display)
    if key not in self.font_cache:self.font_cache[key]=ImageFont.truetype(FONT_DISPLAY if display else FONT_MEDIUM,max(10,key[0]))
    return self.font_cache[key]
 def draw(self,arr,t,stage=None):
    base=Image.fromarray(arr).convert('RGBA');o=Image.new('RGBA',(self.w,self.h),(0,0,0,0));d=ImageDraw.Draw(o)
    W,H=self.w,self.h;k=self.k
    # brand header as integral design object. Not repeated subtitles.
    d.rounded_rectangle((int(76*k),int(138*k),int(320*k),int(199*k)),radius=int(16*k),fill=(11,28,37,222),outline=(*ICE,75),width=max(1,int(2*k)))
    d.text((int(99*k),int(146*k)),'CTRL / PULSE',font=self.font(30,False),fill=PAPER)
    d.line((int(82*k),int(210*k),int(990*k),int(210*k)),fill=(*MUTED,94),width=max(1,int(2*k)))
    key=next((c for c in CUES if c.begin<=t<c.end),CUES[-1]);q=clamp((t-key.begin)/.65)
    # Rich title choreography: stagger, vertical mask, contrast change, accent sweep.
    lines=key.title
    for li,txt in enumerate(lines):
      shift=.14*li
      pr=ease_out((t-key.begin-shift)/.62)
      if pr<.01:continue
      y=int((288+li*112)*k); x=int((84+34*(1-pr))*k)
      color=PAPER if li==0 else (ICE if key.key in ('hook','broadcast') else CORAL)
      f=self.font(78 if len(txt)>15 else 90,True)
      bbox=d.textbbox((x,y),txt,font=f,stroke_width=0)
      # no text-box collisions; single-line titles checked.
      self.guard.label(LabelBox(txt,bbox,t,t,'headline'))
      # textured reveal mask: clip layer to progress and a small y-overshoot
      layer=Image.new('RGBA',(self.w,self.h));ld=ImageDraw.Draw(layer)
      ld.text((x,y+int((1-pr)*32*k)),txt,font=f,fill=(*color,int(255*pr)))
      lo=int((y+8*k));hi=max(lo+1,int(y+f.size*1.25))
      mask=Image.new('L',(self.w,self.h));md=ImageDraw.Draw(mask)
      md.rectangle((x,lo,int(x+max(0,bbox[2]-x)*pr),hi),fill=255)
      layer.putalpha(Image.fromarray(np.minimum(np.asarray(layer.getchannel('A')),np.asarray(mask)).astype('uint8'),'L'))
      o.alpha_composite(layer)
      if li==1 and pr>.10:
       u=int((x+2*k)); ww=int(min((bbox[2]-x)*pr,630*k))
       d.rounded_rectangle((u,int((y+103*k)),u+ww,int((y+110*k))),radius=max(1,int(3*k)),fill=(*CORAL,218))
    # explanatory capsule in its own reserved region bottom-left; read on phone.
    rel=smooth((t-key.begin-.55)/.45)
    if rel>.01:
      b_x=int(78*k);b_y=int(1574*k)
      label=key.label
      font=self.font(37,False)
      tw=int(d.textlength(label,font=font));ww=min(int(900*k),tw+int(54*k))
      yy=int((1-rel)*35*k)
      d.rounded_rectangle((b_x,b_y+yy,b_x+ww,b_y+int(91*k)+yy),radius=int(18*k),fill=(10,28,35,int(rel*225)),outline=(*ICE,int(80*rel)),width=max(1,int(2*k)))
      bbox=d.textbbox((b_x+int(22*k),b_y+int(23*k)+yy),label,font=font)
      self.guard.label(LabelBox(label,bbox,t,t,'callout'))
      d.text((b_x+int(22*k),b_y+int(23*k)+yy),label,font=font,fill=(*PAPER,int(rel*255)))
      # Tether follows the real 3D receiver, unlike a decorative HUD card.
      if stage is not None and t>=3.7:
       px,py=stage.reference_2d(stage,(0,-.10+smooth((t-3.55)/2.25)*.4,-.40))
       px=int(clamp(px,180*k,940*k));py=int(clamp(py,710*k,1460*k))
       sx=b_x+int(ww*.56);sy=b_y+yy
       a=int(125*rel)
       d.line((sx,sy,px,py),fill=(*ICE,a),width=max(1,int(2*k)))
       rr=int(9*k)
       d.ellipse((px-rr,py-rr,px+rr,py+rr),outline=(*ICE,int(220*rel)),width=max(1,int(3*k)))
    # precise 4-link progress graphic: actual signals represented by nodes, not random particles
    if t>=8.25 and t<15.95:
      p=clamp((t-8.25)/4.6)
      center=(int(545*k),int(1470*k))
      for i in range(4):
       cx=int((390+i*100)*k);cy=int((1460+(i%2)*32)*k)
       visible=clamp((p-i*.19)*4)
       if visible>.01:
        color=(*ICE,int(visible*200))
        d.line((cx,cy,center[0],center[1]),fill=(*ICE,int(visible*140)),width=max(1,int(3*k)))
        d.ellipse((cx-int(13*k),cy-int(13*k),cx+int(13*k),cy+int(13*k)),fill=color,outline=(*PAPER,int(visible*210)),width=max(1,int(2*k)))
    # tiny footer line, bar fills along time, not held static.
    x0=int(80*k);x1=int(990*k);y=int(1770*k)
    d.line((x0,y,x1,y),fill=(*MUTED,110),width=max(2,int(3*k)))
    d.line((x0,y,x0+int((x1-x0)*clamp(t/DURATION)),y),fill=(*CORAL,245),width=max(3,int(6*k)))
    d.text((x0,int(1790*k)),f'MOTION LAB / GPS RECEIVER   •   {int(t):02d}s',font=self.font(22,False),fill=(*MUTED,220))
    # color grade via dark transparent gradient where title sits, which preserves readability.
    tint=Image.new('RGBA',(self.w,self.h),(0,0,0,0));td=ImageDraw.Draw(tint)
    for j in range(0,int(890*k),max(2,int(4*k))):
      a=255 if j<=545*k else int(255*max(0,1-(j-545*k)/(345*k))**2)
      td.rectangle((0,j,self.w,j+max(2,int(4*k))),fill=(2,7,14,a))
    base.alpha_composite(tint);base.alpha_composite(o)
    return np.asarray(base.convert('RGB'))


def synth_sounds(path,dur=DURATION,sr=48000):
    N=int(sr*dur);audio=np.zeros((N,2),dtype='float64');rng=np.random.default_rng(4029)
    def add(signal,when,gain=1,pan=0):
      start=int(when*sr);n=min(len(signal),N-start)
      if n<=0:return
      sig=signal[:n]*gain
      audio[start:start+n,0]+=sig*(1-pan)*.5
      audio[start:start+n,1]+=sig*(1+pan)*.5
    def tone(freq,sec,atk=.025,rel=.16,phase=0):
      n=int(sec*sr);tt=np.arange(n)/sr
      env=np.minimum(1,np.arange(n)/max(1,atk*sr))*np.minimum(1,np.arange(n)[::-1]/max(1,rel*sr))
      return np.sin(2*math.pi*freq*tt+phase)*env
    # continuous subtle low harmonic underscore—multiple evolving tones rather than one sine.
    tt=np.arange(N)/sr
    amb=.011*(np.sin(TAU*54*tt)+.55*np.sin(TAU*81*tt)+.35*np.sin(TAU*108*tt))
    amb*=np.minimum(1,tt/.85)*np.minimum(1,(dur-tt)/1.1)
    audio+=amb[:,None]
    # designed events support visible mechanical actions; avoid cheesy constant whooshes.
    events=[(.15,'thump'),(1.3,'tap'),(3.68,'servo'),(4.45,'servo'),(5.35,'click'),(7.6,'tap'),(8.45,'signal'),(9.2,'signal'),(9.95,'signal'),(10.7,'signal'),(12.3,'hit'),(13.0,'resolve'),(14.7,'tap')]
    for idx,(when,typ) in enumerate(events):
      if typ=='tap':
        s=tone(790,.23,.006,.18)*np.exp(-np.arange(int(.23*sr))/(.11*sr));add(s,when,.13,pan=(-.4 if idx%2 else .3))
      elif typ=='signal':
        n=int(.45*sr);tt0=np.arange(n)/sr
        freq=560+200*tt0/.45
        ph=TAU*(560*tt0+200*tt0*tt0/(2*.45))
        s=np.sin(ph)*np.exp(-tt0*7.5)
        add(s,when,.10,pan=(-.6+(idx%4)*.4))
      elif typ=='click':
        tt0=np.arange(int(.19*sr))/sr
        s=rng.standard_normal(len(tt0))*np.exp(-tt0*25)
        s=(s+np.sin(TAU*160*tt0)*.3)*.08
        add(s,when,.55,.35)
      elif typ=='servo':
        tt0=np.arange(int(.83*sr))/sr
        nse=rng.standard_normal(len(tt0))
        c=np.cumsum(nse)*.008
        # motor sweep with texture and bass undertone, locates chassis lift
        s=(np.sin(TAU*(92*tt0+175*tt0**2))+c*.22)*np.minimum(1,tt0/.15)*np.minimum(1,(.83-tt0)/.25)
        add(s,when,.05,-.2)
      elif typ=='thump':
        tt0=np.arange(int(.5*sr))/sr
        s=np.sin(TAU*(72*tt0-38*tt0*tt0)) * np.exp(-tt0*13)
        add(s,when,.29,0)
      elif typ=='hit':
        tt0=np.arange(int(.85*sr))/sr
        s=(np.sin(TAU*94*tt0)+.2*rng.standard_normal(len(tt0)))*np.exp(-tt0*8)
        add(s,when,.14,0)
      elif typ=='resolve':
        # close with tonal success, a brief spaced triad.
        for j,(freq,delay) in enumerate([(261.6,0),(329.6,.14),(392,.28)]):
         add(tone(freq,1.8,.18,.60),when+delay,.050,pan=(j-1)*.22)
    maxval=float(np.max(np.abs(audio)));audio*=min(.56/maxval,4.0) if maxval>0 else 1
    a=(audio*32767).astype('<i2')
    with wave.open(str(path),'wb') as w:
      w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes(a.tobytes())
    return {'duration':dur,'sample_rate':sr,'channels':2,'events':len(events),'peak':float(np.max(np.abs(audio))),'path':str(path)}


def encode(out,frames_iter,w,h,fps):
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','pipe:0','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
      for idx,im in enumerate(frames_iter):
       p.stdin.write(im.tobytes())
       if idx%90==0:print('rendered',idx,'frames',flush=True)
      p.stdin.close();p.wait()
    except Exception:
      p.kill();raise
    if p.returncode!=0:raise RuntimeError(p.stderr.read().decode()[-1200:])


def render(width,height,fps,duration,folder,preview=False):
    folder.mkdir(parents=True,exist_ok=True)
    stage=Stage(width,height);gfx=Graphics(width,height)
    N=int(duration*fps)
    screenshots=[.6,2.3,4.9,6.9,8.6,10.2,12.7,14.4,15.7]
    screen_dir=folder/'frames';screen_dir.mkdir(exist_ok=True)
    sampled=[]
    def frames():
      for i in range(N):
       t=i/fps
       rgb=stage.frame(t)
       frame=gfx.draw(rgb,t,stage)
       if screenshots and min(abs(t-s) for s in screenshots)<.5/fps:
        target=screen_dir/f'frame_{t:05.2f}.jpg';Image.fromarray(frame).save(target,quality=87);sampled.append(str(target))
       yield frame
    silent=folder/'gps_3d_silent.mp4'
    encode(silent,frames(),width,height,fps)
    sound=folder/'studio_sfx.wav';sound_meta=synth_sounds(sound, duration)
    result=folder/'CTRL_PULSE_GPS_3D_MOTION_STUDIO_V4.mp4'
    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(sound),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(result)]
    subprocess.run(command,check=True)
    return {'title':'GPS inside a phone | physical 3D demonstrator','fps':fps,'dimensions':[width,height],'duration':duration,'file':str(result),'sound':sound_meta,'screenshots':sampled,'text_guard':gfx.guard.snapshot(),'status':'LAB_SAMPLE_NOT_PUBLISHED','provenance':'Original procedural VTK geometry, Inter typography, deterministic SFX; no unlicensed reference-video frames used','narration':'not included in engine sample; require quality TTS for publication'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--width',type=int,default=1080);ap.add_argument('--height',type=int,default=1920);ap.add_argument('--fps',type=int,default=30);ap.add_argument('--seconds',type=float,default=DURATION);ap.add_argument('--output-dir',type=pathlib.Path,default=BASE/'output');args=ap.parse_args()
    meta=render(args.width,args.height,args.fps,args.seconds,args.output_dir)
    (args.output_dir/'manifest.json').write_text(json.dumps(meta,indent=2))
    print('RENDER_RESULT',json.dumps(meta,default=str)[:1700]);
if __name__=='__main__':main()