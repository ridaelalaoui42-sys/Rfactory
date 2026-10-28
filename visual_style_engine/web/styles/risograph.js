/* ClipForge Risograph: original printmaking renderer with three separate ink plates.
   Content and timing are data, so new scripts do not require rewriting the texture engine.
   Pure seek(t): identical t + project + viewport produces identical frame pixels. */
(function(){
 'use strict';
 const H=window.H;
 const COLORS={yellow:'#ffd900',pink:'#fa398e',blue:'#2258b6'};
 const PAPER='#eee6d3';
 const BEATS=[
  {id:1,start:0,end:2.5,text:'HOW DO MACHINES LEARN?',scene:0,description:'Build three ink plates into an oversized editorial question.',sound:'press'},
  {id:2,start:2.5,end:5,text:'EXAMPLES',scene:0,description:'Introduce handwritten cards as repeated training examples.',sound:'tick'},
  {id:3,start:5,end:7.5,text:'FIND THE PATTERN',scene:1,description:'Re-register plates into a three-column classification chart.',sound:'roller'},
  {id:4,start:7.5,end:10,text:'COMPARE',scene:1,description:'Reveal a new sample and compare it to known categories.',sound:'stamp'},
  {id:5,start:10,end:12.4,text:'PREDICT',scene:2,description:'Transition to a bold result with large numeric confidence.',sound:'impact'},
  {id:6,start:12.4,end:15,text:'PRACTICE → BETTER GUESSES',scene:2,description:'End with a takeaway and a final three-plate registration.',sound:'ding'}
 ];
 let cachedPaper=null,cachedSize='',plate=null,ctxP=[];
 const duration=15;
 const rad=Math.PI/180;
 const m=(value,base,scale)=>value*scale;
 function setBrush(ctx,color){ctx.fillStyle=color;ctx.strokeStyle=color;ctx.lineCap='round';ctx.lineJoin='round';}
 function resetCanvas(ctx,W,Hh){ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,W,Hh);ctx.globalCompositeOperation='source-over';ctx.globalAlpha=1;}
 function ensureBuffers(W,Hh){
  const key=W+'x'+Hh;
  if(key===cachedSize)return;
  cachedSize=key; cachedPaper=H.canvas(W,Hh);plate=['yellow','pink','blue'].map(()=>H.canvas(W,Hh));ctxP=plate.map(c=>c.getContext('2d'));
  const p=cachedPaper.getContext('2d');p.fillStyle=PAPER;p.fillRect(0,0,W,Hh);
  const r=H.rng(204267),n=Math.round(W*Hh*0.014);
  for(let i=0;i<n;i++){
    const x=r()*W,y=r()*Hh,z=0.2+r()*1.1;
    p.fillStyle=r()>0.5?'rgba(89,68,44,.11)':'rgba(255,255,255,.16)';
    p.fillRect(x,y,z,z*3);
  }
  // Slightly warm imperfect paper edges.
  const v=p.createRadialGradient(W*.5,Hh*.48,Math.min(W,Hh)*.1,W*.5,Hh*.5,Math.max(W,Hh)*.75);
  v.addColorStop(0,'rgba(255,250,234,0)');v.addColorStop(1,'rgba(82,59,39,.10)');p.fillStyle=v;p.fillRect(0,0,W,Hh);
 }
 function inkRect(ctx,x,y,w,h,radius=0){
  if(radius){H.roundRect(ctx,x,y,w,h,radius);ctx.fill();}
  else ctx.fillRect(x,y,w,h);
 }
 function dots(ctx,x,y,w,h,size=8,amount=1){
  const s=Math.max(5,size); ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();
  const rr=H.rng(Math.floor(w*h)+17);ctx.globalAlpha=amount;
  for(let yy=y+s/2;yy<y+h;yy+=s){for(let xx=x+s/2;xx<x+w;xx+=s){
   const dx=(rr()-.5)*s*.18,dy=(rr()-.5)*s*.18;
   ctx.beginPath();ctx.arc(xx+dx,yy+dy,s*(.2+rr()*.12),0,Math.PI*2);ctx.fill();
  }}ctx.restore();
 }
 function text(ctx,s,x,y,maxW,desired=68,align='left'){
  ctx.textAlign=align;ctx.textBaseline='alphabetic';H.fitText(ctx,s,x,y,maxW,desired,'900','DejaVu Sans, Arial Black, sans-serif');
 }
 function label(ctx,s,x,y,size=25,align='left'){
  ctx.font=`700 ${size}px "Liberation Mono", monospace`;ctx.textAlign=align;ctx.fillText(s,x,y);
 }
 function line(ctx,pts,thickness=9){ctx.lineWidth=thickness;ctx.beginPath();pts.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.stroke();}
 function arrow(ctx,x,y,xx,yy,thick=7){
  line(ctx,[[x,y],[xx,yy]],thick);const a=Math.atan2(yy-y,xx-x),d=18;
  line(ctx,[[xx-d*Math.cos(a-.65),yy-d*Math.sin(a-.65)],[xx,yy],[xx-d*Math.cos(a+.65),yy-d*Math.sin(a+.65)]],thick);
 }
 function cropMarker(ctx,x,y,sz=15){line(ctx,[[x-sz,y],[x+sz,y]],3);line(ctx,[[x,y-sz],[x,y+sz]],3);}
 function sceneMotion(t,sceneStart,sceneEnd){return H.smooth(sceneStart,sceneStart+.85,t)*H.smooth(sceneEnd,sceneEnd-.7,t);}
 function currentScene(t){return t<5?0:t<10?1:2;}
 function plateReveal(t,scene){const start=[0,5,10][scene];return H.clamp((t-start)/.7);}
 function drawScene0(P,W,V,t){
  const [Y,PINK,B]=P;const isPortrait=V>W;const unit=isPortrait?Math.min(W/720,V/1280):Math.min(W/1280,V/720);const cx=W/2,margin=W*.07;
  const titleSize=isPortrait?70*unit:110*unit;
  const top=V*(isPortrait?.21:.24);
  const begin=H.smooth(.1,1.0,t);
  const title='HOW MACHINES';const title2='LEARN';
  setBrush(Y,'#000');
  inkRect(Y,margin*.65,top-titleSize*1.05,(W-margin*1.3)*begin,titleSize*1.17,Math.max(1,unit*7));
  setBrush(B,'#000');
  text(B,title,cx,top-titleSize*.11,W-margin*2,titleSize*.76,'center');
  text(B,title2,cx,top+titleSize*1.0,W-margin*2,titleSize*1.55,'center');
  setBrush(PINK,'#000');
  PINK.save();PINK.translate(cx,top+titleSize*1.05);PINK.rotate(-.055);PINK.lineWidth=15*unit;PINK.strokeRect(-W*.26,-titleSize*.79,W*.52*H.smooth(.9,2.0,t),titleSize*1.03);PINK.restore();
  const cardY=V*(isPortrait?.57:.65);
  const cardW=W*(isPortrait?.23:.19);const gap=W*.035;
  [-1,0,1].forEach((i,ind)=>{
    const x=cx+i*(cardW+gap)-cardW/2,show=H.smooth(2.25+ind*.35,2.65+ind*.35,t);
    setBrush(Y,'#000');inkRect(Y,x,cardY+8*unit,cardW*show,cardW*.96,8*unit);
    setBrush(B,'#000');B.strokeStyle='#000';B.lineWidth=5*unit;B.strokeRect(x,cardY,cardW*show,cardW*.96);
    if(show>.4){
      setBrush(PINK,'#000');PINK.beginPath();PINK.arc(x+cardW*.5,cardY+cardW*.37,(ind===1?.18:.13)*cardW*show,0,Math.PI*2);PINK.fill();
      setBrush(B,'#000');label(B,['A','B','C'][ind],x+cardW*.5,cardY+cardW*.82,Math.max(18,27*unit),'center');
    }
  });
  setBrush(B,'#000');label(B,'01 / EXAMPLES',margin,V*.9,Math.max(18,25*unit));
  setBrush(PINK,'#000');cropMarker(PINK,W-margin,V*.91,16*unit);
 }
 function drawScene1(P,W,V,t){
  const [Y,PINK,B]=P,portrait=V>W,unit=portrait?Math.min(W/720,V/1280):Math.min(W/1280,V/720),cx=W*.5,margin=W*.09;
  const titleTop=V*.18;
  setBrush(B,'#000');text(B,'FIND THE',cx,titleTop,W*.85,83*unit,'center');
  setBrush(PINK,'#000');text(PINK,'PATTERN',cx,titleTop+86*unit,W*.85,102*unit,'center');
  const rowY=V*(portrait?.37:.43),cardW=W*.2,dx=W*.26;
  const choices=['01','02','03'];
  choices.forEach((n,i)=>{
    const x=cx+(i-1)*dx;
    const appear=H.smooth(5.4+i*.25,6.2+i*.25,t);
    setBrush(Y,'#000');inkRect(Y,x-cardW/2,rowY,cardW*appear,cardW*.85,12*unit);
    setBrush(PINK,'#000');dots(PINK,x-cardW/2,rowY,cardW*appear,cardW*.85,Math.max(7,12*unit),.22);
    setBrush(B,'#000');B.lineWidth=6*unit;B.strokeRect(x-cardW/2,rowY,cardW*appear,cardW*.85);
    if(appear>.7){
      const py=rowY+cardW*.42;
      if(i===0){B.beginPath();B.arc(x,py,cardW*.21,0,7);B.stroke();}
      else if(i===1){B.lineWidth=8*unit;B.strokeRect(x-cardW*.2,py-cardW*.2,cardW*.4,cardW*.4);}
      else {line(B,[[x,py-cardW*.22],[x-cardW*.2,py+cardW*.2],[x+cardW*.2,py+cardW*.2],[x,py-cardW*.22]],6*unit);}
      setBrush(PINK,'#000');label(PINK,n,x,rowY+cardW*.72,25*unit,'center');
    }
  });
  const arrowY=rowY+cardW*1.12;
  const sweep=H.smooth(7.1,8.3,t);
  setBrush(B,'#000');arrow(B,margin,arrowY,W-margin*sweep,arrowY,6*unit);
  setBrush(PINK,'#000');label(PINK,'COMPARE THE NEW EXAMPLE',cx,V*(portrait?.70:.81),Math.max(17,28*unit),'center');
  if(t>8){setBrush(PINK,'#000');PINK.lineWidth=9*unit;PINK.beginPath();PINK.ellipse(cx,rowY+cardW*.45,cardW*.85,cardW*.65,-.2,0,Math.PI*2*H.smooth(8,9,t));PINK.stroke();}
  setBrush(B,'#000');label(B,'02 / RECOGNITION',margin,V*.94,Math.max(16,23*unit));
 }
 function drawScene2(P,W,V,t){
  const [Y,PINK,B]=P,portrait=V>W,unit=portrait?Math.min(W/720,V/1280):Math.min(W/1280,V/720),cx=W*.5;
  setBrush(Y,'#000');inkRect(Y,W*.1,V*.22,W*.8*H.smooth(10.05,10.75,t),V*.24,10*unit);
  setBrush(B,'#000');dots(B,W*.1,V*.22,W*.8,V*.24,Math.max(8,13*unit),.20);
  setBrush(B,'#000');text(B,'PREDICT',cx,V*.38,W*.87,145*unit,'center');
  setBrush(PINK,'#000');text(PINK,'97%',cx,V*.64,W*.85,205*unit,'center');
  PINK.lineWidth=10*unit;PINK.beginPath();PINK.arc(cx,V*.51,W*.32,-.3*Math.PI,2*Math.PI*H.smooth(10.3,12.2,t));PINK.stroke();
  setBrush(B,'#000');label(B,'CONFIDENCE / DEMO ONLY',cx,V*.69,Math.max(17,25*unit),'center');
  const takeaway=H.smooth(12.3,13,t);setBrush(B,'#000');
  const tx=V>W?'PRACTICE MAKES':'PRACTICE  →  BETTER GUESSES';
  text(B,tx,cx,V*.82,W*.85,(V>W?52:56)*unit,'center');
  if(V>W)text(B,'BETTER GUESSES',cx,V*.89,W*.85,52*unit,'center');
  setBrush(PINK,'#000');line(PINK,[[W*.13,V*.855],[W*(.13+.72*takeaway),V*.855]],11*unit);
  setBrush(B,'#000');label(B,'03 / TAKEAWAY',W*.08,V*.95,Math.max(17,22*unit));
 }
 const DRAW=[drawScene0,drawScene1,drawScene2];
 function draw(ctx,W,V,t){
  ensureBuffers(W,V);
  t=H.clamp(t,0,duration);
  resetCanvas(ctx,W,V);ctx.drawImage(cachedPaper,0,0);
  const scene=currentScene(t),progress=plateReveal(t,scene);
  for(let i=0;i<3;i++)resetCanvas(ctxP[i],W,V);
  DRAW[scene](ctxP,W,V,t);
  // Registration, paper defects and halftone print finish per plate.
  const noise=H.fingerprint(t,400);const scatter=H.rng(900+scene);
  for(let k=0;k<3;k++){
   const px=ctxP[k];px.save();px.globalCompositeOperation='destination-out';
   // Tiny ink pinholes reproduce uneven mechanical transfer.
   for(let i=0;i<Math.round(W*V/5500);i++){
     const x=scatter()*W,y=scatter()*V;
     px.fillStyle='rgba(0,0,0,.5)';px.beginPath();px.arc(x,y,(1.0+scatter()*1.7)*Math.max(.6,Math.min(W,V)/720),0,Math.PI*2);px.fill();
   }px.restore();
   px.save();px.globalCompositeOperation='source-in';px.fillStyle=COLORS[['yellow','pink','blue'][k]];px.fillRect(0,0,W,V);px.restore();
   const pass=H.clamp((progress-.15*k)/.55);
   if(pass<=0)continue;
   const offsetX=(k-1)*Math.max(1,W/450)+(noise[k]-.5)*1.6;
   const offsetY=(k===1?2:-1)*Math.max(1,V/720)+(noise[2-k]-.5)*1.6;
   ctx.save();ctx.globalAlpha=H.smooth(0,1,pass);ctx.globalCompositeOperation='multiply';
   ctx.drawImage(plate[k],offsetX,offsetY-((1-pass)*V*.36));ctx.restore();
  }
  // Fine colored screen pattern: explicitly procedural and subtly animated at 8fps.
  const count=H.rng(1207+Math.floor(t*8));ctx.save();ctx.globalAlpha=.11;
  for(let i=0;i<Math.round(W*V/3000);i++){
   const x=count()*W,y=count()*V,s=1+count()*2.2;
   ctx.fillStyle=i%3===0?COLORS.yellow:i%3===1?COLORS.pink:COLORS.blue;ctx.fillRect(x,y,s,s);
  }ctx.restore();
  // Print crop marks anchored to the page, not to the animated ink.
  ctx.save();ctx.fillStyle='#24498d';ctx.font=`bold ${Math.max(10,Math.floor(Math.min(W,V)/45))}px monospace`;
  ctx.fillText('CF / RISO 001',W*.055,V*.047);
  ctx.textAlign='right';ctx.fillText(`${(t).toFixed(2)} / ${duration}.00`,W*.94,V*.047);ctx.restore();
 }
 function getSoundEvents(){
  const e=[{time:.10,kind:'roller',gain:.4},{time:.35,kind:'press',gain:.6},{time:.75,kind:'tick',gain:.3},{time:1.15,kind:'press',gain:.25},
   {time:2.5,kind:'paper',gain:.4},{time:2.85,kind:'tick',gain:.25},{time:3.22,kind:'tick',gain:.25},{time:3.6,kind:'tick',gain:.25},
   {time:5.0,kind:'roller',gain:.65},{time:5.28,kind:'press',gain:.45},{time:5.5,kind:'tick',gain:.3},{time:5.8,kind:'press',gain:.35},
   {time:7.5,kind:'swish',gain:.3},{time:8.2,kind:'tick',gain:.35},
   {time:10.0,kind:'roller',gain:.55},{time:10.3,kind:'press',gain:.6},{time:11.2,kind:'impact',gain:.55},
   {time:12.4,kind:'paper',gain:.4},{time:13.4,kind:'tick',gain:.25},{time:14.1,kind:'ding',gain:.5}];
  return e;
 }
 window.RISO={id:'risograph_zine',duration,beats:BEATS,draw,getSoundEvents,version:'0.1.0',
   description:'Original three-plate, seeded-time ink printing animation'};
})();
