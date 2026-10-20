"""Dedicated authenticated assistance routes inside the native dashboard process."""
import grp
import hmac
import html
import logging
import re
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import store as links

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
audit = logging.getLogger("arcenal.assistance")


def identity(request, admin=False):
    expected = links.configuration().get("proxy_key", "")
    supplied = request.headers.get("x-arcenal-proxy", "")
    user = request.headers.get("remote-user", "")
    if not expected or not hmac.compare_digest(supplied, expected) or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,128}", user):
        raise HTTPException(401, "Session SSO YunoHost requise.")
    if admin:
        try:
            members = grp.getgrnam("admins").gr_mem
        except KeyError:
            raise HTTPException(503, "Annuaire indisponible.") from None
        if user not in members:
            raise HTTPException(403, "Validation réservée aux administrateurs YunoHost.")
    return user


def page(content):
    return HTMLResponse('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<title>Assistance · ARCenal Agent</title><style>body{font:1.1rem system-ui;background:#f8f6f0;color:#20352b;'
        'max-width:46rem;margin:4rem auto;padding:1rem}button,a{padding:.8rem}:focus-visible{outline:3px solid #a3482c;outline-offset:4px}</style>'
        '<main><h1>ARCenal Agent</h1>' + content + '</main></html>', headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})


@app.post("/assistance/service")
async def service(request: Request):
    if len(await request.body()) > 4096:
        raise HTTPException(413, "Demande trop longue.")
    try:
        payload = await request.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("application"), str):
            raise links.LinkError
        application = payload["application"]
        entry = links.authenticate(application, request.headers.get("authorization", ""))
        result = links.exchange(application, entry, payload)
        audit.info("assistance.%s", payload["operation"])
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
    except (ValueError, TypeError):
        raise HTTPException(403, "Liaison absente, invalide ou non autorisée.") from None


@app.get("/assistance/")
def landing(request: Request, pair: str = "", reference: str = ""):
    user = identity(request, admin=bool(pair))
    if (len(request.query_params) != 1 or len(pair or reference) != 43
            or len(request.query_params.getlist("pair" if pair else "reference")) != 1):
        raise HTTPException(403, "Référence invalide.")
    try:
        if pair and not reference:
            nonce = links.prepare_confirmation(pair, user)
            return page('<h2>Lier ARCenal Matos</h2><p>Assistance en lecture seule. Aucun accès aux fiches ni aucune action métier.</p>'
                f'<form method="post"><input type="hidden" name="pair" value="{html.escape(pair, quote=True)}">'
                f'<input type="hidden" name="nonce" value="{nonce}">'
                '<button name="decision" value="approve">Valider la liaison</button><button name="decision" value="revoke">Révoquer la liaison</button></form>')
        if reference and not pair:
            context = links.receive(reference, user)
            audit.info("assistance.received")
            return page(f'<h2>Assistance Matos · {links.MODULES[context["resource_id"]]}</h2>'
                '<p>Votre session et vos droits ont été vérifiés. La liaison est en lecture seule.</p>'
                '<p>Les demandes et validations se font dans Matos. Aucune fiche ni document n’a été transmis. Cet accueil ne lance pas de conversation IA.</p>')
        raise links.LinkError
    except links.LinkError:
        raise HTTPException(403, "Demande absente, expirée ou non autorisée.") from None
    except (OSError, ValueError, TypeError):
        raise HTTPException(503, "Matos est momentanément indisponible.") from None


@app.post("/assistance/")
async def decide(request: Request):
    user = identity(request, admin=True)
    body = await request.body()
    if len(body) > 1024:
        raise HTTPException(413, "Demande trop longue.")
    try:
        values = parse_qs(body.decode(), strict_parsing=True)
        if set(values) != {"pair", "nonce", "decision"} or any(len(value) != 1 for value in values.values()):
            raise ValueError
        links.confirm(values["pair"][0], user, values["nonce"][0], values["decision"][0])
        audit.info("assistance.confirmed")
    except (ValueError, UnicodeError):
        raise HTTPException(403, "Confirmation absente, expirée ou déjà utilisée.") from None
    return page('<h2>Choix enregistré</h2><p>Revenez dans Matos et cliquez sur « Vérifier la liaison ».</p>')


class AssistanceMiddleware:
    """Bypass native dashboard authentication only for this self-authenticated app."""
    def __init__(self, app):
        self.native = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/assistance/"):
            await app(scope, receive, send)
        else:
            await self.native(scope, receive, send)


def install(native):
    logging.getLogger("uvicorn.access").addFilter(AccessFilter())
    native.add_middleware(AssistanceMiddleware)


class AccessFilter(logging.Filter):
    def filter(self, record):
        args = record.args
        return not (isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str) and args[2].startswith("/assistance/"))
