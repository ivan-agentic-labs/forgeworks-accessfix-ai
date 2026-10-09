from __future__ import annotations
import sqlite3, threading, uuid, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
TENANT="00000000-0000-0000-0000-000000000001"; USER="00000000-0000-0000-0000-000000000010"; SITE="22222222-2222-2222-2222-222222222222"
def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
class Store:
 def __init__(self,path):
  self.path=path; self.lock=threading.RLock(); Path(path).parent.mkdir(parents=True,exist_ok=True) if path!=':memory:' else None; self.init()
 def conn(self): c=sqlite3.connect(self.path,check_same_thread=False); c.row_factory=sqlite3.Row; return c
 def init(self):
  with self.conn() as c:
   c.executescript('''CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY,slug TEXT,status TEXT); CREATE TABLE IF NOT EXISTS memberships(tenant_id TEXT,user_id TEXT,role TEXT,status TEXT,PRIMARY KEY(tenant_id,user_id)); CREATE TABLE IF NOT EXISTS sites(tenant_id TEXT,id TEXT,origin TEXT,repo_id TEXT,status TEXT,verified_until TEXT,PRIMARY KEY(tenant_id,id)); CREATE TABLE IF NOT EXISTS challenges(tenant_id TEXT,id TEXT,site_id TEXT,token_hash TEXT,expires_at TEXT,used_at TEXT,PRIMARY KEY(tenant_id,id)); CREATE TABLE IF NOT EXISTS scans(tenant_id TEXT,id TEXT,site_id TEXT,commit_sha TEXT,policy_sha TEXT,status TEXT,created_at TEXT,job_id TEXT,PRIMARY KEY(tenant_id,id)); CREATE TABLE IF NOT EXISTS findings(tenant_id TEXT,id TEXT,scan_id TEXT,rule_id TEXT,severity TEXT,selector TEXT,fingerprint TEXT,manual_required INTEGER,PRIMARY KEY(tenant_id,id)); CREATE TABLE IF NOT EXISTS proposals(tenant_id TEXT,id TEXT,finding_id TEXT,base_sha TEXT,patch_sha TEXT,status TEXT,retest_status TEXT,version INTEGER,PRIMARY KEY(tenant_id,id)); CREATE TABLE IF NOT EXISTS reviews(tenant_id TEXT,id TEXT,proposal_id TEXT,reviewer_id TEXT,decision TEXT,manual_status TEXT,version INTEGER,PRIMARY KEY(tenant_id,id));''')
 def seed(self):
  with self.conn() as c:
   c.execute('INSERT OR IGNORE INTO tenants VALUES(?,?,?)',(TENANT,'synthetic-demo','ACTIVE')); c.execute('INSERT OR IGNORE INTO memberships VALUES(?,?,?,?)',(TENANT,USER,'editor','ACTIVE')); c.execute('INSERT OR IGNORE INTO sites VALUES(?,?,?,?,?,?)',(TENANT,SITE,'http://fixture.local','synthetic-repo','UNVERIFIED',None))
 def member(self,t,u):
  with self.conn() as c:return c.execute("SELECT 1 FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'",(t,u)).fetchone() is not None
 def site(self,t,s):
  with self.conn() as c:return c.execute('SELECT * FROM sites WHERE tenant_id=? AND id=?',(t,s)).fetchone()
 def challenge(self,t,s,token,exp):
  cid=str(uuid.uuid4());
  with self.conn() as c:c.execute('INSERT INTO challenges VALUES(?,?,?,?,?,NULL)',(t,cid,s,hashlib.sha256(token.encode()).hexdigest(),exp))
  return cid
 def get_challenge(self,t,cid):
  with self.conn() as c:return c.execute('SELECT * FROM challenges WHERE tenant_id=? AND id=?',(t,cid)).fetchone()
 def verify(self,t,cid):
  with self.conn() as c:
   row=c.execute('SELECT * FROM challenges WHERE tenant_id=? AND id=?',(t,cid)).fetchone(); c.execute('UPDATE challenges SET used_at=? WHERE tenant_id=? AND id=?',(now(),t,cid)); c.execute("UPDATE sites SET status='VERIFIED',verified_until=? WHERE tenant_id=? AND id=?",(datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year+1).isoformat().replace('+00:00','Z'),t,row['site_id'])); return c.execute('SELECT * FROM sites WHERE tenant_id=? AND id=?',(t,row['site_id'])).fetchone()
 def scan(self,t,site,sha,policy):
  sid,jid=str(uuid.uuid4()),str(uuid.uuid4());
  with self.conn() as c:c.execute('INSERT INTO scans VALUES(?,?,?,?,?,?,?,?)',(t,sid,site,sha,policy,'PENDING',now(),jid))
  return self.get_scan(t,sid)
 def get_scan(self,t,sid):
  with self.conn() as c:return c.execute('SELECT * FROM scans WHERE tenant_id=? AND id=?',(t,sid)).fetchone()
 def finish_scan(self,t,sid):
  fid=str(uuid.uuid4()); fp=hashlib.sha256(b'fixture.local:/main:img-alt').hexdigest()
  with self.conn() as c:
   c.execute('INSERT INTO findings VALUES(?,?,?,?,?,?,?,?)',(t,fid,sid,'image-alt','SERIOUS','img#hero',fp,1)); c.execute("UPDATE scans SET status='SUCCEEDED' WHERE tenant_id=? AND id=?",(t,sid))
 def findings(self,t,sid):
  with self.conn() as c:return c.execute('SELECT * FROM findings WHERE tenant_id=? AND scan_id=?',(t,sid)).fetchall()
 def finding(self,t,fid):
  with self.conn() as c:return c.execute('SELECT * FROM findings WHERE tenant_id=? AND id=?',(t,fid)).fetchone()
 def proposal(self,t,fid,sha,patch):
  pid=str(uuid.uuid4());
  with self.conn() as c:c.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?)',(t,pid,fid,sha,patch,'PENDING_RETEST','NOT_RUN',1))
  return self.proposal_get(t,pid)
 def proposal_get(self,t,pid):
  with self.conn() as c:return c.execute('SELECT * FROM proposals WHERE tenant_id=? AND id=?',(t,pid)).fetchone()
 def review(self,t,pid,reviewer,patch,decision,manual,version):
  row=self.proposal_get(t,pid)
  if not row:return None,'NOT_FOUND'
  if row['version']!=version:return row,'STALE'
  if row['patch_sha']!=patch:return row,'DIGEST_MISMATCH'
  rid=str(uuid.uuid4()); status='APPROVED' if decision=='approve' and manual=='passed' else 'REJECTED'
  with self.conn() as c:c.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?)',(t,rid,pid,reviewer,decision,manual,version)); c.execute('UPDATE proposals SET status=? WHERE tenant_id=? AND id=?',(status,t,pid))
  return (rid,status),'OK'
