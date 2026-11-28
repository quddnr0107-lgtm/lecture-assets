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
    await page.selectOption('#lesson','');
    const bodyKeywordResults=[];
    for(const [term,expectedCount,expectedLessons] of [
      ['6시간',1,['RL-007']],
      ['관혼상제',3,['RL-007','RL-008','RL-010']],
    ]){
      await page.fill('#q',term);
      const count=await page.locator('.diagram:not([hidden])').count();
      const lessons=await page.locator('section:not([hidden])').evaluateAll(nodes=>nodes.map(n=>n.dataset.lesson));
      if(count!==expectedCount||JSON.stringify(lessons)!==JSON.stringify(expectedLessons))throw new Error('Body keyword search failed: '+term);
      bodyKeywordResults.push({term,count,lessons});
    }
    const exactLessonQueries=[];
    for(const term of ['7강','제7강','RL-007']){
      await page.fill('#q',term);
      const count=await page.locator('.diagram:not([hidden])').count();
      const lessons=await page.locator('section:not([hidden])').evaluateAll(nodes=>nodes.map(n=>n.dataset.lesson));
      if(count!==manifest.lessons.find(l=>l.lessonId==='RL-007').diagrams.length||JSON.stringify(lessons)!=='["RL-007"]')throw new Error('Exact lesson search failed: '+term);
      exactLessonQueries.push({term,count,lessons});
    }
    await page.fill('#q','7강 관혼상제');
    const combinedQueryResults=await page.locator('.diagram:not([hidden])').count();
    if(combinedQueryResults!==1)throw new Error('Lesson and keyword search failed');
    await page.fill('#q','');
    const clearedSearchResults=await page.locator('.diagram:not([hidden])').count();
    if(clearedSearchResults!==manifest.diagramCount)throw new Error('Clearing search did not restore all diagrams');
    await page.selectOption('#lesson','RL-004');
    await page.fill('#q','7강');
    const filterIntersectionResults=await page.locator('.diagram:not([hidden])').count();
    if(filterIntersectionResults!==0)throw new Error('Lesson selection and number query should both apply');
    await page.fill('#q','');
    if(await page.locator('.diagram:not([hidden])').count()!==selected)throw new Error('Clearing search did not preserve lesson selection');
    await page.setViewportSize({width:390,height:844});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    if(overflow||errors.length)throw new Error(JSON.stringify({overflow,errors}));
    const wordBreak=await page.evaluate(()=>getComputedStyle(document.body).wordBreak);
    if(wordBreak!=='keep-all')throw new Error('Korean word wrapping is not protected');
    if(artifacts)await page.screenshot({path:path.join(artifacts,'gallery-mobile.png')});
    const result={renderer:'Chromium',totalDiagrams:all,selectedRL004:selected,keywordResults:searched,emptySearchResults:empty,bodyKeywordResults,exactLessonQueries,combinedQueryResults,clearedSearchResults,filterIntersectionResults,mobileWidth:390,mobileHorizontalOverflow:overflow,koreanWordBreak:wordBreak,pageErrors:errors};
    fs.writeFileSync(path.join(base,'review','gallery-check.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exit(1);});
