"""Remote proof, private-network denial and pinned TLS connection tests."""
import pytest
from fastapi.testclient import TestClient
from accessfix_ai.main import create_app
from accessfix_ai.presentation.auth import claims
from accessfix_ai.infrastructure.store import TENANT, USER, SITE
from accessfix_ai.infrastructure import ownership_verifier as verifier


def test_caller_token_alone_is_not_ownership(tmp_path,monkeypatch):
    app=create_app(str(tmp_path/'ownership.db'),seed=True)
    app.dependency_overrides[claims]=lambda:{"tenant_id":TENANT,"sub":USER,"scope":"site:verify"}
    monkeypatch.setenv('APP_ENV','staging');monkeypatch.setenv('OWNERSHIP_VERIFY_MODE','http-file')
    with TestClient(app) as client:
        response=client.post('/v1/sites/verification-challenges',json={"canonical_origin":"https://owner.example.invalid","repository_id":"33333333-3333-3333-3333-333333333333"})
        assert response.status_code==201,response.text
        assert 'X-Development-Challenge-Token' not in response.headers
        value=response.json();proof=value['verification_token']
        body={"challenge_id":value['id'],"evidence_token":proof}
        monkeypatch.setattr(verifier,'fetch_proof',lambda _: 'not-the-proof')
        denied=client.post(f'/v1/sites/{SITE}/verify',json=body)
        assert denied.status_code==400 and denied.json()['code']=='OWNERSHIP_PROOF_UNAVAILABLE'
        monkeypatch.setattr(verifier,'fetch_proof',lambda _: proof)
        assert client.post(f'/v1/sites/{SITE}/verify',json=body).status_code==200
        assert client.post(f'/v1/sites/{SITE}/verify',json=body).status_code==400


@pytest.mark.parametrize('origin',['http://fixture.local','https://127.0.0.1','https://localhost','https://169.254.169.254','https://owner.invalid:8443'])
def test_unsafe_target_rejected(origin):
    assert verifier.verify_ownership(origin,'synthetic-proof') is False


def test_private_dns_never_connects(monkeypatch):
    monkeypatch.setattr(verifier,'_resolve',lambda _:['127.0.0.1'])
    monkeypatch.setattr(verifier.socket,'create_connection',lambda *a,**k:pytest.fail('Private egress attempted'))
    assert verifier.verify_ownership('https://owner.invalid','synthetic-proof') is False


def test_public_ip_pinned_with_original_tls_host(monkeypatch):
    seen={};raw=object()
    monkeypatch.setattr(verifier,'_resolve',lambda _:['93.184.216.34'])
    def connect(address,timeout):seen['address']=address;return raw
    monkeypatch.setattr(verifier.socket,'create_connection',connect)
    class Context:
        def wrap_socket(self,socket,server_hostname):seen['tls_host']=server_hostname;assert socket is raw;return raw
    monkeypatch.setattr(verifier.ssl,'create_default_context',lambda:Context())
    class Response:
        status=200
        def getheader(self,*args):return 'identity'
        def read(self,size):assert size==4097;return b'actual-proof\n'
    class Connection:
        def __init__(self,*args,**kwargs):pass
        def request(self,method,path,headers):self.connect();seen['path']=path;seen['host']=headers['Host']
        def getresponse(self):return Response()
        def close(self):seen['closed']=True
    monkeypatch.setattr(verifier.http.client,'HTTPSConnection',Connection)
    assert verifier.verify_ownership('https://owner.invalid','actual-proof') is True
    assert seen['address']==('93.184.216.34',443) and seen['tls_host']==seen['host']=='owner.invalid'
    assert seen['path']==verifier.PROOF_PATH and seen['closed']
