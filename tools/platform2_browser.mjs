// Local rendered-page QA using an installed Chromium; no npm dependencies or deployment.
import {spawn} from 'node:child_process';
import {readFile, writeFile, mkdtemp, rm} from 'node:fs/promises';
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
const timer = setTimeout(() => { browser.kill(); process.exitCode = 1; }, 120000);
const results = [], failures = [];
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
  const manifest = JSON.parse(await readFile(join(output, 'manifest.json'), 'utf8'));
  for (const width of [320, 375, 390, 430, 768, 1024, 1440]) {
    await c('Emulation.setDeviceMetricsOverride', {width, height: width < 600 ? 800 : 1000, deviceScaleFactor: 1, mobile: width < 600});
    for (const page of manifest) {
      await c('Page.navigate', {url: 'file://' + join(output, page.file)});
      let ready = false;
      for (let n = 0; n < 60; n++) {
        ready = await evaluate('document.readyState === "complete" && !!document.querySelector(".has-menu")');
        if (ready) break;
        await new Promise(resolveWait => setTimeout(resolveWait, 20));
      }
      if (!ready) throw new Error(`Page not ready: ${page.file}`);
      const layout = JSON.parse(await evaluate(`JSON.stringify({
        viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
        scrollers:[...document.querySelectorAll('main *')].filter(e=>e.scrollWidth>e.clientWidth+2&&['auto','scroll'].includes(getComputedStyle(e).overflowX)).map(e=>e.tagName+'.'+e.className),
        missingLabels:[...document.querySelectorAll('input:not([type="hidden"]),textarea,select')].filter(e=>!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')&&!e.closest('label')&&![...document.querySelectorAll('label[for]')].some(l=>l.htmlFor===e.id)).map(e=>e.id||e.name),
        missingAlts:[...document.images].filter(e=>!e.hasAttribute('alt')).length,
        h1:document.querySelectorAll('h1').length,
        scanner:document.querySelector('#domain')?{top:document.querySelector('#domain').getBoundingClientRect().top,buttonBottom:document.querySelector('.scan-form button[type="submit"]').getBoundingClientRect().bottom}:null
      })`));
      const entry = {...page, width, ...layout};
      results.push(entry);
      if (layout.documentWidth > width + 2 || layout.scrollers.length || layout.missingLabels.length || layout.missingAlts || layout.h1 !== 1)
        failures.push(entry);
      if (page.name === 'home' && width < 600 && layout.scanner.buttonBottom > 740) failures.push({...entry, reason:'scanner below initial viewport'});
      if (page.name === 'home' && width === 390) {
        const works = await evaluate(`(() => {const b=document.querySelector('.menu-toggle');b.click();return b.getAttribute('aria-expanded')==='true'&&getComputedStyle(document.querySelector('#primary-nav')).display!=='none'})()`);
        if (!works) failures.push({...entry, reason:'menu did not open'});
        await c('Input.dispatchKeyEvent', {type:'keyDown', key:'Escape', code:'Escape', windowsVirtualKeyCode:27});
        if (!await evaluate('document.querySelector(".menu-toggle").getAttribute("aria-expanded")==="false"')) failures.push({...entry, reason:'Escape did not close menu'});
        await evaluate('document.activeElement.blur()');
      }
      if ([390,1440].includes(width) && ['home','scan-classical-fixture','scan-retry-fixture','adoption'].includes(page.name) && ['en','ar'].includes(page.lang)) {
        const screenshot = await c('Page.captureScreenshot', {format:'png'});
        await writeFile(join(output, `${page.name}-${page.lang}-${width}.png`), Buffer.from(screenshot.data,'base64'));
      }
    }
  }
  await writeFile(join(output,'responsive-results.json'),JSON.stringify({checks:results.length,failures,results},null,2));
  console.log(JSON.stringify({checks:results.length,failures:failures.map(f=>({page:f.name,lang:f.lang,width:f.width,reason:f.reason,labels:f.missingLabels,scrollers:f.scrollers,documentWidth:f.documentWidth}))},null,2));
  if (failures.length) process.exitCode = 1;
} finally {
  clearTimeout(timer);
  browser.kill();
  browser.stdio[3].destroy(); browser.stdio[4].destroy();
  await rm(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});
}
