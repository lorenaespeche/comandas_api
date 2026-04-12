# Lorena Espeche

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from settings import HOST, PORT, RELOAD, CORS_ORIGINS
from infra.rate_limit import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import uvicorn

# import das classes com as rotas/endpoints
from routers import AuditoriaRouter
from routers import AuthRouter
from routers import FuncionarioRouter
from routers import ClienteRouter
from routers import ProdutoRouter
from routers import ComandaRouter
from routers import HealthRouter

# lifespan - ciclo de vida da aplicação
from infra import database
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # executa no startup
    print("API has started")
    # cria, caso não existam, as tabelas de todos os modelos que encontrar na aplicação (importados)
    await database.cria_tabelas()
    yield
    # executa no shutdown
    print("API is shutting down")

# cria a aplicação FastAPI com o contexto de vida
app = FastAPI(lifespan=lifespan)

# importar middleware personalizado de controle de acesso por IP
from infra.middleware.IPAccessMiddleware import IPAccessMiddleware

# aplicar middleware de controle de acesso (deve vir antes do CORS)
app.add_middleware(IPAccessMiddleware, allowed_origins=CORS_ORIGINS)

# configuração de CORS - permite integração com frontends modernos (React, Vue, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False if "*" in CORS_ORIGINS else True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["*"],
    max_age=600,
)

# configuração de Rate Limiting
app.state.limiter = limiter

# registrar handler personalizado ANTES de incluir rotas
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# rota padrão
@app.get("/", tags=["Root"], status_code=200, summary="Informações da API - pública")
async def root():
    return {
        "detail": "API Pastelaria",
        "Swagger UI": "http://127.0.0.1:8000/docs",
        "ReDoc": "http://127.0.0.1:8000/redoc"
    }

# incluir as rotas/endpoints no FastAPI
app.include_router(AuditoriaRouter.router)
app.include_router(AuthRouter.router)
app.include_router(FuncionarioRouter.router)
app.include_router(ClienteRouter.router)
app.include_router(ProdutoRouter.router)
app.include_router(ComandaRouter.router)
app.include_router(HealthRouter.router)

if __name__ == "__main__":
    uvicorn.run('main:app', host=HOST, port=int(PORT), reload=RELOAD)