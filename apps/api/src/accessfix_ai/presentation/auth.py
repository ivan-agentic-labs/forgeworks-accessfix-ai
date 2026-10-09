import os, jwt
from fastapi import Depends, Header, HTTPException
from typing import Annotated
from accessfix_ai.infrastructure.store import Store

def reject(status,code,detail): raise HTTPException(status_code=status,detail={"type":"about:blank","title":"Request rejected","status":status,"code":code,"detail":detail,"request_id":"runtime"})
def claims(authorization: Annotated[str|None,Header()]=None):
 if not authorization or not authorization.startswith('Bearer '): reject(401,'UNAUTHENTICATED','Bearer token is required')
 secret=os.getenv('DEV_AUTH_SECRET','forgeworks-development-secret-32-plus')
 if os.getenv('APP_ENV','development')=='production' and secret=='forgeworks-development-secret-32-plus': reject(500,'AUTH_NOT_CONFIGURED','Production issuer secret is not configured')
 try:return jwt.decode(authorization[7:],secret,algorithms=['HS256'],issuer=os.getenv('AUTH_ISSUER','https://issuer.synthetic.invalid'),audience=os.getenv('AUTH_AUDIENCE','forgeworks-api'))
 except jwt.PyJWTError: reject(401,'INVALID_TOKEN','Token signature, issuer, audience, or expiry is invalid')
def scope(required,store:Store):
 def dep(c=Depends(claims)):
  if not c.get('tenant_id') or not c.get('sub') or not store.member(c['tenant_id'],c['sub']): reject(403,'TENANT_CONTEXT_INVALID','Verified membership is required')
  if required not in set(str(c.get('scope','')).split()): reject(403,'INSUFFICIENT_SCOPE',f'Scope {required} is required')
  return c
 return dep
