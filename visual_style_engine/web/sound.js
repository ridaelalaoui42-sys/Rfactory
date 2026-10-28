/* ClipForge original Web Audio sound kit; shared event timestamps in RISO.getSoundEvents(). */
(function(){
 'use strict';
 const SOUND=window.SOUND={};
 const names=new Set(['roller','press','paper','tick','swish','impact','ding']);
 function voiceSound(ctx,e,at,vo){
   if(!names.has(e.kind))return;
   const gain=ctx.createGain();gain.connect(ctx.destination);
   const base=e.gain*(vo?.42:.7);
   const types={roller:{f:120,end:65,d:.42,w:'sawtooth'},press:{f:135,end:55,d:.16,w:'triangle'},paper:{f:310,end:145,d:.2,w:'triangle'},tick:{f:930,end:610,d:.048,w:'square'},swish:{f:300,end:800,d:.18,w:'triangle'},impact:{f:140,end:48,d:.3,w:'sine'},ding:{f:730,end:740,d:.5,w:'sine'}};
   const p=types[e.kind];const osc=ctx.createOscillator();osc.type=p.w;
   osc.frequency.setValueAtTime(p.f,at);osc.frequency.exponentialRampToValueAtTime(p.end,at+p.d*.94);
   gain.gain.setValueAtTime(.0001,at);gain.gain.exponentialRampToValueAtTime(Math.max(.0001,base*.11),at+.009);
   gain.gain.exponentialRampToValueAtTime(.0001,at+p.d);
   osc.connect(gain);osc.start(at);osc.stop(at+p.d+.01);
 }
 SOUND.live=function(events,from=0,voiceover=false){
   const ctx=new (window.AudioContext||window.webkitAudioContext)();
   for(const e of events){if(e.time>=from)voiceSound(ctx,e,ctx.currentTime+.04+e.time-from,voiceover);}
   return ()=>{try{ctx.close();}catch(_){}};
 };
 SOUND.renderOffline=async function(events,duration,rate=48000,voiceover=false){
   const ctx=new OfflineAudioContext(2,Math.ceil(duration*rate),rate);
   for(const e of events)voiceSound(ctx,e,e.time,voiceover);
   const buf=await ctx.startRendering(),L=buf.getChannelData(0),R=buf.getChannelData(1);
   const pcm=new Int16Array(L.length*2);
   for(let i=0;i<L.length;i++){pcm[i*2]=Math.round(Math.max(-1,Math.min(1,L[i]))*32767);pcm[i*2+1]=Math.round(Math.max(-1,Math.min(1,R[i]))*32767);}
   return Array.from(new Uint8Array(pcm.buffer)); // one-time offline render, not every frame
 };
})();
