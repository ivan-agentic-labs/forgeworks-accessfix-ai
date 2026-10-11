import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from accessfix_ai.infrastructure.store import TENANT, USER
from accessfix_ai.main import Retest, Review, create_app

PROPOSAL = '33333333-3333-3333-3333-333333333333'


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    app = create_app(str(tmp_path_factory.mktemp('version') / 'db.sqlite'), seed=True)
    with TestClient(app, raise_server_exceptions=False) as value:
        yield value


def headers(scope):
    token = jwt.encode({'sub': USER, 'tenant_id': TENANT, 'scope': scope,
                        'iss': 'https://issuer.synthetic.invalid', 'aud': 'forgeworks-api',
                        'exp': datetime.now(timezone.utc) + timedelta(minutes=5)},
                       'forgeworks-development-secret-32-plus', algorithm='HS256')
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


@pytest.mark.parametrize('action', ['retests', 'reviews'])
@pytest.mark.parametrize('version', [True, '1', 1.0, 1.5, float('inf'), 0])
def test_invalid_version_is_rejected_before_store(client, monkeypatch, action, version):
    body = {'repo_commit_sha': 'a' * 40} if action == 'retests' else {
        'patch_sha256': 'a' * 64, 'decision': 'approve', 'manual_check_status': 'passed'}
    body['expected_version'] = version
    method = 'retest' if action == 'retests' else 'review'
    called = []
    original = getattr(client.app.state.store, method)
    def tracked(*args, **kwargs):
        called.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(client.app.state.store, method, tracked)
    response = client.post(f'/v1/fix-proposals/{PROPOSAL}/{action}',
                           headers=headers('patch:create' if action == 'retests' else 'patch:review'),
                           content=json.dumps(body).replace('Infinity', '1e400'))
    assert response.status_code == 422
    assert response.json()['code'] == 'INVALID_REQUEST'
    assert not called
    assert 'input' not in response.json()


@pytest.mark.parametrize('version', [1, 2, 2147483647])
def test_integer_versions_remain_accepted(version):
    assert Retest(repo_commit_sha='a' * 40, expected_version=version).expected_version == version
    assert Review(patch_sha256='a' * 64, decision='approve', manual_check_status='passed', expected_version=version).expected_version == version
