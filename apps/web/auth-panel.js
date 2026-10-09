(() => {
  'use strict';
  const panel=document.createElement('section');panel.className='panel card forge-session';
  panel.innerHTML='<h2>Masuk ke ForgeWorks</h2><p>Sesi hanya disimpan di halaman ini.</p><form id="forge-login"><label>Email<input id="forge-email" type="email" autocomplete="username" required></label><label>Kata sandi<input id="forge-password" type="password" autocomplete="current-password" required></label><button id="forge-signin" type="submit" disabled>Masuk</button><button id="forge-signout" type="button" hidden>Keluar</button></form><p id="forge-auth-status" role="status" aria-live="polite">Memeriksa konfigurasi login…</p>';
  const main=document.querySelector('main')||document.body;main.insertBefore(panel,main.children[1]||null);
  const $=id=>document.getElementById(id);let config=null,session=null,timer=null,epoch=0;
  const tokenFields=()=>['token','bearer-token'].map($).filter(Boolean);
  const baseFields=()=>['api-base','api-base-url','baseUrl'].map($).filter(Boolean);
  const status=text=>{$('forge-auth-status').textContent=text;};
  function clearSession(){epoch+=1;session=null;delete window.forgeUploadedArtifact;clearTimeout(timer);tokenFields().forEach(input=>{input.value='';});$('forge-signout').hidden=true;$('forge-signin').disabled=!config;window.dispatchEvent(new CustomEvent('forge-session-cleared'));}
  function applySession(next){
    session=next;tokenFields().forEach(input=>{input.value=next.access_token;input.readOnly=true;});
    baseFields().forEach(input=>{input.value=location.origin;input.readOnly=true;});
    $('forge-signout').hidden=false;$('forge-signin').disabled=true;$('forge-password').value='';
    status('Sudah masuk. Akses aplikasi mengikuti izin tenant akun Anda.');
    clearTimeout(timer);timer=setTimeout(refresh,Math.max(10000,(next.expires_in||3600)*1000-60000));
    window.dispatchEvent(new CustomEvent('forge-session-ready'));
  }
  async function authRequest(path,body,bearer){
    const response=await fetch(config.supabase_url+'/auth/v1/'+path,{method:'POST',headers:{'apikey':config.publishable_key,'Content-Type':'application/json',...(bearer?{'Authorization':'Bearer '+bearer}:{})},body:JSON.stringify(body),cache:'no-store',credentials:'omit'});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.msg||data.error_description||'Permintaan login gagal ('+response.status+').');
    return data;
  }
  async function refresh(){const current=session,version=epoch;if(!current)return;try{const next=await authRequest('token?grant_type=refresh_token',{refresh_token:current.refresh_token});if(epoch===version&&session===current)applySession(next);}catch{if(epoch===version&&session===current){clearSession();status('Sesi berakhir. Silakan masuk kembali.');}}}
  $('forge-login').addEventListener('submit',async event=>{event.preventDefault();if(!config||$('forge-signin').disabled)return;const version=epoch;$('forge-signin').disabled=true;try{const next=await authRequest('token?grant_type=password',{email:$('forge-email').value.trim(),password:$('forge-password').value});if(epoch===version)applySession(next);}catch(error){if(epoch===version){$('forge-password').value='';$('forge-signin').disabled=false;status(error.message);}}});
  $('forge-signout').addEventListener('click',async()=>{const current=session;clearSession();if(!current)return;try{await authRequest('logout?scope=global',{},current.access_token);status('Sudah keluar. Sesi akun dicabut di server.');}catch{status('Sesi halaman ditutup. Logout server belum dapat dikonfirmasi.');}});
  fetch('/v1/auth/config',{cache:'no-store'}).then(response=>response.ok?response.json():null).then(value=>{
    if(!value||!value.enabled){status('Login Supabase belum dikonfigurasi untuk lingkungan ini.');return;}
    const url=new URL(value.supabase_url);if(url.protocol!=='https:'||!url.hostname.endsWith('.supabase.co')||url.username||url.password||url.search||url.hash||!['','/'].includes(url.pathname))throw new Error('Konfigurasi login tidak valid.');
    config=value;window.forgeAuthConfig=value;window.dispatchEvent(new CustomEvent('forge-auth-configured',{detail:value}));$('forge-signin').disabled=false;status('Masuk dengan akun yang memiliki membership ForgeWorks.');
    if(value.environment!=='development'&&value.environment!=='test'){
      baseFields().forEach(input=>{input.value=location.origin;input.readOnly=true;});
      tokenFields().forEach(input=>{input.readOnly=true;const label=input.closest('label');if(label)label.hidden=true;});
      const synthetic=$('csvContent');if(synthetic&&synthetic.closest('label'))synthetic.closest('label').hidden=true;
    }
  }).catch(()=>status('Konfigurasi login belum dapat dimuat. Muat ulang halaman untuk mencoba lagi.'));
})();
