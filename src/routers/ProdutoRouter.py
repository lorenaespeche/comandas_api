# Lorena Espeche

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# domain schemas
from domain.schemas.ProdutoSchema import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse
)

# infra
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_db

router = APIRouter()


@router.get("/produto/", response_model=List[ProdutoResponse], tags=["Produto"], status_code=status.HTTP_200_OK)
async def get_produto(db: Session = Depends(get_db)):
    """Retorna todos os produtos"""
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )


@router.get("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
async def get_produto(id: int, db: Session = Depends(get_db)):
    """Retorna um produto específico pelo ID"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
        return produto
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produto: {str(e)}"
        )


@router.post("/produto/", response_model=ProdutoResponse, status_code=status.HTTP_201_CREATED, tags=["Produto"])
async def post_produto(produto_data: ProdutoCreate, db: Session = Depends(get_db)):
    """Cria um novo produto"""
    try:
        # Verifica se já existe produto com este código
        #existing_produto = db.query(ProdutoDB).filter(ProdutoDB.codigo == produto_data.codigo).first()
        #if existing_produto:
        #    raise HTTPException(
        #    status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um produto com este código"
        #    )
        # Cria o novo produto
        novo_produto = ProdutoDB(
            id=None, 
            nome=produto_data.nome,
            descricao=produto_data.descricao,
            valor_unitario=produto_data.valor_unitario,
            foto=produto_data.foto
        )
        db.add(novo_produto)
        db.commit()
        db.refresh(novo_produto)
        return novo_produto
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar produto: {str(e)}"
        )


@router.put("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
async def put_produto(id: int, produto_data: ProdutoUpdate, db: Session = Depends(get_db)):
    """Atualiza um produto existente"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado"
            )
        # Verifica se está tentando atualizar para um código que já existe
        #if produto_data.codigo and produto_data.codigo != produto.codigo:
        #    existing_produto = db.query(ProdutoDB).filter(ProdutoDB.codigo == produto_data.codigo).first()
        #    if existing_produto:
        #        raise HTTPException(
        #            status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um produto com este código"
        #        )
        # Atualiza apenas os campos fornecidos
        update_data = produto_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(produto, field, value)
        db.commit()
        db.refresh(produto)
        return produto
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar produto: {str(e)}"
        )


@router.delete("/produto/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Produto"], summary="Remover produto")
async def delete_produto(id: int, db: Session = Depends(get_db)):
    """Remove um produto"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto não encontrado"
            )
        db.delete(produto)
        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar produto: {str(e)}"
        )