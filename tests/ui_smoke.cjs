/* Dependency-free JS render/controller smoke test. NOT a browser/layout test. */
'use strict';
const vm=require('node:vm');const fs=require('node:fs');const path=require('node:path');const os=require('node:os');const {spawn}=require('node:child_process');const assert=require('node:assert/strict');const crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'receipt-ui-'));
const child=spawn(process.env.PYTHON || 'python3',['server.py','--port','0','--db',path.join(tmp,'ui.sqlite')],{cwd:root,stdio:['ignore','pipe','pipe']});
const errors=[];child.stderr.on('data',d=>errors.push(String(d)));
(async()=>{
 const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Server startup timed out')),10000);child.stdout.on('data',chunk=>{const m=String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0]);}});child.on('error',reject);});
 const elements=new Map();const get=s=>{if(!elements.has(s))elements.set(s,{innerHTML:'',textContent:'',value:'',disabled:false,open:false,classList:{add(){},remove(){},toggle(){}},addEventListener(){},setAttribute(){},showModal(){this.open=true;},close(){this.open=false;}});return elements.get(s);};
 const context=vm.createContext({document:{querySelector:get,querySelectorAll:()=>[],addEventListener(){}},window:{scrollTo(){}},localStorage:{getItem:()=>null,setItem(){}},fetch:(url,o)=>fetch(base+url,o),crypto,console,URL,FormData,setTimeout,clearTimeout});
 vm.runInContext(fs.readFileSync(path.join(root,'web/app.js'),'utf8'),context);
 await vm.runInContext('load()',context);
 assert.match(get('#app').innerHTML,/Outcome queue/);assert.match(get('#queue-body').innerHTML,/Quality triage threshold/);
 for(const v of ['queue','timeline','learning','audit'])await vm.runInContext(`view='${v}';selected=null;${v==='audit'?'renderAudit()':'render()'}`,context);
 for(let i=1;i<=9;i++){vm.runInContext(`selected='oc-demo-${String(i).padStart(3,'0')}';renderDetail()`,context);assert.match(get('#app').innerHTML,/Evidence & version history/);}
 vm.runInContext('newContract()',context);assert.match(get('#dialog-body').innerHTML,/Minimum improvement/);
 const defaults=await (await fetch(base+'/api/state')).json();const form=new Map(Object.entries({...defaults.defaults,title:'UI <img onerror=attack()> check',action_id:'act-ui-check',decision_id:'decision-ui-check',confounders:''}));
 context.uiForm=form;await vm.runInContext('modalSave(uiForm)',context);assert.match(get('#app').innerHTML,/UI &lt;img/);assert.doesNotMatch(get('#app').innerHTML,/<img onerror/);
 for(const action of ['validate','arm','complete']){vm.runInContext(`actionModal('${action}')`,context);context.uiForm=new Map([['reason','UI controller workflow test']]);await vm.runInContext('modalSave(uiForm)',context);}
 await vm.runInContext("command('advance',{days:23})",context);
 vm.runInContext("actionModal('measure')",context);await vm.runInContext('modalSave(uiForm)',context);
 assert.match(get('#app').innerHTML,/Accept receipt/);
 vm.runInContext("actionModal('accept')",context);await vm.runInContext('modalSave(uiForm)',context);
 vm.runInContext("actor='metric-owner';render();actionModal('accept')",context);await vm.runInContext('modalSave(uiForm)',context);
 assert.match(get('#app').innerHTML,/Draft learning proposal/);
 vm.runInContext("actionModal('propose')",context);context.uiForm=new Map([['reason','Preserve the outcome as a regression fixture'],['kind','regression_fixture']]);await vm.runInContext('modalSave(uiForm)',context);
 vm.runInContext("selected=null;view='learning';render()",context);assert.match(get('#app').innerHTML,/Preserve the outcome/);
 await vm.runInContext('load()',context);assert.match(get('#app').innerHTML,/Preserve the outcome/);
 const replay=await (await fetch(base+'/api/replay')).json();assert.equal(replay.verified,true);
 const packet=await (await fetch(base+'/api/export')).json();assert.equal(packet.state.contracts.at(-1).measurements[0].reviews.length,2);
 vm.runInContext("view='queue';filters.search='nothing matches';render()",context);assert.match(get('#queue-body').innerHTML,/No matching contracts/);
 assert.equal(errors.length,0);
 console.log(JSON.stringify({passed:true,test:'JavaScript controller + HTML render smoke (no browser)',workflow:'create → validate → arm → complete → advance → measure → dual review → proposal → reload → replay → export',views:4,seeded_receipts_rendered:9,escaping:true,events:replay.events,visual_layout:'unverified'}));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{child.kill();setTimeout(()=>{fs.rmSync(tmp,{recursive:true,force:true});},300);});
