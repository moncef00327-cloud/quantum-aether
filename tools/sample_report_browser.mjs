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



  const pause=ms=>new Promise(r=>setTimeout(r,ms));
  for(const width of [320,390,430,768,1440]){
    await c('Emulation.setDeviceMetricsOverride',{width,height:1100,deviceScaleFactor:1,mobile:width<600});
    for(const lang of ['en','ar']){
      await c('Page.navigate',{url:'http://127.0.0.1:8765/sample-report?lang='+lang});
      for(let n=0;n<100;n++){if(await evaluate('document.readyState==="complete" && !!document.querySelector(".result-head")'))break;await pause(30)}
      await evaluate('document.fonts.ready');await pause(80);
      const state=await evaluate(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,headingWidth:document.querySelector('.result-head h1').getBoundingClientRect().width,headerHeight:document.querySelector('.result-head').getBoundingClientRect().height,overflow:[...document.querySelectorAll('.service-content *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2||e.getBoundingClientRect().left< -2).map(e=>e.tagName+'.'+e.className)})`);
      results.push({width,lang,...state});if(state.scrollWidth>width+2||state.overflow.length||state.headingWidth<120||state.headerHeight>700)failures.push({width,lang,...state});
      if([390,1440].includes(width)){
        const shot=await c('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await writeFile(join(output,`sample-report-${lang}-${width}.png`),Buffer.from(shot.data,'base64'));
      }
    }
  }
  await writeFile(join(output,'sample-results.json'),JSON.stringify({checks:results.length,failures,results},null,2));
  console.log(JSON.stringify({checks:results.length,failures,results}));if(failures.length)process.exitCode=1;
} finally {
  clearTimeout(timer);
  browser.kill();
  browser.stdio[3].destroy(); browser.stdio[4].destroy();
  await rm(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});
}
