from pathlib import Path
import jsonschema,pytest,yaml
from fastapi.testclient import TestClient
from accessfix_ai.main import create_app
from accessfix_ai.infrastructure.store import TENANT,SITE
from test_accessfix_flow import hdr


@pytest.mark.parametrize('internal_state',['FAILED','TIMED_OUT'])
def test_terminal_worker_states_match_public_job_contract(tmp_path,internal_state):
    app=create_app(str(tmp_path/'db.sqlite'),seed=True)
    row=app.state.store.scan(TENANT,SITE,'a'*40,'b'*64)
    with app.state.store.conn() as db:db.execute('UPDATE scans SET status=? WHERE id=?',(internal_state,row['id']))
    with TestClient(app) as client:
        result=client.get(f"/v1/jobs/{row['job_id']}",headers=hdr('job:read'))
        assert result.status_code==200
        contract=yaml.safe_load((Path(__file__).resolve().parents[2]/'contracts/openapi.yaml').read_text())
        jsonschema.Draft202012Validator({**contract,'$ref':'#/components/schemas/JobStatus'}).validate(result.json())
        assert result.json()['state']=='FAILED_TERMINAL'
