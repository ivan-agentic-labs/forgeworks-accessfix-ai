#!/usr/bin/env python3
"""G1 offline contract sanity checker. Not independent semantic OAS certification."""
from pathlib import Path
import json,re,sys
import yaml
from jsonschema import Draft202012Validator
root=Path(__file__).resolve().parents[1]
spec=yaml.safe_load((root/'contracts/openapi.yaml').read_text(encoding='utf-8'))
events=json.loads((root/'contracts/events.schema.json').read_text(encoding='utf-8'))
errors=[]
if not str(spec.get('openapi','')).startswith('3.1.'):
    errors.append('expected OpenAPI 3.1.x')
if not spec.get('info') or not isinstance(spec.get('paths'),dict):
    errors.append('missing info or paths')
try:
    Draft202012Validator.check_schema(events)
except Exception as exc:
    errors.append(f'event schema invalid: {exc}')
ids=set(); count=0
for path,item in spec.get('paths',{}).items():
    for method,op in item.items():
        if method.lower() not in {'get','post','put','patch','delete','head','options','trace'}:
            continue
        count+=1
        oid=op.get('operationId')
        if not oid or oid in ids: errors.append(f'{method.upper()} {path}: missing/duplicate operationId {oid}')
        ids.add(oid)
        if not op.get('security'): errors.append(f'{oid}: no operation security')
        if not op.get('x-required-scope'): errors.append(f'{oid}: no scoped auth declaration')
        declared=set(re.findall(r'\{([^{}]+)\}',path))
        params={p.get('name') for p in op.get('parameters',[])+item.get('parameters',[]) if p.get('in')=='path'}
        if declared != params: errors.append(f'{oid}: path parameter mismatch {declared} vs {params}')
components=spec.get('components',{}).get('schemas',{})
def refs(data):
    if isinstance(data,dict):
        for k,v in data.items():
            if k=='$ref' and isinstance(v,str) and v.startswith('#/components/schemas/'):
                n=v.rsplit('/',1)[-1].replace('~1','/').replace('~0','~')
                if n not in components: errors.append(f'unknown schema ref {v}')
            else: refs(v)
    elif isinstance(data,list):
        for v in data: refs(v)
refs(spec)
print(json.dumps({'checks':'G1 static contract sanity only','operations':count,'event_schema':'draft2020-12','errors':errors},indent=2))
if errors: sys.exit(1)
