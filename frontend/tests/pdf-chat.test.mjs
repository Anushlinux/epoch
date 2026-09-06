import test from 'node:test';
import assert from 'node:assert/strict';
import { ChatWorkspace, CHAT_PENDING_KEY } from '../src/chat-api.mjs';
import { environmentPicker, environmentView } from '../src/chat-environment.mjs';
import { repairView } from '../src/chat-repair.mjs';
const memory = () => { const values = new Map(); return { getItem:k=>values.get(k)??null, setItem:(k,v)=>values.set(k,v), removeItem:k=>values.delete(k) }; };
test('CSV pending writes retire without replay and PDF is offered in their place', () => {
 const storage=memory(); const p={version:1,kind:'repair',origin:'http://127.0.0.1:8000',chatId:crypto.randomUUID(),create:{client_request_id:crypto.randomUUID(),project_id:'demo'},message:{client_request_id:crypto.randomUUID(),content:'old repair'}};
 storage.setItem(CHAT_PENDING_KEY,JSON.stringify(p)); const w=new ChatWorkspace({storage});
 assert.equal(w.state.pending,null); assert.equal(storage.getItem(CHAT_PENDING_KEY),null); assert.ok(storage.getItem(CHAT_PENDING_KEY+'.retired'));
 assert.match(environmentPicker('pdf_workshop',false),/Documents/); assert.doesNotMatch(environmentPicker('pdf_workshop',false),/CSV/);
});
test('PDF actions retain the exact endpoint, source evidence and version across acknowledgement loss', async t => {
 const storage=memory(), id=crypto.randomUUID(), writes=[]; let lost=true;
 const chat={id,title:'PDF test',environment:'pdf_workshop',project_id:'demo',messages:[],operations:[]};
 const env={environment:'pdf_workshop',local:true,assets:[],tools:[],actions:[{action:'repair_tool',evidence_id:crypto.randomUUID(),expected_version:'builtin',eligible:true}],runtime:{available:true}};
 const api={health:async()=>({}),call:async(path,payload)=>{
  if(payload){writes.push({path,payload});if(lost){lost=false;throw new Error('Lost acknowledgement');}return {body:{id:crypto.randomUUID(),chat_id:id,client_request_id:payload.client_request_id,status:'completed'}};}
  if(path.startsWith('/api/chats?'))return {body:{items:[chat],total:1}};
  if(path.endsWith('/environment'))return {body:env};
  if(path==='/api/runtime')return {body:{execution_enabled:true,active_run_id:null}};
  return {body:chat};
 }};
 const w=new ChatWorkspace({storage,apiFactory:()=>api});w.state.selected=id;await w.connect();t.after(()=>w.stop());
 assert.equal(await w.environmentAction('repair_tool'),false);
 const p=JSON.parse(storage.getItem(CHAT_PENDING_KEY));assert.equal(p.version,2);assert.equal(p.endpoint,`/api/chats/${id}/environment-actions`);
 const restored=new ChatWorkspace({storage,apiFactory:()=>api});t.after(()=>restored.stop());await restored.connect();assert.equal(writes.length,1);
 assert.equal(await restored.retry(),true);assert.deepEqual(writes[0],writes[1]);
});
test('PDF views use actual asset URLs, host verdicts and explicit repair controls',()=>{
 const id=crypto.randomUUID(), asset=crypto.randomUUID();
 const state={origin:'http://127.0.0.1:8000',chat:{id,environment:'pdf_workshop',operations:[]},runtime:{debugger:{available:true}},environment:{active_version:'builtin',runtime:{available:true},tools:[],versions:{history:[]},actions:[{action:'repair_tool',eligible:true,reason:'Captured overflow',evidence_id:crypto.randomUUID()}],assets:[{id:asset,name:'broken.pdf',kind:'pdf',page_count:1,verification:{passed:false,checks:[{name:'within_page_bounds',passed:false}]}}]}};
 const html=environmentView({...state,previewAsset:asset,previewPage:1});
 assert.match(html,/Content checks failed/);assert.match(html,new RegExp(`/assets/${asset}/pages/1`));
 assert.match(repairView(state,false),/Fix PDF tool/);assert.doesNotMatch(repairView(state,false),/Repair published/);
 assert.match(repairView(state,false),/Ready to fix/);
 assert.match(repairView({...state,chat:{...state.chat,operations:[{status:'running',action:'repair_tool',activity:'Testing'}]}},true),/>Stop</);
});
