from __future__ import annotations
import os, threading, time, hashlib, secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
from typing import Annotated
from fastapi import FastAPI, Depends, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from accessfix_ai.infrastructure.store import Store, TENANT, USER, SITE
from accessfix_ai.domain.target_policy import validate_origin, validate_scan_path
from accessfix_ai.presentation.auth import scope
ROOT=Path(__file__).resolve().parents[4]
class Challenge(BaseModel):
 model_config=ConfigDict(extra='forbid'); canonical_origin:str; repository_id:UUID
class Verify(BaseModel):
 model_config=ConfigDict(extra='forbid'); challenge_id:UUID; evidence_token:str
class StartScan(BaseModel):
 model_config=ConfigDict(extra='forbid'); repo_commit_sha:str=Field(pattern=r'^[0-9a-fA-F]{40,64}$'); paths:list[str]
class CreateFix(BaseModel):
 model_config=ConfigDict(extra='forbid'); source_mapping_id:UUID
class Review(BaseModel):
 model_config=ConfigDict(extra='forbid'); patch_sha256:str=Field(pattern=r'^[0-9a-f]{64}$'); decision:str; manual_check_status:str; expected_version:int=Field(ge=1)
class Publish(BaseModel):
 model_config=ConfigDict(extra='forbid'); review_id:UUID

