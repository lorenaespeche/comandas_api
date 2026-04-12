from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import re

class IPAccessMiddleware(BaseHTTPMiddleware):
    """
    Middleware para bloquear acesso externo baseado em CORS_ORIGINS.
    Extrai IPs e domínios permitidos da configuração CORS_ORIGINS e bloqueia
    qualquer requisição de IP/domínio não autorizado.
    """

    def __init__(self, app, allowed_origins):
        super().__init__(app)
        self.allow_all = False
        self.allowed_hosts = []

        for origin in allowed_origins:
            if not origin or origin.strip() == "":
                continue

            origin = origin.strip()

            # se for *, permite tudo (desabilita o bloqueio)
            if origin == "*":
                self.allow_all = True
                return

            # se for URL, extrair o hostname
            if origin.startswith("http://") or origin.startswith("https://"):
                hostname = re.sub(r'^https?://', '', origin).split('/')[0]
                self.allowed_hosts.append(hostname)
            else:
                self.allowed_hosts.append(origin)

        # sempre permitir localhost
        if "127.0.0.1" not in self.allowed_hosts:
            self.allowed_hosts.append("127.0.0.1")
        if "localhost" not in self.allowed_hosts:
            self.allowed_hosts.append("localhost")

    async def dispatch(self, request: Request, call_next):
        client_host = request.client.host if request.client else None

        # se allow_all for True, permite qualquer acesso
        if self.allow_all:
            return await call_next(request)

        # bloquear acesso de hosts não permitidos
        if client_host and client_host not in self.allowed_hosts:
            return Response(
                content="Access denied: Host not allowed",
                status_code=403,
                media_type="text/plain"
            )

        return await call_next(request)