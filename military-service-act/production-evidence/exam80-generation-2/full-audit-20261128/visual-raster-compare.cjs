#!/usr/bin/env node
/* Compare decoded committed WebP pixels with the SVG rendered through sharp.
 * Production files are never overwritten. */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const sharp=require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES,'sharp'));
const root=path.resolve(__dirname,'../../../..');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'military-service-act/diagrams-manifest.json'),'utf8'));
const rows=[];sharp.concurrency(1);let next=0;
async function worker(){
 while(next<manifest.items.length){
  const item=manifest.items[next++];
  try{
   const svg=await sharp(path.join(root,item.files.svg.path)).ensureAlpha().raw().toBuffer({resolveWithObject:true});
   const webp=await sharp(path.join(root,item.files.webp.path)).ensureAlpha().raw().toBuffer({resolveWithObject:true});
   let maxDiff=0,changed=0,absolute=0;
   if(svg.data.length===webp.data.length){for(let k=0;k<svg.data.length;k++){const d=Math.abs(svg.data[k]-webp.data[k]);if(d){changed++;absolute+=d;if(d>maxDiff)maxDiff=d}}}
   const row={id:item.id,svg_info:svg.info,webp_info:webp.info,identical:svg.data.equals(webp.data),changed_channels:changed,max_channel_difference:maxDiff,mean_absolute_difference:absolute/Math.max(svg.data.length,1),svg_pixel_sha256:crypto.createHash('sha256').update(svg.data).digest('hex'),webp_pixel_sha256:crypto.createHash('sha256').update(webp.data).digest('hex')};
   rows.push(row);
  }catch(e){rows.push({id:item.id,error:String(e)})}
 }
}
(async()=>{await Promise.all([worker(),worker(),worker(),worker()]);rows.sort((a,b)=>a.id.localeCompare(b.id));const report={date_kst:'2026-11-28',method:'sharp SVG render vs decoded committed lossless WebP, RGBA 8-bit exact comparison',renderer_versions:sharp.versions,summary:{pages:rows.length,exact_pixel_matches:rows.filter(x=>x.identical).length,mismatches:rows.filter(x=>x.identical===false).length,errors:rows.filter(x=>x.error).length},pages:rows};fs.writeFileSync(path.join(__dirname,'visual-raster-comparison.json'),JSON.stringify(report,null,2)+'\n');console.log(report.summary)})().catch(e=>{console.error(e);process.exitCode=1});