def problem(status,code,detail): return JSONResponse(status_code=status,content={'type':'about:blank','title':'Request rejected','status':status,'code':code,'detail':detail,'request_id':'runtime'})
def create_app(db_path=None,seed=False):
 store=Store(db_path or os.getenv('ACCESSFIX_DB_PATH',str(ROOT/'.runtime/accessfix.db')))
 if seed: store.seed()
 stop=threading.Event()
 def worker():
  while not stop.is_set():
   with store.conn() as c: pending=c.execute("SELECT * FROM scans WHERE status='PENDING'").fetchall()
   for row in pending: store.finish_scan(row['tenant_id'],row['id'])
   stop.wait(.05)
 @asynccontextmanager
 async def lifespan(app):
  t=threading.Thread(target=worker,daemon=True,name='accessfix-worker'); t.start(); yield; stop.set(); t.join(1)
 app=FastAPI(title='AccessFix AI MVP',version='0.1.0',lifespan=lifespan); app.state.store=store
 @app.exception_handler(HTTPException)
 async def err(_,e): return JSONResponse(status_code=e.status_code,content=e.detail if isinstance(e.detail,dict) else {'type':'about:blank','title':'Request rejected','status':e.status_code,'code':'REQUEST_REJECTED','detail':str(e.detail),'request_id':'runtime'})
 @app.get('/healthz')
 def health(): return {'status':'ok','service':'accessfix-ai'}
 @app.post('/v1/sites/verification-challenges',status_code=201)
 def challenge(body:Challenge,response:Response,c=Depends(scope('site:verify',store))):
  try: origin=validate_origin(body.canonical_origin)
  except ValueError as e:return problem(400,'TARGET_NOT_ALLOWED',str(e))
  token=secrets.token_urlsafe(24); expires=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat().replace('+00:00','Z')
  with store.conn() as db: db.execute('INSERT OR IGNORE INTO sites VALUES(?,?,?,?,?,?)',(c['tenant_id'],SITE,origin,str(body.repository_id),'UNVERIFIED',None))
  cid=store.challenge(c['tenant_id'],SITE,token,expires); response.headers['X-Development-Challenge-Token']=token
  return {'id':cid,'status':'PENDING','created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'site_id':SITE,'canonical_origin':origin,'verification_method':'DEVELOPMENT_HEADER_TOKEN','expires_at':expires}
 @app.post('/v1/sites/{site_id}/verify')
 def verify(site_id:UUID,body:Verify,c=Depends(scope('site:verify',store))):
  row=store.get_challenge(c['tenant_id'],str(body.challenge_id))
  if not row or row['site_id']!=str(site_id) or row['used_at'] or row['expires_at']<datetime.now(timezone.utc).isoformat().replace('+00:00','Z') or hashlib.sha256(body.evidence_token.encode()).hexdigest()!=row['token_hash']: return problem(400,'VERIFICATION_FAILED','Challenge is invalid, expired, or already used')
  site=store.verify(c['tenant_id'],str(body.challenge_id)); proof=hashlib.sha256((site['origin']+body.evidence_token).encode()).hexdigest()
  return {'id':str(body.challenge_id),'status':'VERIFIED','created_at':row['expires_at'],'site_id':site['id'],'verified_until':site['verified_until'],'proof_digest':proof}
 @app.post('/v1/sites/{site_id}/scans',status_code=202)
 def scan(site_id:UUID,body:StartScan,c=Depends(scope('scan:start',store))):
  site=store.site(c['tenant_id'],str(site_id))
  if not site or site['status']!='VERIFIED': return problem(403,'OWNERSHIP_REQUIRED','Site ownership must be verified before scanning')
  try:
   for p in body.paths: validate_scan_path(p,site['origin'])
  except ValueError as e:return problem(400,'TARGET_NOT_ALLOWED',str(e))
  policy=hashlib.sha256((site['origin']+'|same-origin|no-private-egress').encode()).hexdigest(); row=store.scan(c['tenant_id'],str(site_id),body.repo_commit_sha,policy)
  return {'id':row['id'],'status':row['status'],'created_at':row['created_at'],'site_id':row['site_id'],'repo_commit_sha':row['commit_sha'],'network_policy_sha256':row['policy_sha'],'job_id':row['job_id']}
 @app.get('/v1/scans/{scan_id}/findings')
 def findings(scan_id:UUID,c=Depends(scope('scan:read',store))):
  if not store.get_scan(c['tenant_id'],str(scan_id)): return problem(404,'RESOURCE_NOT_FOUND','Scan is not visible')
  items=[{'id':f['id'],'scan_id':f['scan_id'],'rule_id':f['rule_id'],'severity':f['severity'],'selector':f['selector'],'fingerprint':f['fingerprint'],'manual_check_required':bool(f['manual_required'])} for f in store.findings(c['tenant_id'],str(scan_id))]
  return {'items':items,'next_cursor':None,'has_more':False}
 @app.post('/v1/findings/{finding_id}/fix-proposals',status_code=201)
 def fix(finding_id:UUID,body:CreateFix,c=Depends(scope('patch:create',store))):
  f=store.finding(c['tenant_id'],str(finding_id))
  if not f or str(body.source_mapping_id)!=str(finding_id): return problem(409,'SOURCE_MAPPING_UNAVAILABLE','Finding has no verified source mapping')
  patch=hashlib.sha256((f['selector']+'|add alt text|'+f['fingerprint']).encode()).hexdigest(); row=store.proposal(c['tenant_id'],str(finding_id),'a'*40,patch)
  return {'id':row['id'],'status':row['status'],'created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'finding_id':row['finding_id'],'base_sha':row['base_sha'],'patch_sha256':row['patch_sha'],'retest_status':row['retest_status'],'version':row['version']}
 @app.post('/v1/fix-proposals/{proposal_id}/reviews',status_code=201)
 def review(proposal_id:UUID,body:Review,c=Depends(scope('patch:review',store))):
  if body.decision not in {'approve','reject'} or body.manual_check_status not in {'passed','failed','not_applicable'}: return problem(400,'INVALID_REVIEW','Review decision or manual status is invalid')
  result,status=store.review(c['tenant_id'],str(proposal_id),c['sub'],body.patch_sha256,body.decision,body.manual_check_status,body.expected_version)
  if status=='NOT_FOUND': return problem(404,'RESOURCE_NOT_FOUND','Proposal is not visible')
  if status=='STALE': return problem(409,'STALE_VERSION','Proposal version is stale')
  if status=='DIGEST_MISMATCH': return problem(409,'DIGEST_MISMATCH','Patch digest is not the reviewed proposal')
  rid,decision=result; return {'id':rid,'status':decision,'created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'proposal_id':str(proposal_id),'reviewer_id':c['sub'],'decision':body.decision,'manual_check_status':body.manual_check_status}
 @app.post('/v1/fix-proposals/{proposal_id}/pull-requests')
 def publish(proposal_id:UUID,body:Publish,c=Depends(scope('github:write',store))): return problem(503,'LIVE_INTEGRATION_BLOCKED','GitHub write integration is disabled until permission and sandbox evidence are verified')
 @app.get('/v1/jobs/{job_id}')
 def job(job_id:UUID,c=Depends(scope('job:read',store))):
  with store.conn() as db: row=db.execute('SELECT * FROM scans WHERE tenant_id=? AND job_id=?',(c['tenant_id'],str(job_id))).fetchone()
  if not row:return problem(404,'RESOURCE_NOT_FOUND','Job is not visible')
  return {'id':row['job_id'],'kind':'accessibility_scan','state':row['status'],'created_at':row['created_at'],'state_version':1,'attempt_count':1,'last_error_code':None}
 return app
app=create_app(seed=os.getenv('ACCESSFIX_SEED_FIXTURE','0')=='1')
