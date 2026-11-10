"""Five independent motion grammars plus a compositional director.
Every pixel is rasterized at native 1080x1920 from time t; no slide fade loop.
"""
from PIL import Image,ImageDraw,ImageFont
import math,random
from .router import STYLE_ORDER
W,H=1080,1920
INK='#152723'; DARK='#0B211D'; PAPER='#F2EEDD'; ORANGE='#F36642'; CITRON='#D8EE6D'; SAGE='#A9B4A8'; BLUE='#4D67F4'; ROSE='#F58B94'; MID='#285147'
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def font(sz,bold=False):return ImageFont.truetype(BOLD if bold else FONT,sz)
def ease(t):t=max(0,min(1,t));return t*t*(3-2*t)
def clamp(x,lo=0,hi=1):return max(lo,min(hi,x))
def lerp(a,b,t):return a+(b-a)*t
def txt(d,x,y,s,size,color=PAPER,bold=False,anchor=None):
    d.text((int(x),int(y)),s,font=font(size,bold),fill=color,anchor=anchor,stroke_width=0)
def rr(d,xy,fill,r=28,outline=None,w=2): d.rounded_rectangle(tuple(map(int,xy)),radius=r,fill=fill,outline=outline,width=w)
def line(d,xy,fill,w=5):d.line([(int(a),int(b)) for a,b in xy],fill=fill,width=w,joint='curve')
def circles(d,cx,cy,r,col):d.ellipse((int(cx-r),int(cy-r),int(cx+r),int(cy+r)),fill=col)
def brand(d,section):
    rr(d,(52,65,250,115),PAPER,13)
    txt(d,70,75,'CTRL PULSE',23,INK,True)
    rr(d,(800,66,1024,116),ORANGE,13)
    txt(d,826,76,section.upper(),21,PAPER,True)
def bg(color=INK):return Image.new('RGB',(W,H),color)
def cpath(d,pts,at,col,width=9):
    if at<=0:return
    if at>=1:line(d,pts,col,width);return
    lengths=[];total=0
    for a,b in zip(pts[:-1],pts[1:]):
        k=math.hypot(a[0]-b[0],a[1]-b[1]);lengths.append(k);total+=k
    target=total*at;drawn=[]
    for i,dist in enumerate(lengths):
        a,b=pts[i],pts[i+1]
        if not drawn:drawn=[a]
        if target>=dist:drawn.append(b);target-=dist
        else:
            drawn.append((lerp(a[0],b[0],target/dist),lerp(a[1],b[1],target/dist)));break
    if len(drawn)>1:line(d,drawn,col,width)

def intro(im, t):
    d=ImageDraw.Draw(im); brand(d,'ADAPTIVE / V4')
    p=ease(t/2.5)
    txt(d,68,325,'ONE STORY.',92,PAPER,True)
    txt(d,68,439,'FIVE MOTION',75,CITRON,True)
    txt(d,68,545,'ENGINES.',90,ORANGE,True)
    cx,cy=540,1080
    for idx,a in enumerate([i*2*math.pi/5 for i in range(5)]):
        ang=a+t*0.55
        x=cx+300*math.cos(ang);y=cy+290*math.sin(ang)
        col=[ORANGE,CITRON,BLUE,ROSE,SAGE][idx]
        line(d,[(cx,cy),(x,y)],MID,8)
        circles(d,x,y,55 if idx!=0 else 72,col)
        rr(d,(x-18,y-12,x+18,y+12),INK,7)
    circles(d,cx,cy,100,ORANGE);circles(d,cx,cy,64,INK);txt(d,cx,cy,'V4',52,PAPER,True,'mm')
    for i in range(7):
        a=i*1.12+t*1.4;r=420+18*math.sin(t+i)
        circles(d,cx+math.cos(a)*r,cy+math.sin(a)*r,5,CITRON)
    txt(d,75,1645,'Topic-aware animation',42,PAPER)
    txt(d,75,1725,'Scene graph  /  Motion grammar',29,SAGE)

