from datetime import datetime,timedelta,timezone
import jwt,time
from fastapi.testclient import TestClient
from accessfix_ai.main import create_app
from accessfix_ai.infrastructure.store import TENANT,USER,SITE
SECRET='forgeworks-development-secret-32-plus'; ISS='https://issuer.synthetic.invalid'; AUD='forgeworks-api'
def tok(scope,tenant=TENANT): return jwt.encode({'sub':USER,'tenant_id':tenant,'scope':scope,'iss':ISS,'aud':AUD,'exp':datetime.now(timezone.utc)+timedelta(minutes=5)},SECRET,algorithm='HS256')
def hdr(scope): return {'Authorization':'Bearer '+tok(scope)}
def test_verify_scan_findings_and_review(tmp_path):
 app=create_app(str(tmp_path/'db.sqlite'),seed=True)
 with TestClient(app) as c:
  r=c.post('/v1/sites/verification-challenges',headers=hdr('site:verify'),json={'canonical_origin':'http://fixture.local','repository_id':'33333333-3333-3333-3333-333333333333'})
  assert r.status_code==201; challenge=r.json(); token=r.headers['X-Development-Challenge-Token']
  v=c.post(f"/v1/sites/{SITE}/verify",headers=hdr('site:verify'),json={'challenge_id':challenge['id'],'evidence_token':token}); assert v.status_code==200
  s=c.post(f"/v1/sites/{SITE}/scans",headers=hdr('scan:start'),json={'repo_commit_sha':'a'*40,'paths':['/']}); assert s.status_code==202; scan=s.json()
  for _ in range(30):
   f=c.get(f"/v1/scans/{scan['id']}/findings",headers=hdr('scan:read')).json()['items']
   if f: break
   time.sleep(.02)
  assert f[0]['rule_id']=='image-alt' and f[0]['manual_check_required'] is True
  p=c.post(f"/v1/findings/{f[0]['id']}/fix-proposals",headers=hdr('patch:create'),json={'source_mapping_id':f[0]['id']}); assert p.status_code==201
  proposal=p.json()
  retest=c.post(f"/v1/fix-proposals/{proposal['id']}/retests",headers=hdr('patch:create'),json={'repo_commit_sha':proposal['base_sha'],'expected_version':proposal['version']}); assert retest.status_code==202
  review=c.post(f"/v1/fix-proposals/{proposal['id']}/reviews",headers=hdr('patch:review'),json={'patch_sha256':proposal['patch_sha256'],'decision':'approve','manual_check_status':'passed','expected_version':retest.json()['version']}); assert review.status_code==201

def test_unverified_and_ssrf_fail_closed(tmp_path):
 app=create_app(str(tmp_path/'db.sqlite'),seed=True)
 with TestClient(app) as c:
  r=c.post('/v1/sites/verification-challenges',headers=hdr('site:verify'),json={'canonical_origin':'https://127.0.0.1','repository_id':'33333333-3333-3333-3333-333333333333'}); assert r.status_code==400
  r=c.post(f'/v1/sites/{SITE}/scans',headers=hdr('scan:start'),json={'repo_commit_sha':'a'*40,'paths':['/']}); assert r.status_code==403

def test_cross_tenant_and_scope_fail_closed(tmp_path):
 app=create_app(str(tmp_path/'db.sqlite'),seed=True)
 with TestClient(app) as c:
  r=c.post('/v1/sites/verification-challenges',headers=hdr('scan:start'),json={'canonical_origin':'http://fixture.local','repository_id':'33333333-3333-3333-3333-333333333333'}); assert r.status_code==403
  other=jwt.encode({'sub':USER,'tenant_id':'00000000-0000-0000-0000-000000000099','scope':'site:verify','iss':ISS,'aud':AUD,'exp':datetime.now(timezone.utc)+timedelta(minutes=5)},SECRET,algorithm='HS256')
  r=c.post('/v1/sites/verification-challenges',headers={'Authorization':'Bearer '+other},json={'canonical_origin':'http://fixture.local','repository_id':'33333333-3333-3333-3333-333333333333'}); assert r.status_code==403
