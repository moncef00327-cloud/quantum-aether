import {build} from 'esbuild';
await build({entryPoints:['main.tsx'],bundle:true,minify:true,format:'esm',jsx:'automatic',outdir:'../../static/command',entryNames:'app',assetNames:'[name]-[hash]',target:['es2020'],external:['/static/*'],legalComments:'none'});

import {mkdir,writeFile,unlink} from 'node:fs/promises';
await build({entryPoints:['ssr.tsx'],bundle:true,platform:'node',format:'cjs',jsx:'automatic',outfile:'.ssr.cjs',external:['react','react-dom/server']});
const {render}=await import('./.ssr.cjs');
await mkdir('../../templates/command',{recursive:true});
for(const lang of ['ar','en'])await writeFile('../../templates/command/'+lang+'.html',render(lang));
await unlink('.ssr.cjs');

import {execFileSync} from 'node:child_process';
execFileSync('python3',['../../tools/generate_command_shell.py'],{stdio:'inherit'});