def bang(im,t):
    d=ImageDraw.Draw(im);brand(d,'BANG / PRODUCT')
    txt(d,72,260,'SOFTWARE',95,PAPER,True)
    txt(d,72,367,'SHOULD MOVE.',77,CITRON,True)
    # persistent product UI, connected camera panel rather than slides
    sway=20*math.sin(t*.7)
    ox,oy=90+sway,620
    rr(d,(ox,oy,980+sway,1370),PAPER,38)
    rr(d,(ox+18,oy+18,962+sway,1370-18),DARK,32)
    rr(d,(ox+45,oy+55,933+sway,oy+120),INK,16)
    for i,c in enumerate([ORANGE,CITRON,ROSE]):circles(d,ox+83+i*46,oy+88,14,c)
    txt(d,ox+250,oy+65,'Live product canvas',34,PAPER,True)
    # animated tools menu
    for i,n in enumerate(['CAPTURE','EDIT','EXPORT']):
        yy=oy+176+i*146
        rr(d,(ox+47,yy,ox+285,yy+109),MID if i!=int(t*1.3)%3 else ORANGE,22)
        txt(d,ox+70,yy+35,n,24,PAPER,True)
    rr(d,(ox+315,oy+166,ox+844,oy+608),INK,24)
    for i in range(6):
        xx=ox+340+i*87
        top=oy+585-(0.30+0.60*abs(math.sin(t*.65+i*.58)))*330
        rr(d,(xx,top,xx+53,oy+585),CITRON if i%2 else ORANGE,14)
    # cursor follows an actual Bezier path and click ring
    q=(t%3.5)/3.5
    x=lerp(ox+105,ox+700,ease(q));y=lerp(oy+240,oy+520,ease(q)) -90*math.sin(math.pi*q)
    d.polygon([(x,y),(x+10,y+64),(x+24,y+42),(x+55,y+44)],fill=PAPER)
    if abs(q-.5)<.1:d.ellipse((x-35,y-35,x+35,y+35),outline=ORANGE,width=7)
    txt(d,85,1505,'Motion: camera follows interaction',35,PAPER)
    cpath(d,[(86,1590),(350,1590),(560,1615),(865,1555),(980,1555)],ease(t/2.8),ORANGE,12)

def vox(im,t):
    d=ImageDraw.Draw(im);brand(d,'VOX / EVIDENCE')
    txt(d,70,245,'FOLLOW',98,INK,True)
    txt(d,70,350,'THE EVIDENCE.',75,ORANGE,True)
    # paper-collage: no synthetic 'news screenshot' posing as real: actual upstream project titles
    src=[('SOURCE / 01','bangtutorial/bang-motion'),('SOURCE / 02','huashu-art-motion'),('SOURCE / 03','claude-drawing-skill')]
    for i,(k,n) in enumerate(src):
        x=90+i*35+24*math.sin(t*.6+i); y=640+i*260-18*math.sin(t*.9+i)
        rr(d,(x,y,x+820,y+215),PAPER,8,INK,3)
        rr(d,(x+20,y+20,x+235,y+62),ORANGE,4)
        txt(d,x+38,y+29,k,20,PAPER,True)
        txt(d,x+40,y+98,n,30,INK,True)
        # metadata elements look like clippings, not fake article text
        for j in range(4):rr(d,(x+40,y+160+j*3,x+290+j*65,y+163+j*3),SAGE,2)
        d.polygon([(x+790,y+175),(x+820,y+175),(x+820,y+205)],fill=SAGE)
    # active investigation connections and measurement focus
    p=ease((t-.15)/2.6)
    cpath(d,[(183,660),(88,1120),(535,1390),(922,1180)],p,ORANGE,10)
    for a,b in [(183,660),(88,1120),(535,1390),(922,1180)]:circles(d,a,b,11,BLUE)
    rr(d,(135,1510,975,1690),INK,26)
    txt(d,170,1555,'AUTHENTIC SOURCES',52,PAPER,True)
    txt(d,170,1631,'Verified titles  •  no fabricated clippings',22,CITRON)

