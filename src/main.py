# Lorena Espeche

from fastapi import FastAPI
from settings import HOST, PORT, RELOAD
import uvicorn

from routers import FuncionarioRouter
from routers import ClienteRouter
from routers import ProdutoRouter

app = FastAPI()

# mapeamento das rotas/endpoints
app.include_router(FuncionarioRouter.router)
app.include_router(ClienteRouter.router)
app.include_router(ProdutoRouter.router)

# rota padrão
@app.get("/", tags=["Root"], status_code=200)
def root():
    return {
        "detail": "API Pastelaria do Zé",
        "Swagger": "http://127.0.0.1:8000/docs",
        "ReDoc": "http://127.0.0.1:8000/redoc"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=int(PORT), reload=RELOAD)