# Lorena Espeche

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List

# domain schemas
from domain.schemas.ProdutoSchema import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse,
    ProdutoPublicResponse
)
from domain.schemas.AuthSchema import FuncionarioAuth

# infra
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_db
from infra.dependencies import get_current_active_user, require_group
from infra.rate_limit import limiter, get_rate_limit
from slowapi.errors import RateLimitExceeded
from services.AuditoriaService import AuditoriaService

router = APIRouter()


@router.get(
    "/produto/public/",
    response_model=List[ProdutoPublicResponse],
    tags=["Produto"],
    status_code=status.HTTP_200_OK,
    summary="Listar todos os produtos - pública - sem id e valor"
)
@limiter.limit(get_rate_limit("low"))
async def get_produtos_public(
    request: Request,
    db: Session = Depends(get_db)
):
    """Retorna todos os produtos sem id e valor unitário - pública"""
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    except RateLimitExceeded:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )


@router.get(
    "/produto/",
    response_model=List[ProdutoResponse],
    tags=["Produto"],
    status_code=status.HTTP_200_OK,
    summary="Listar todos os produtos - protegida"
)
@limiter.limit(get_rate_limit("moderate"))
async def get_produtos(
    request: Request,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user)
):
    """Retorna todos os produtos completos - protegida por autenticação"""
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    except RateLimitExceeded:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )


@router.get(
    "/produto/{id}",
    response_model=ProdutoResponse,
    tags=["Produto"],
    status_code=status.HTTP_200_OK,
    summary="Buscar produto por ID - protegida"
)
@limiter.limit(get_rate_limit("moderate"))
async def get_produto(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user)
):
    """Retorna um produto específico pelo ID - protegida por autenticação"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto não encontrado"
            )
        return produto
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produto: {str(e)}"
        )


@router.post(
    "/produto/",
    response_model=ProdutoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Produto"],
    summary="Criar novo produto - grupo 1"
)
@limiter.limit(get_rate_limit("restrictive"))
async def post_produto(
    request: Request,
    produto_data: ProdutoCreate,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    """Cria um novo produto - protegida por autenticação e grupo 1"""
    try:
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

        # Registra a ação na auditoria depois de tudo executado e antes do return
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="PRODUTO",
            recurso_id=novo_produto.id,
            dados_antigos=None,
            dados_novos=novo_produto,
            request=request
        )

        return novo_produto
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar produto: {str(e)}"
        )


@router.put(
    "/produto/{id}",
    response_model=ProdutoResponse,
    tags=["Produto"],
    status_code=status.HTTP_200_OK,
    summary="Atualizar produto - grupo 1"
)
@limiter.limit(get_rate_limit("restrictive"))
async def put_produto(
    id: int,
    request: Request,
    produto_data: ProdutoUpdate,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    """Atualiza um produto existente - protegida por autenticação e grupo 1"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto não encontrado"
            )

        # Armazena cópia dos dados atuais para a auditoria (antes de alterar)
        dados_antigos_obj = produto.__dict__.copy()

        update_data = produto_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(produto, field, value)

        db.commit()
        db.refresh(produto)

        # Registra a ação na auditoria depois de tudo executado e antes do return
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="PRODUTO",
            recurso_id=produto.id,
            dados_antigos=dados_antigos_obj,
            dados_novos=produto,
            request=request
        )

        return produto
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar produto: {str(e)}"
        )


@router.delete(
    "/produto/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Produto"],
    summary="Remover produto - grupo 1"
)
@limiter.limit(get_rate_limit("critical"))
async def delete_produto(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    """Remove um produto - protegida por autenticação e grupo 1"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto não encontrado"
            )

        db.delete(produto)
        db.commit()

        # Registra a ação na auditoria depois de tudo executado e antes do return
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="DELETE",
            recurso="PRODUTO",
            recurso_id=produto.id,
            dados_antigos=produto,
            dados_novos=None,
            request=request
        )

        return None
    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar produto: {str(e)}"
        )