def huashu(im,t):
    d=ImageDraw.Draw(im);brand(d,'HUASHU / SCIENCE')
    txt(d,70,260,'ILLUSTRATIONS',75,PAPER,True)
    txt(d,70,355,'COME ALIVE.',89,CITRON,True)
    # vivid living paper landscape, layered motion *within* art instead of image zoom
    d.ellipse((-130,750,1230,2200),fill='#31584C')
    for i,col in enumerate(['#3F7962','#5E8C70','#8EAF77','#B7C891']):
        yy=1080+i*200+16*math.sin(t*.9+i)
        pts=[(0,yy+60*math.sin((x/160)+t*.5+i)) for x in range(-10,1101,35)]
        d.polygon(pts+[(1080,1920),(0,1920)],fill=col)
    # wind lines: each independent oscillating, purposeful
    for i in range(6):
        y=850+i*103
        x0=-260+((t*230+i*145)%1540)
        cpath(d,[(x0,y),(x0+90,y-20),(x0+210,y+15),(x0+310,y-18)],1,PAPER,4)
    # sun rises and moves
    cx=820+30*math.sin(t*.5);cy=730+52*math.sin(t*.4)
    circles(d,cx,cy,117,ORANGE)
    # seed grows visibly into branching tree in foreground
    base=(230,1640)
    grow=ease(t/2.7)
    cpath(d,[base,(245,1520),(230,1400),(278,1275),(270,1180)],grow,INK,16)
    for i,side in enumerate([-1,1,-1,1]):
        phase=clamp((grow-.20-i*.13)*3)
        x=245+i*5;y=1480-i*90
        cpath(d,[(x,y),(x+side*105,y-75),(x+side*175,y-110)],phase,INK,11)
        if phase>.75:circles(d,x+side*175,y-110,26,CITRON)
    txt(d,75,1760,'A world with living objects',34,INK,True)

def drawing(im,t):
    d=ImageDraw.Draw(im);brand(d,'DRAWING / TECH')
    txt(d,76,262,'WATCH THE',90,PAPER,True)
    txt(d,76,370,'IDEA APPEAR.',81,CITRON,True)
    # paper notebook and progressive geometric drafting
    rr(d,(65,610,1015,1620),PAPER,24)
    for y in range(675,1570,52):line(d,[(115,y),(970,y)],'#D5D5C8',2)
    for x in range(120,980,52):line(d,[(x,655),(x,1580)],'#DADDD1',2)
    txt(d,130,693,'ENGINEERING SKETCH  /  SCHEMATIC',27,INK,True)
    p=ease(t/3.1)
    pts=[(205,1050),(375,1050),(375,875),(590,875),(590,1110),(780,1110),(780,945),(910,945)]
    cpath(d,pts,p,INK,17)
    for j,(x,y) in enumerate([(205,1050),(375,875),(590,1110),(780,945)]):
        if p>j*.23:circles(d,x,y,27,ORANGE);circles(d,x,y,13,PAPER)
    if p>.4:
        rr(d,(420,1210,720,1355),CITRON,14)
        txt(d,468,1255,'CONTROL',40,INK,True)
    # pencil tip moves along current path and lifts on last frame
    if p<1:
        idx=min(len(pts)-2,int(p*(len(pts)-1)))
        frac=p*(len(pts)-1)-idx
        x=lerp(pts[idx][0],pts[idx+1][0],frac);y=lerp(pts[idx][1],pts[idx+1][1],frac)
        d.polygon([(x+10,y+4),(x+100,y-83),(x+123,y-58),(x+35,y+29)],fill=ORANGE)
    txt(d,130,1485,'Deterministic paths',29,INK,True)

