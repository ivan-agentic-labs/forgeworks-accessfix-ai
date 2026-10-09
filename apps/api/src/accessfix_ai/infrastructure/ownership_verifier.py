"""Fetch bounded ownership evidence over TLS to a checked, pinned public IP."""
import hmac
import http.client
import socket
import ssl
from urllib.parse import urlsplit
from accessfix_ai.domain.target_policy import validate_origin, _checked_answers, _resolve

PROOF_PATH="/.well-known/forgeworks-site-verification.txt"


def fetch_proof(origin):
    origin=validate_origin(origin,allow_fixture=False)
    parsed=urlsplit(origin)
    if parsed.port not in (None,443):raise ValueError("Only HTTPS port 443 is supported")
    host=parsed.hostname
    addresses=_checked_answers(host,_resolve)
    context=ssl.create_default_context()
    connection=http.client.HTTPSConnection(host,443,context=context,timeout=5)
    def connect():
        raw=socket.create_connection((addresses[0],443),timeout=5)
        try:connection.sock=context.wrap_socket(raw,server_hostname=host)
        except Exception:raw.close();raise
    connection.connect=connect
    try:
        connection.request("GET",PROOF_PATH,headers={"Host":host,"Accept":"text/plain","Accept-Encoding":"identity","User-Agent":"ForgeWorks-OwnershipVerifier/1.0"})
        response=connection.getresponse()
        if response.status!=200 or response.getheader("Content-Encoding","identity")!="identity":raise ValueError("Proof must return HTTP 200 without redirects or compression")
        body=response.read(4097)
        if len(body)>4096:raise ValueError("Ownership proof exceeds 4 KiB")
        return body.decode("utf-8").strip()
    finally:connection.close()


def verify_ownership(origin,token):
    try:return hmac.compare_digest(fetch_proof(origin),token)
    except (ValueError,UnicodeError,OSError,http.client.HTTPException):return False
