/* The review navigation shared by every server-rendered service page. */
(()=>{
 const aside=document.querySelector('#command-sidebar'),toggle=document.querySelector('.hamb'),closeButton=aside?.querySelector('.close'),scrim=document.querySelector('.scrim'),main=document.querySelector('#workspace-content');
 if(!aside||!toggle||!scrim||!main)return;
 const mobile=matchMedia('(max-width:850px)');let previousOverflow='',focusTimer;
 const close=(focus=false)=>{const wasOpen=aside.classList.contains('open');aside.classList.remove('open');toggle.setAttribute('aria-expanded','false');scrim.hidden=true;main.inert=false;aside.inert=mobile.matches;aside.setAttribute('aria-hidden',String(mobile.matches));aside.removeAttribute('role');aside.removeAttribute('aria-modal');clearTimeout(focusTimer);if(wasOpen)document.body.style.overflow=previousOverflow;if(focus&&wasOpen)toggle.focus()};
 const open=()=>{if(!mobile.matches)return;previousOverflow=document.body.style.overflow;aside.inert=false;aside.setAttribute('aria-hidden','false');aside.classList.add('open');aside.setAttribute('role','dialog');aside.setAttribute('aria-modal','true');toggle.setAttribute('aria-expanded','true');scrim.hidden=false;main.inert=true;document.body.style.overflow='hidden';focusTimer=setTimeout(()=>closeButton?.focus(),300)};
 toggle.addEventListener('click',open);closeButton?.addEventListener('click',()=>close(true));scrim.addEventListener('click',()=>close(true));mobile.addEventListener('change',()=>close());
 document.addEventListener('keydown',event=>{if(!aside.classList.contains('open'))return;if(event.key==='Escape'){close(true);return}if(event.key!=='Tab')return;const controls=[...aside.querySelectorAll('a[href],button')].filter(e=>e.getClientRects().length);const first=controls[0],last=controls.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}});
 document.querySelectorAll('.service-content table th').forEach(th=>{if(!th.hasAttribute('scope'))th.setAttribute('scope',th.closest('.kv')?'row':'col')});
 document.querySelectorAll('.bar-row').forEach(row=>{const bar=row.querySelector('.bar');if(bar){bar.setAttribute('role','img');bar.setAttribute('aria-label',row.textContent.trim())}});
 close();
})();
