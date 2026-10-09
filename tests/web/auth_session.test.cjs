const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function harness(){
  const elements=new Map();
  function element(id){if(!elements.has(id))elements.set(id,{value:'',hidden:false,disabled:false,events:{},addEventListener(name,fn){this.events[name]=fn;},closest(){return {hidden:false};}});return elements.get(id);}
  const main={children:[],insertBefore(){}};const timers=[];const pending=[];const calls=[];
  const reply=data=>({ok:true,json:async()=>data});
  const config={enabled:true,supabase_url:'https://synthetic.supabase.co',publishable_key:'sb_publishable_synthetic',environment:'staging'};
  const context={document:{createElement(){return {};},querySelector(){return main;},getElementById:element,body:main},window:{dispatchEvent(){}},CustomEvent:function(){},location:{origin:'https://console.invalid'},URL,setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){},fetch(url){calls.push(url);if(url==='/v1/auth/config')return Promise.resolve(reply(config));if(url.includes('logout'))return Promise.resolve(reply({}));return new Promise(resolve=>pending.push(data=>resolve(reply(data))));}};
  vm.runInNewContext(fs.readFileSync('apps/web/auth-panel.js','utf8'),context);
  await new Promise(setImmediate);
  element('forge-email').value='synthetic'+String.fromCharCode(64)+'example.invalid';element('forge-password').value='synthetic-password';
  const submit=()=>element('forge-login').events.submit({preventDefault(){}});
  return {element,timers,pending,calls,submit};
}
const session=label=>({access_token:'synthetic-access-'+label,refresh_token:'synthetic-refresh-'+label,expires_in:120});

test('a delayed refresh cannot restore a logged-out session',async()=>{
  const h=await harness();const login=h.submit();h.pending.shift()(session('first'));await login;
  const refresh=h.timers[0]();
  await h.element('forge-signout').events.click();
  h.pending.shift()(session('refreshed'));await refresh;
  assert.equal(h.element('token').value,'');assert.equal(h.element('forge-signout').hidden,true);
  assert.ok(h.element('forge-auth-status').textContent.includes('Sudah keluar'));
});

test('duplicate submits do not create competing login requests',async()=>{
  const h=await harness();const first=h.submit();await h.submit();
  assert.equal(h.pending.length,1);h.pending.shift()(session('first'));await first;
  assert.equal(h.element('forge-password').value,'');
});

test('a cancelled login response cannot restore a cleared session',async()=>{
  const h=await harness();const login=h.submit();await h.element('forge-signout').events.click();
  h.pending.shift()(session('late'));await login;
  assert.equal(h.element('token').value,'');assert.equal(h.element('forge-signout').hidden,true);
});
