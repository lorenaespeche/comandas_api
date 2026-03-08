# Lorena Espeche

from pydantic import BaseModel

class Produto(BaseModel):
    id_produto: int = None
    nome: str
    descricao: str = None
    foto: bytes
    valor_unitario: float