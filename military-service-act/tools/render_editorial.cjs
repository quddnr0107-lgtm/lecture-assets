#!/usr/bin/env node
/* Rasterize the SVG source and update hashes; run after build_editorial.py. */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
let sharp;
try {sharp=require('sharp')} catch {sharp=require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES,'sharp'))}
const root=path.resolve(__dirname,'../..');
const mf=path.join(root,'military-service-act/diagrams-manifest.json');
const manifest=JSON.parse(fs.readFileSync(mf,'utf8'));
const makePng=process.argv.includes('--png');
sharp.concurrency(1);
async function one(item) {
  const svg=path.join(root,item.files.svg.path);
  const target=svg.slice(0,-4);
  await sharp(svg).webp({lossless:true,effort:6}).toFile(target+'.webp');
  if(makePng) await sharp(svg).png({compressionLevel:9,palette:false}).toFile(target+'.png');
  if(!makePng) delete item.files.png;
  for(const ext of (makePng ? ['png','webp'] : ['webp'])) {
    const p=target+'.'+ext,b=fs.readFileSync(p);
    item.files[ext]={path:path.relative(root,p),bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex')};
  }
}
(async()=>{
  let n=0;
  const queue=[...manifest.items];
  await Promise.all(Array.from({length:4},async()=>{while(queue.length){await one(queue.shift());n++;if(n%50===0)process.stdout.write(`Rendered ${n}/${manifest.items.length}\n`)}}));
  fs.writeFileSync(mf,JSON.stringify(manifest,null,2)+'\n');
  console.log(JSON.stringify({rendered:n,totalBytes:manifest.items.reduce((n,x)=>n+Object.values(x.files).reduce((s,f)=>s+f.bytes,0),0)}));
})().catch(e=>{console.error(e);process.exit(1)});
