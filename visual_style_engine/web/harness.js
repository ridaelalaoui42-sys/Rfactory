/* ClipForge procedural video runtime. Original implementation, no external asset dependencies. */
(function () {
  'use strict';
  const H = window.H = {};
  H.clamp = (x, a=0, b=1) => Math.min(b, Math.max(a, x));
  H.lerp = (a,b,t) => a+(b-a)*t;
  H.smooth = (a,b,x) => { const t=H.clamp((x-a)/(b-a)); return t*t*(3-2*t); };
  H.ease = t => 1 - Math.pow(1-H.clamp(t),3);
  H.rng = function(seed) { // Mulberry32, deterministic across platforms and scrubs.
    let a=(seed>>>0)||1;
    return () => { a=(a+0x6D2B79F5)|0; let t=Math.imul(a^(a>>>15),1|a); t^=t+Math.imul(t^(t>>>7),61|t); return ((t^(t>>>14))>>>0)/4294967296; };
  };
  H.canvas = (w,h) => { const c=document.createElement('canvas');c.width=w;c.height=h;return c; };
  H.roundRect = (ctx,x,y,w,h,r) => {ctx.beginPath();ctx.roundRect(x,y,w,h,r);};
  H.fitText=(ctx,text,x,y,maxWidth,fontSize=55,weight='900',family='sans-serif')=>{
    let size=fontSize;do{ctx.font=`${weight} ${size}px ${family}`;if(ctx.measureText(text).width<=maxWidth)break;size-=2;}while(size>27);
    ctx.fillText(text,x,y);return size;
  };
  H.fingerprint=(t,seed=7)=>{ const r=H.rng((Math.floor(t*8)+1)*2654435761^seed);return [r(),r(),r()]; };
})();
