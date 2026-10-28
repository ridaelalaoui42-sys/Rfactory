(function(){
 'use strict';
 const el=id=>document.getElementById(id),canvas=el('stage'),ctx=canvas.getContext('2d');
 const voice=el('audio'),events=RISO.getSoundEvents();let stopped=null,playing=false,offset=0,when=0,t=0;
 let format=(new URLSearchParams(location.search)).get('format')||'horizontal';
 const formats={horizontal:[1280,720],vertical:[720,1280],square:[960,960]};
 function setup(size){if(!(size in formats))size='horizontal';format=size;el('format').value=size;[canvas.width,canvas.height]=formats[size];seek(t);}
 function stopSound(){if(stopped){stopped();stopped=null;}}
 function clock(){return voice.src&&voice.readyState>=1?voice.currentTime:offset+(performance.now()-when)/1000;}
 function seek(value){t=H.clamp(Number(value)||0,0,RISO.duration);RISO.draw(ctx,canvas.width,canvas.height,t);el('scrub').value=t.toFixed(2);el('time').textContent=t.toFixed(2)+' / '+RISO.duration.toFixed(2);return t;}
 function pause(){if(!playing)return;offset=clock();playing=false;voice.pause();stopSound();el('toggle').textContent='▶ PLAY';}
 function play(){if(playing)return;playing=true;when=performance.now();offset=t;if(voice.src)voice.currentTime=t,voice.play().catch(()=>{});if(el('sfx').checked)stopped=SOUND.live(events,t,!!voice.src);el('toggle').textContent='❚❚ PAUSE';requestAnimationFrame(tick);}
 function tick(){if(!playing)return;let now=clock();if(now>=RISO.duration){pause();seek(RISO.duration);if(el('loop').checked){seek(0);play();}return;}seek(now);requestAnimationFrame(tick);}
 window.seek=seek;window.DURATION=RISO.duration;window.scoreSound=()=>events;window.renderReady=true;
 el('toggle').onclick=()=>playing?pause():play();
 el('scrub').oninput=e=>{const resume=playing;pause();seek(e.target.value);if(resume)play();};
 el('format').onchange=e=>setup(e.target.value);
 el('sfx').onchange=e=>{stopSound();if(playing&&e.target.checked)stopped=SOUND.live(events,t,!!voice.src);};
 el('loadBtn').onclick=()=>el('voice').click();
 el('voice').onchange=e=>{const f=e.target.files?.[0];if(!f)return;pause();if(voice.src.startsWith('blob:'))URL.revokeObjectURL(voice.src);voice.src=URL.createObjectURL(f);voice.currentTime=t;};
 document.addEventListener('dragover',e=>e.preventDefault());document.addEventListener('drop',e=>{e.preventDefault();const f=[...e.dataTransfer.files].find(x=>x.type.startsWith('audio/'));if(f){pause();voice.src=URL.createObjectURL(f);}});
 setup(format);
})();
