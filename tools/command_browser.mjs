// Local rendered-page QA using an installed Chromium; no npm dependencies or deployment.
import {spawn} from 'node:child_process';
import {readFile, writeFile, mkdtemp, mkdir, rm} from 'node:fs/promises';
import {tmpdir, homedir} from 'node:os';
import {resolve, join} from 'node:path';

const output = resolve(process.argv[2] || 'artifacts/platform2/after');
const chromium = process.env.CHROME_BIN || join(homedir(), '.cache/ms-playwright/chromium-1140/chrome-linux/chrome');
const profile = await mkdtemp(join(tmpdir(), 'aether-browser-'));
const browser = spawn(chromium, ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
  '--disable-gpu', '--remote-debugging-pipe', '--no-first-run', '--no-default-browser-check',
  `--user-data-dir=${profile}`, '--allow-file-access-from-files'], {stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe']});
let nextId = 0, buffer = '', stderr = '';
const pending = new Map();
browser.stderr.on('data', data => { stderr += data; });
browser.on('error', error => { for (const job of pending.values()) job.reject(error); });
browser.on('exit', code => { for (const job of pending.values()) job.reject(new Error(`Chromium exit ${code}: ${stderr.slice(-1000)}`)); });
for (const pipe of [browser.stdio[3], browser.stdio[4]]) pipe.on('error', error => { for (const job of pending.values()) job.reject(error); });
browser.stdio[4].on('data', data => {
  buffer += data.toString();
  let end;
  while ((end = buffer.indexOf('\0')) >= 0) {
    const message = JSON.parse(buffer.slice(0, end)); buffer = buffer.slice(end + 1);
    const job = pending.get(message.id);
    if (job) { pending.delete(message.id); message.error ? job.reject(new Error(JSON.stringify(message.error))) : job.resolve(message.result); }
  }
});
function command(method, params = {}, sessionId) {
  return new Promise((resolveJob, reject) => {
    const id = ++nextId;
    pending.set(id, {resolve: resolveJob, reject});
    browser.stdio[3].write(JSON.stringify({id, method, params, sessionId}) + '\0');
  });
}
const timer = setTimeout(() => { browser.kill(); process.exitCode = 1; }, 240000);
const results = [], failures = [];
await mkdir(output,{recursive:true});
try {
  const {targetId} = await command('Target.createTarget', {url: 'about:blank'});
  const {sessionId} = await command('Target.attachToTarget', {targetId, flatten: true});
  const c = (method, params) => command(method, params, sessionId);
  const evaluate = async expression => {
    const result = await c('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  await c('Page.enable');
  await c('Page.bringToFront');

  const pause = ms=>new Promise(r=>setTimeout(r,ms));
  async function settled(){for(let i=0;i<80;i++){if(await evaluate('!!document.querySelector(".intro h1")')){await pause(180);return;}await pause(30);}throw Error('React did not mount');}
  for (const width of [320,390,768,1440]) {
    await c('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
    for(const lang of ['ar','en']) {
      await c('Page.navigate',{url:`http://127.0.0.1:8765/?lang=${lang}`});await settled();
      for(const tab of ['overview','scanner','tracker','monitor','guides','business','llm']) {
        await evaluate(`location.hash=${JSON.stringify(tab)}`);await pause(120);
        const state=await evaluate(`({width:innerWidth,scroll:document.documentElement.scrollWidth,lang:document.documentElement.lang,h1:document.querySelectorAll('h1').length,active:document.querySelector('nav button[aria-current="page"]')?.textContent,resources:document.querySelectorAll('.resource').length,labels:[...document.querySelectorAll('input')].every(e=>document.querySelector('label[for="'+e.id+'"]')),brokenLinks:[...document.querySelectorAll('a[href]')].filter(a=>a.getAttribute('href').includes('speckledblanket')).length})`);
        results.push({width,lang,tab,...state});
        if(state.scroll>width+2||state.h1!==1||state.lang!==lang||!state.labels||state.brokenLinks)failures.push({width,lang,tab,...state});
        if(tab==='business'&&state.resources!==3)throw Error('Business resources missing');
        if(tab==='llm'&&state.resources!==3)throw Error('LLM resources missing');
        if([390,1440].includes(width)&&['overview','business','llm'].includes(tab)){
          const shot=await c('Page.captureScreenshot',{format:'png'});await writeFile(join(output,`${tab}-${lang}-${width}.png`),Buffer.from(shot.data,'base64'));
        }
      }
      if(width<850){
        await evaluate('document.querySelector(".hamb").click()');await pause(1100);
        if(!await evaluate('document.body.style.overflow==="hidden" && document.activeElement.className==="close" && document.querySelector("main").inert'))throw Error('Drawer focus/scroll trap failed '+JSON.stringify(await evaluate('({width:innerWidth,overflow:document.body.style.overflow,active:document.activeElement?.tagName,main:document.querySelector("main").inert,drawer:document.querySelector("aside").className,closeDisplay:getComputedStyle(document.querySelector(".close")).display,closeVisibility:getComputedStyle(document.querySelector(".close")).visibility,inert:document.querySelector("aside").inert,rect:document.querySelector(".close").getBoundingClientRect().toJSON()})')));
        await c('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await pause(120);
        if(await evaluate('!!document.querySelector("aside.open")'))throw Error('Escape failed');
      }
    }
  }
  await c('Page.navigate',{url:'http://127.0.0.1:8765/?lang=en#scanner'});await settled();
  await evaluate('document.querySelector(".scanner form").dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}))');await pause(80);
  if(!await evaluate('!!document.querySelector("#domain-error")'))throw Error('Invalid input was accepted');
  await evaluate(`(()=>{const input=document.querySelector('#domain');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(input,'fixture.example');input.dispatchEvent(new Event('input',{bubbles:true}));})()`);await pause(80);
  await evaluate('document.querySelector(".scanner form").dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}))');await pause(1000);
  if(!await evaluate('location.pathname.startsWith("/scan/")'))throw Error('Live scanner POST did not reach report: '+await evaluate('location.href'));

  const services=['/business','/pricing','/monitoring','/agency','/adoption','/guides','/research','/gravity','/sample-report','/compare','/scanning','/impressum','/datenschutz','/agb','/scan/qa-classical','/scan/qa-retry','/report/qa-private-classical'];
  for(const width of [320,390,768,1440]){
    await c('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
    for(const lang of ['ar','en'])for(const path of services){
      await c('Page.navigate',{url:'http://127.0.0.1:8765'+path+'?lang='+lang});
      for(let n=0;n<100;n++){if(await evaluate('document.readyState==="complete" && !!document.querySelector(".command-service")'))break;await pause(30)}
      await pause(80);
      const state=await evaluate(`({width:innerWidth,scroll:document.documentElement.scrollWidth,oldMenu:!!document.querySelector('#primary-nav,.mobile-dock,.site-header'),oldAssets:[...document.querySelectorAll('link[rel=stylesheet],script[src]')].map(e=>e.href||e.src).filter(url=>['/aether.css','/aether-dark.css','/aether-ui.js','/style.css','/observatory.css'].some(name=>url.includes(name))),navCount:document.querySelectorAll('#workspace-nav>a').length,main:!!document.querySelector('.service-content')})`);
      results.push({width,lang,path,...state});
      if(state.scroll>width+2||state.oldMenu||state.oldAssets.length||state.navCount!==7||!state.main)failures.push({width,lang,path,...state});
      if(width===390&&path==='/business'){
        await evaluate('document.querySelector(".hamb").click()');await pause(1100);
        if(!await evaluate('document.querySelector("aside.open") && document.activeElement.className==="close" && document.querySelector("main").inert'))throw Error('Service drawer focus failed');
        const shot=await c('Page.captureScreenshot',{format:'png'});await writeFile(join(output,`business-drawer-${lang}-${width}.png`),Buffer.from(shot.data,'base64'));
        await c('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await pause(80);
        if(await evaluate('!!document.querySelector("aside.open")'))throw Error('Service Escape failed');
      }
      if([390,1440].includes(width)&&['/business','/adoption','/scan/qa-classical','/monitoring'].includes(path)){
        const shot=await c('Page.captureScreenshot',{format:'png'});await writeFile(join(output,`${path.slice(1).replaceAll('/','-')}-${lang}-${width}.png`),Buffer.from(shot.data,'base64'));
      }
    }
  }
  await writeFile(join(output,'responsive-results.json'),JSON.stringify({checks:results.length,failures,results},null,2));
  console.log(JSON.stringify({checks:results.length,failures,fixtureScan:'passed',drawer:'passed',validation:'passed'}));
  if(failures.length)process.exitCode=1;
} finally {
  clearTimeout(timer);
  browser.kill();
  browser.stdio[3].destroy(); browser.stdio[4].destroy();
  await rm(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});
}
