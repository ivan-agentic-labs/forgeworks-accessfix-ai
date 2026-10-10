from accessfix_ai.presentation.authentication import decode_bearer, verify_session
import os, jwt
from fastapi import Depends, Header, HTTPException
from typing import Annotated
from accessfix_ai.infrastructure.store import Store

def reject(status,code,detail): raise HTTPException(status_code=status,detail={"type":"about:blank","title":"Request rejected","status":status,"code":code,"detail":detail,"request_id":"runtime"})
def claims(authorization: Annotated[str | None, Header()] = None):
    return decode_bearer(authorization)


def role_scope_allowed(role: str, required_scope: str) -> bool:
    """JWT scope AND current membership role are both required.

    Viewer may only read. Unknown roles fail closed until explicitly reviewed.
    Editor/owner/admin retain granular server-provisioned JWT scope checks.
    """
    if role == "viewer":
        return required_scope.endswith(":read")
    return role in {"editor", "owner", "admin"}


def scope(required,store:Store):
 def dep(c=Depends(claims)):
  verify_session(store, c)
  if not c.get('tenant_id') or not c.get('sub'): reject(403,'TENANT_CONTEXT_INVALID','Verified membership is required')
  role = store.member_role(c['tenant_id'], c['sub'])
  if role is None: reject(403,'TENANT_CONTEXT_INVALID','Verified membership is required')
  if not role_scope_allowed(role, required): reject(403,'ROLE_FORBIDDEN','Membership role cannot perform this operation')
  if required not in set(str(c.get('scope','')).split()): reject(403,'INSUFFICIENT_SCOPE',f'Scope {required} is required')
  return c
 return dep

