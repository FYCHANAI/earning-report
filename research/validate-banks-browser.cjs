#!/usr/bin/env node
/* Chromium QA: real report initial gate only, plus separate presentation fixtures.
 * Never accepts PI, hides a live gate, sets storage, or calls an AI endpoint.
 * A fixture contains only a single component with no report access-flow code.
 */
const fs=require('fs');
const path=require('path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const url=process.env.BANK_QA_URL||'http://127.0.0.1:8765/';
const out=process.env.BANK_QA_OUT||path.join(root,'research','browser-qa');
const tickers=['jpm','c','gs','bac','ms'];
const files=tickers.flatMap(t=>['','-sc','-en'].map(s=>t+s+'.html'));
const sizes=[{name:'desktop',width:1440,height:1000},{name:'mobile',width:390,height:844}];
const checks=[],screenshots=[];
function check(name,ok,detail){checks.push({check:name,status:ok?'pass':'fail',...(detail===undefined?{}:{detail})});}
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 for(const size of sizes){
  const context=await browser.newContext({viewport:{width:size.width,height:size.height}});
  await context.route('**/api/**',route=>route.abort('blockedbyclient'));
  for(const file of files){
   const page=await context.newPage(),errors=[],failed=[],api=[];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure()?.errorText}));
   page.on('request',r=>{if(r.url().includes('/api/'))api.push(r.url())});
   await page.goto(url+file,{waitUntil:'networkidle',timeout:45000});
   const state=await page.evaluate(()=>{
    const gate=document.getElementById('pi-modal'),inner=gate?.firstElementChild;
    const r=inner?.getBoundingClientRect();
    return {gateDisplay:getComputedStyle(gate).display,bodyOverflow:document.body.style.overflow,
     piStorage:sessionStorage.getItem('pi_agreed'),gateBounds:r?{left:r.left,right:r.right,top:r.top,bottom:r.bottom}:null,
     chartKeys:Object.keys(window.charts||{}),tailwindLoaded:getComputedStyle(gate).position==='fixed',
     chartAvailable:typeof Chart==='function',viewport:innerWidth,documentWidth:document.documentElement.scrollWidth};
   });
   check(`${file}:${size.name}:initial_gate_active`,state.gateDisplay==='flex'&&state.bodyOverflow==='hidden'&&state.piStorage===null,state);
   check(`${file}:${size.name}:gate_fits_viewport`,state.gateBounds&&state.gateBounds.left>=0&&state.gateBounds.right<=size.width+1&&state.gateBounds.top>=0&&state.gateBounds.bottom<=size.height+1);
   check(`${file}:${size.name}:cdn_runtime_no_errors`,state.tailwindLoaded&&state.chartAvailable&&!errors.length&&!failed.length,{errors,failed});
   check(`${file}:${size.name}:no_live_api_calls`,!api.length,api);
   if(['jpm.html','bac-en.html','ms-sc.html'].includes(file)){
    const name=`${file.replace('.html','')}-${size.name}-initial-pi-gate.png`;
    await page.screenshot({path:path.join(out,name),fullPage:false});screenshots.push({file:name,purpose:'Real report initial PI gate; no acceptance'});
   }
   await page.close();
  }
  await context.close();
 }
 await browser.close();
 const failed=checks.filter(c=>c.status==='fail');
 const report={status:failed.length?'fail':'pass',checks,screenshots,limitations:[
  'Only unauthenticated initial-gate behavior was tested on the real reports. No PI acceptance, gate manipulation, storage write, or live AI call occurred.',
  'This does not establish rendering of content behind the gate or production deployment. Presentation fixture checks, if performed, are separate.'
 ]};
 fs.writeFileSync(path.join(out,'browser-gate-validation.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({status:report.status,checks:checks.length,failed,output:out},null,2));
 process.exitCode=failed.length?1:0;
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
