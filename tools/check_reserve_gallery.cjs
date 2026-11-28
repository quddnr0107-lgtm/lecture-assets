#!/usr/bin/env node
// A real Chromium check of the offline gallery. No external pages are opened.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..');
const base=path.join(root,'reserve-forces-act','diagrams');
const manifest=JSON.parse(fs.readFileSync(path.join(base,'manifest.json'),'utf8'));
const artifacts=process.env.RESERVE_GALLERY_QA_DIR;
(async()=>{
  const options={headless:true,args:['--no-sandbox']};
  if(process.env.RESERVE_DIAGRAM_CHROMIUM)options.executablePath=process.env.RESERVE_DIAGRAM_CHROMIUM;
  const browser=await chromium.launch(options);
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.join(base,'gallery.html')).href);
    await page.waitForFunction(()=>/현재 \d+장 표시/.test(document.querySelector('#count').textContent));
    const all=await page.locator('.diagram:not([hidden])').count();
    if(all!==manifest.diagramCount)throw new Error('Total count mismatch');
    await page.selectOption('#lesson','RL-004');
    const selected=await page.locator('.diagram:not([hidden])').count();
    if(selected!==manifest.lessons.find(l=>l.lessonId==='RL-004').diagrams.length)throw new Error('Lesson filter mismatch');
    if(artifacts){fs.mkdirSync(artifacts,{recursive:true});await page.screenshot({path:path.join(artifacts,'gallery-desktop.png')});}
    await page.fill('#q','산업');
    const searched=await page.locator('.diagram:not([hidden])').count();
    if(!searched)throw new Error('Keyword search failed');
    await page.fill('#q','검색결과가없어야하는고유문구');
    const empty=await page.locator('.diagram:not([hidden])').count();
    if(empty!==0)throw new Error('Empty search does not hide diagrams');
    await page.fill('#q','');
    await page.setViewportSize({width:390,height:844});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    if(overflow||errors.length)throw new Error(JSON.stringify({overflow,errors}));
    const wordBreak=await page.evaluate(()=>getComputedStyle(document.body).wordBreak);
    if(wordBreak!=='keep-all')throw new Error('Korean word wrapping is not protected');
    if(artifacts)await page.screenshot({path:path.join(artifacts,'gallery-mobile.png')});
    const result={renderer:'Chromium',totalDiagrams:all,selectedRL004:selected,keywordResults:searched,emptySearchResults:empty,mobileWidth:390,mobileHorizontalOverflow:overflow,koreanWordBreak:wordBreak,pageErrors:errors};
    fs.writeFileSync(path.join(base,'review','gallery-check.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1);});
