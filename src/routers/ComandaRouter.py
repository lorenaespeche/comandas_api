from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import datetime
from domain.schemas.ComandaSchema import (
    ComandaCreate, ComandaUpdate, ComandaResponse, FuncionarioResponse, ClienteResponse,
    ComandaProdutosCreate, ComandaProdutosUpdate, ComandaProdutosResponse, ProdutoResponse
)
from domain.schemas.AuthSchema import FuncionarioAuth
from infra.orm.ComandaModel import ComandaDB, ComandaProdutoDB
from infra.orm.ProdutoModel import ProdutoDB
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.orm.ClienteModel import ClienteDB
from infra.database import get_async_db
from infra.dependencies import require_group, get_current_active_user
from infra.rate_limit import limiter, get_rate_limit
from services.AuditoriaService import AuditoriaService

router = APIRouter()

# busca comanda conforme id informado
@router.get("/comanda/{id}", response_model=ComandaResponse, tags=["Comanda"], summary="Buscar comanda por ID - protegida por JWT")
@limiter.limit(get_rate_limit("moderate"))
async def get_comanda(id: int, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    try:
        result = await db.execute(
            select(ComandaDB, FuncionarioDB, ClienteDB)
            .outerjoin(FuncionarioDB, FuncionarioDB.id == ComandaDB.funcionario_id)
            .outerjoin(ClienteDB, ClienteDB.id == ComandaDB.cliente_id)
            .where(ComandaDB.id == id)
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        comanda, funcionario, cliente = row
        return ComandaResponse(
            id=comanda.id, comanda=comanda.comanda, data_hora=comanda.data_hora, status=comanda.status,
            cliente_id=comanda.cliente_id, funcionario_id=comanda.funcionario_id,
            funcionario=FuncionarioResponse(id=funcionario.id, nome=funcionario.nome, matricula=funcionario.matricula,
                cpf=funcionario.cpf, telefone=funcionario.telefone, grupo=funcionario.grupo) if funcionario else None,
            cliente=ClienteResponse(id=cliente.id, nome=cliente.nome, cpf=cliente.cpf,
                telefone=cliente.telefone) if cliente else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao buscar comanda: {str(e)}")

# lista todas as comandas com paginação e filtro opcional
@router.get("/comanda/", response_model=List[ComandaResponse], tags=["Comanda"], summary="Listar todas as comandas - opção de filtro e paginação - protegida por JWT")
@limiter.limit(get_rate_limit("moderate"))
async def get_comandas(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    id: Optional[int] = Query(None),
    comanda: Optional[str] = Query(None),
    status: Optional[int] = Query(None),
    funcionario_id: Optional[int] = Query(None),
    cliente_id: Optional[int] = Query(None),
    data_inicio: Optional[datetime] = Query(None),
    data_fim: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user)
):
    try:
        query = select(ComandaDB, FuncionarioDB, ClienteDB)\
            .outerjoin(FuncionarioDB, FuncionarioDB.id == ComandaDB.funcionario_id)\
            .outerjoin(ClienteDB, ClienteDB.id == ComandaDB.cliente_id)
        conditions = []
        if id is not None:
            conditions.append(ComandaDB.id == id)
        if comanda is not None:
            conditions.append(ComandaDB.comanda == comanda)
        if status is not None:
            conditions.append(ComandaDB.status == status)
        if funcionario_id is not None:
            conditions.append(ComandaDB.funcionario_id == funcionario_id)
        if cliente_id is not None:
            conditions.append(ComandaDB.cliente_id == cliente_id)
        if data_inicio is not None:
            conditions.append(ComandaDB.data_hora >= data_inicio)
        if data_fim is not None:
            conditions.append(ComandaDB.data_hora <= data_fim)
        if conditions:
            query = query.where(*conditions)
        result = await db.execute(query.offset(skip).limit(limit))
        results = result.all()
        comandas_response = []
        for comanda_obj, funcionario, cliente in results:
            comandas_response.append(ComandaResponse(
                id=comanda_obj.id, comanda=comanda_obj.comanda, data_hora=comanda_obj.data_hora,
                status=comanda_obj.status, cliente_id=comanda_obj.cliente_id, funcionario_id=comanda_obj.funcionario_id,
                funcionario=FuncionarioResponse(id=funcionario.id, nome=funcionario.nome, matricula=funcionario.matricula,
                    cpf=funcionario.cpf, telefone=funcionario.telefone, grupo=funcionario.grupo) if funcionario else None,
                cliente=ClienteResponse(id=cliente.id, nome=cliente.nome, cpf=cliente.cpf,
                    telefone=cliente.telefone) if cliente else None
            ))
        return comandas_response
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao buscar comandas: {str(e)}")

# nova comanda
@router.post("/comanda/", response_model=ComandaResponse, status_code=status.HTTP_201_CREATED, tags=["Comanda"], summary="Criar nova comanda - protegida por JWT")
@limiter.limit(get_rate_limit("restrictive"))
async def create_comanda(comanda_data: ComandaCreate, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    try:
        result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == comanda_data.funcionario_id))
        funcionario = result.scalar_one_or_none()
        if not funcionario:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Funcionário não encontrado")
        if comanda_data.cliente_id:
            result = await db.execute(select(ClienteDB).where(ClienteDB.id == comanda_data.cliente_id))
            cliente = result.scalar_one_or_none()
            if not cliente:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cliente não encontrado")
        if comanda_data.status not in [0]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status inválido - na abertura a comanda deve estar com status 0 (aberta)")
        result = await db.execute(
            select(ComandaDB).where(ComandaDB.comanda == comanda_data.comanda).where(ComandaDB.status == 0)
        )
        comanda_existente = result.scalar_one_or_none()
        if comanda_existente:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comanda já existe e está aberta")
        new_comanda = ComandaDB(
            comanda=comanda_data.comanda,
            data_hora=datetime.now(),
            status=comanda_data.status,
            cliente_id=comanda_data.cliente_id,
            funcionario_id=comanda_data.funcionario_id
        )
        db.add(new_comanda)
        await db.commit()
        await db.refresh(new_comanda)
        AuditoriaService.registrar_acao(db=db, funcionario_id=current_user.id, acao="CREATE", recurso="COMANDA",
            recurso_id=new_comanda.id, dados_novos=new_comanda, request=request)
        return new_comanda
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar comanda: {str(e)}")

# atualizar comanda
@router.put("/comanda/{id}", response_model=ComandaResponse, tags=["Comanda"], summary="Atualizar comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("restrictive"))
async def update_comanda(id: int, comanda_data: ComandaUpdate, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        dados_antigos_obj = comanda.__dict__.copy()
        if comanda_data.comanda is not None:
            comanda.comanda = comanda_data.comanda
        if comanda_data.status is not None:
            comanda.status = comanda_data.status
        if comanda_data.cliente_id is not None:
            if comanda_data.cliente_id != 0:
                result = await db.execute(select(ClienteDB).where(ClienteDB.id == comanda_data.cliente_id))
                cliente = result.scalar_one_or_none()
                if not cliente:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cliente não encontrado")
                comanda.cliente_id = comanda_data.cliente_id
            else:
                comanda.cliente_id = None
        if comanda_data.funcionario_id is not None:
            result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == comanda_data.funcionario_id))
            funcionario = result.scalar_one_or_none()
            if not funcionario:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Funcionário não encontrado")
            comanda.funcionario_id = comanda_data.funcionario_id
        await db.commit()
        await db.refresh(comanda)
        AuditoriaService.registrar_acao(db=db, funcionario_id=current_user.id, acao="UPDATE", recurso="COMANDA",
            recurso_id=comanda.id, dados_antigos=dados_antigos_obj, dados_novos=comanda, request=request)
        return comanda
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar comanda: {str(e)}")

# excluir comanda
@router.delete("/comanda/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Comanda"], summary="Remover comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("critical"))
async def delete_comanda(id: int, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        result = await db.execute(select(func.count(ComandaProdutoDB.id)).where(ComandaProdutoDB.comanda_id == id))
        produtos_count = result.scalar()
        if produtos_count > 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível excluir comanda com {produtos_count} produtos vinculados. Remova os produtos primeiro.")
        await db.delete(comanda)
        await db.commit()
        AuditoriaService.registrar_acao(db=db, funcionario_id=current_user.id, acao="DELETE", recurso="COMANDA",
            recurso_id=id, dados_antigos=comanda, request=request)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao remover comanda: {str(e)}")

# cancelar comanda
@router.put("/comanda/{id}/cancelar", response_model=ComandaResponse, tags=["Comanda"], summary="Cancelar comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("critical"))
async def cancelar_comanda(id: int, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        if comanda.status == 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comanda já está cancelada")
        if comanda.status == 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comanda já está fechada e não pode ser cancelada")
        dados_antigos = {"id": comanda.id, "comanda": comanda.comanda, "status": comanda.status,
            "data_hora": comanda.data_hora.isoformat() if comanda.data_hora else None}
        comanda.status = 2
        await db.commit()
        await db.refresh(comanda)
        AuditoriaService.registrar_acao(db=db, funcionario_id=current_user.id, acao="CANCEL", recurso="comanda",
            recurso_id=comanda.id, dados_antigos=dados_antigos, request=request)
        result = await db.execute(
            select(ComandaDB, FuncionarioDB, ClienteDB)
            .outerjoin(FuncionarioDB, FuncionarioDB.id == ComandaDB.funcionario_id)
            .outerjoin(ClienteDB, ClienteDB.id == ComandaDB.cliente_id)
            .where(ComandaDB.id == id)
        )
        comanda_data = result.first()
        comanda, funcionario, cliente = comanda_data
        return ComandaResponse(
            id=comanda.id, comanda=comanda.comanda, data_hora=comanda.data_hora, status=comanda.status,
            cliente_id=comanda.cliente_id, funcionario_id=comanda.funcionario_id,
            funcionario=FuncionarioResponse(id=funcionario.id, nome=funcionario.nome, matricula=funcionario.matricula,
                cpf=funcionario.cpf, telefone=funcionario.telefone, grupo=funcionario.grupo) if funcionario else None,
            cliente=ClienteResponse(id=cliente.id, nome=cliente.nome, cpf=cliente.cpf,
                telefone=cliente.telefone) if cliente else None
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao cancelar comanda: {str(e)}")

# adicionar produto à comanda
@router.post("/comanda/{comanda_id}/produto", response_model=ComandaProdutosResponse, status_code=status.HTTP_201_CREATED, tags=["Comanda"], summary="Adicionar produto à comanda - protegida por JWT")
@limiter.limit(get_rate_limit("restrictive"))
async def add_produto_to_comanda(comanda_id: int, produto_data: ComandaProdutosCreate, request: Request,
    db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == comanda_id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        if comanda.status != 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível adicionar produtos a uma comanda fechada ou cancelada")
        result = await db.execute(select(ProdutoDB).where(ProdutoDB.id == produto_data.produto_id))
        produto = result.scalar_one_or_none()
        if not produto:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Produto não encontrado")
        result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == produto_data.funcionario_id))
        funcionario = result.scalar_one_or_none()
        if not funcionario:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Funcionário não encontrado")
        new_comanda_produto = ComandaProdutoDB(
            comanda_id=comanda_id, produto_id=produto_data.produto_id,
            funcionario_id=produto_data.funcionario_id, quantidade=produto_data.quantidade,
            valor_unitario=produto_data.valor_unitario
        )
        db.add(new_comanda_produto)
        await db.commit()
        await db.refresh(new_comanda_produto)
        AuditoriaService.registrar_acao(db=db, funcionario_id=current_user.id, acao="CREATE", recurso="COMANDA_PRODUTO",
            recurso_id=new_comanda_produto.id, dados_novos=new_comanda_produto, request=request)
        return new_comanda_produto
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao adicionar produto à comanda: {str(e)}")

# listar produtos de uma comanda
@router.get("/comanda/{id}/produtos", response_model=List[ComandaProdutosResponse], tags=["Comanda"], summary="Listar produtos de uma comanda - protegida por JWT")
@limiter.limit(get_rate_limit("moderate"))
async def get_comanda_produtos(id: int, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    try:
        result = await db.execute(select(ComandaDB).where(ComandaDB.id == id))
        comanda = result.scalar_one_or_none()
        if not comanda:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comanda não encontrada")
        produtos_result = await db.execute(
            select(ComandaProdutoDB, ProdutoDB, FuncionarioDB)
            .outerjoin(ProdutoDB, ComandaProdutoDB.produto_id == ProdutoDB.id)
            .outerjoin(FuncionarioDB, ComandaProdutoDB.funcionario_id == FuncionarioDB.id)
            .where(ComandaProdutoDB.comanda_id == id)
        )
        produtos_response = []
        for comanda_produto, produto, funcionario in produtos_result.all():
            produtos_response.append(ComandaProdutosResponse(
                id=comanda_produto.id, comanda_id=comanda_produto.comanda_id,
                funcionario_id=comanda_produto.funcionario_id,
                funcionario=FuncionarioResponse(id=funcionario.id, nome=funcionario.nome, matricula=funcionario.matricula,
                    cpf=funcionario.cpf, telefone=funcionario.telefone, grupo=funcionario.grupo) if funcionario else None,
                produto_id=comanda_produto.produto_id,
                produto=ProdutoResponse(id=produto.id, nome=produto.nome, descricao=produto.descricao,
                    foto=produto.foto, valor_unitario=produto.valor_unitario) if produto else None,
                quantidade=comanda_produto.quantidade, valor_unitario=comanda_produto.valor_unitario
            ))
        return produtos_response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao buscar produtos da comanda: {str(e)}")

# atualizar produto de uma comanda
@router.put("/comanda/produto/{id}", response_model=ComandaProdutosResponse, tags=["Comanda"], summary="Atualizar produto na comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("restrictive"))
async def update_comanda_produto(id: int, produto_data: ComandaProdutosUpdate, request: Request,
    db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaProdutoDB).where(ComandaProdutoDB.id == id))
        comanda_produto = result.scalar_one_or_none()
        if not comanda_produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto da comanda não encontrado")
        dados_antigos_obj = comanda_produto.__dict__.copy()
        if produto_data.quantidade is not None:
            if produto_data.quantidade <= 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantidade deve ser maior que zero")
            comanda_produto.quantidade = produto_data.quantidade
        if produto_data.valor_unitario is not None:
            if produto_data.valor_unitario <= 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valor unitário deve ser maior que zero")
            comanda_produto.valor_unitario = produto_data.valor_unitario
        await db.commit()
        await db.refresh(comanda_produto)
        AuditoriaService.registrar_acao(db=db, funcionario_id=current_user.id, acao="UPDATE", recurso="COMANDA_PRODUTO",
            recurso_id=comanda_produto.id, dados_antigos=dados_antigos_obj, dados_novos=comanda_produto, request=request)
        return comanda_produto
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar produto da comanda: {str(e)}")

# deletar produto da comanda
@router.delete("/comanda/produto/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Comanda"], summary="Remover produto da comanda - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("critical"))
async def remove_produto_from_comanda(id: int, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        result = await db.execute(select(ComandaProdutoDB).where(ComandaProdutoDB.id == id))
        comanda_produto = result.scalar_one_or_none()
        if not comanda_produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto da comanda não encontrado")
        await db.delete(comanda_produto)
        await db.commit()
        AuditoriaService.registrar_acao(db=db, funcionario_id=current_user.id, acao="DELETE", recurso="COMANDA_PRODUTO",
            recurso_id=id, dados_antigos=comanda_produto, request=request)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao remover produto da comanda: {str(e)}")
