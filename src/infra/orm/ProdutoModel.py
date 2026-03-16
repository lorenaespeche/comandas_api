# Lorena Espeche

from infra import database
from sqlalchemy import Column, VARCHAR, Integer, LargeBinary

# ORM
class ProdutoDB(database.Base):
    __tablename__ = 'tb_produto'

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nome = Column(VARCHAR(100), nullable=False)
    descricao = Column(VARCHAR(200), nullable=False)
    valor_unitario = Column(Integer, nullable=False)
    foto = Column(LargeBinary, nullable=True)

    def __init__(self, id, nome, descricao, valor_unitario, foto):
        self.id = id
        self.nome = nome
        self.descricao = descricao
        self.valor_unitario = valor_unitario
        self.foto = foto