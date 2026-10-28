#!/usr/bin/env node
/* Headless native Canvas frame renderer. Uses the exact browser style draw() code. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
let Canvas;
try{({Canvas}=require('skia-canvas'));}catch(err){
 process.stderr.write('Install skia-canvas: npm install skia-canvas (or set NODE_PATH)\n');process.exit(2);
}
const root=path.resolve(__dirname,'..');
const argv=process.argv.slice(2);
function opt(name,def){const i=argv.indexOf('--'+name);return i>=0?argv[i+1]:def;}
const fmt=opt('format','horizontal'),w=Number(opt('width',960));
const h=fmt==='vertical'?Math.round((w*16/9)/2)*2:fmt==='square'?w:Math.round((w*9/16)/2)*2;
const fps=Number(opt('fps',24)),duration=Number(opt('duration',15));
const poster=opt('poster',null),single=opt('single',null);
const seedContext={};
global.window=global;
global.document={createElement(name){if(name!=='canvas')throw Error('unexpected element '+name);return new Canvas(1,1);}};
for(const f of ['harness.js','styles/risograph.js']){
 vm.runInThisContext(fs.readFileSync(path.join(root,'web',f),'utf8'),{filename:f});
}
(async()=>{
 if(argv.includes('--events')){process.stdout.write(JSON.stringify(RISO.getSoundEvents()));return;}
 if(argv.includes('--probe')){process.stdout.write(JSON.stringify({style:RISO.id,beats:RISO.beats,length:RISO.duration,formats:['horizontal','vertical','square']}));return;}
 const canvas=new Canvas(w,h),ctx=canvas.getContext('2d');
 if(single!==null){RISO.draw(ctx,w,h,Number(single));fs.writeFileSync(poster||'frame.png',await canvas.toBuffer('png'));return;}
 if(!(fps>0&&fps<=60&&duration>0&&duration<=15))throw Error('invalid fps/duration');
 const total=Math.round(fps*duration);
 for(let i=0;i<total;i++){
   RISO.draw(ctx,w,h,i/fps);
   const bytes=await canvas.toBuffer('jpeg',{quality:.88});
   if(!process.stdout.write(bytes))await new Promise(r=>process.stdout.once('drain',r));
   if((i+1)%Math.max(1,Math.round(total/4))===0)process.stderr.write(`Rendered ${i+1}/${total} frames\n`);
 }
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