def stickman(im,t):
    d=ImageDraw.Draw(im);brand(d,'STICKMAN / STORY')
    txt(d,70,260,'CHARACTERS',85,INK,True)
    txt(d,70,367,'DO THE WORK.',82,ORANGE,True)
    # desk and control button with reactions in real choreography
    rr(d,(120,1260,990,1360),INK,25)
    rr(d,(740,1190,932,1260),ORANGE,20)
    txt(d,768,1206,'CLICK',27,PAPER,True)
    q=ease(clamp((t-.25)/1.9));bounce=24*math.sin(q*math.pi*2)
    x,y=430,1030-bounce
    circles(d,x,y-190,118,INK)
    # expressive eyes swap according to reach state
    for off in [-42,42]:
        circles(d,x+off,y-202,13,PAPER)
        if q>.55:circles(d,x+off+6,y-202,5,CITRON)
    d.arc((x-30,y-155,x+30,y-124),0,180,fill=PAPER,width=6)
    line(d,[(x,y-67),(x,y+168)],INK,23)
    line(d,[(x,y+168),(x-115,y+300)],INK,20)
    line(d,[(x,y+168),(x+120,y+300)],INK,20)
    # two independent limbs; one reaching button with anticipation
    line(d,[(x,y-25),(x-140,y+20),(x-175,y+125)],INK,20)
    hand_x=lerp(x+130,850,q);hand_y=lerp(y+80,1190,q)
    line(d,[(x,y-25),(x+125,y+30),(hand_x,hand_y)],INK,20)
    circles(d,hand_x,hand_y,26,ORANGE)
    if q>.82:
        for i in range(5):
            a=i*math.pi/2.5; xx=850+110*math.cos(a+t*3);yy=1200+100*math.sin(a+t*3)
            circles(d,xx,yy,9,CITRON)
        rr(d,(200,1450,865,1640),CITRON,25)
        txt(d,250,1500,'ACTION > SLIDES',46,INK,True)
        txt(d,253,1577,'anticipation • contact • recoil',23,INK)

def router_montage(im,t):
    d=ImageDraw.Draw(im);brand(d,'SMART ROUTER')
    txt(d,70,240,'ONE BRAND.',90,PAPER,True)
    txt(d,70,350,'RIGHT MOTION.',82,CITRON,True)
    for i,(name,color) in enumerate(zip(['BANG','VOX','HUASHU','DRAWING','STICKMAN'],[ORANGE,BLUE,CITRON,ROSE,SAGE])):
        y=560+i*225
        rr(d,(115,y,965,y+170),MID,24)
        pp=ease(clamp((t-i*.65)/1.2))
        rw=lerp(0,700,pp)
        rr(d,(135,y+120,135+rw,y+142),color,8)
        circles(d,205,y+79,40,color)
        txt(d,290,y+35,name,55,PAPER,True)
        txt(d,800,y+60,'ON' if pp>.8 else '··',27,CITRON)
    for k in range(17):
        a=(k*2.39+t*.85);x=540+500*math.cos(a);y=1680+120*math.sin(a)
        circles(d,x,y,4,CITRON)

def outro(im,t):
    d=ImageDraw.Draw(im); brand(d,'CTRL PULSE / V4')
    for i in range(9):
        ang=i*2*math.pi/9+t*.45; cx=540+360*math.cos(ang);cy=865+360*math.sin(ang)
        circles(d,cx,cy,50,([ORANGE,CITRON,BLUE,SAGE][i%4]))
    circles(d,540,870,220,ORANGE)
    rr(d,(388,740,694,1000),PAPER,58)
    txt(d,456,782,'C',154,INK,True)
    rr(d,(590,895,665,970),ORANGE,5)
    txt(d,116,1300,'CTRL PULSE',104,PAPER,True)
    txt(d,125,1430,'GOOD TECH. NO GATEKEEPING.',35,CITRON,True)
    txt(d,125,1690,'NATIVE FULL HD  •  NO SUBTITLES',28,SAGE)

def draw_frame(t):
    # Hard-cut changes only between genuinely animated motion worlds; no fading slides.
    if t<2.97:im=bg(INK);intro(im,t)
    elif t<5.40:im=bg(INK);bang(im,t-2.97)
    elif t<7.73:im=bg('#E7E1D5');vox(im,t-5.40)
    elif t<10.80:im=bg('#214238');huashu(im,t-7.73)
    elif t<13.77:im=bg(INK);drawing(im,t-10.80)
    elif t<17.12:im=bg(PAPER);stickman(im,t-13.77)
    elif t<24.07:im=bg(INK);router_montage(im,t-17.12)
    else:im=bg(INK);outro(im,t-24.07)
    return im

def draw_module_frame(module, local_t):
    """Public shot-level module switch used by plan renders.
    A shot renders its own world in CTRL PULSE colors.
    """
    table={
       'bang':(INK,bang),
       'vox':('#E7E1D5',vox),
       'huashu':('#214238',huashu),
       'drawing':(INK,drawing),
       'stickman':(PAPER,stickman),
    }
    if module not in table:raise ValueError('Unknown animation module '+str(module))
    color,fn=table[module]
    image=bg(color);fn(image,local_t)
    return image