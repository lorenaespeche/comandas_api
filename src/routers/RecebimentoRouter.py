from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import datetime

from domain.schemas.RecebimentoSchema import (
    RecebimentoDashboardItem,
    RecebimentoCompletoRequest,
    RecebimentoCompletoResponse,
    ComprovanteRecebimento,
    RecebimentoResponse,
    _FuncionarioMin,
    _ClienteMin,
    _ItemComanda,
    _ComandaDetalhe,
    _ComandaPagaResumo,
    _ResumoValores,
    _InfoRecebimento,
    _Rodape,
    _Cabecalho,
)
from domain.schemas.AuthSchema import FuncionarioAuth
from infra.orm.ComandaModel import ComandaDB, ComandaProdutoDB
from infra.orm.RecebimentoModel import RecebimentoDB, RecebimentoComandaDB
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.orm.ClienteModel import ClienteDB
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_async_db
from infra.rate_limit import limiter, get_rate_limit
from infra.security import verify_access_token

router = APIRouter(prefix="/recebimento", tags=["Recebimento"])

_bearer = HTTPBearer()

# ─── autenticação assíncrona própria (evita mistura sync/async) ───────────────

async def _get_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_async_db)
) -> FuncionarioAuth:
    payload = verify_access_token(credentials.credentials)
    cpf: str = payload.get("sub")
    id_func: int = payload.get("id")
    if not cpf or not id_func:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    r = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == id_func))
    func = r.scalar_one_or_none()
    if not func or func.cpf != cpf:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")
    return FuncionarioAuth(id=func.id, nome=func.nome, matricula=func.matricula, cpf=func.cpf, grupo=func.grupo)

async def _require_group(groups: list, credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_async_db)) -> FuncionarioAuth:
    user = await _get_user(credentials, db)
    if user.grupo not in groups:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão negada")
    return user

# ─── helpers ──────────────────────────────────────────────────────────────────

async def _total_comanda(db: AsyncSession, comanda_id: int) -> float:
    r = await db.execute(
        select(func.coalesce(func.sum(ComandaProdutoDB.quantidade * ComandaProdutoDB.valor_unitario), 0))
        .where(ComandaProdutoDB.comanda_id == comanda_id)
    )
    return float(r.scalar() or 0)

async def _count_produtos(db: AsyncSession, comanda_id: int) -> int:
    r = await db.execute(
        select(func.count(ComandaProdutoDB.id)).where(ComandaProdutoDB.comanda_id == comanda_id)
    )
    return int(r.scalar() or 0)

def _cli(c) -> _ClienteMin:
    return _ClienteMin(id=c.id, nome=c.nome, cpf=c.cpf, telefone=c.telefone or "")

def _func(f) -> _FuncionarioMin:
    return _FuncionarioMin(id=f.id, nome=f.nome, matricula=f.matricula)

async def _detalhar(db: AsyncSession, comanda: ComandaDB) -> _ComandaDetalhe:
    cliente_obj = None
    if comanda.cliente_id:
        r = await db.execute(select(ClienteDB).where(ClienteDB.id == comanda.cliente_id))
        c = r.scalar_one_or_none()
        if c:
            cliente_obj = _cli(c)

    itens_r = await db.execute(
        select(ComandaProdutoDB, ProdutoDB)
        .outerjoin(ProdutoDB, ComandaProdutoDB.produto_id == ProdutoDB.id)
        .where(ComandaProdutoDB.comanda_id == comanda.id)
    )
    itens, subtotal = [], 0.0
    for cp, prod in itens_r.all():
        sub = float(cp.quantidade) * float(cp.valor_unitario)
        subtotal += sub
        itens.append(_ItemComanda(
            produto_id=cp.produto_id,
            produto_nome=prod.nome if prod else f"Produto {cp.produto_id}",
            produto_foto=prod.foto if prod else None,
            quantidade=cp.quantidade,
            valor_unitario=float(cp.valor_unitario),
            subtotal=sub
        ))
    return _ComandaDetalhe(
        comanda_id=comanda.id, comanda=comanda.comanda, cliente=cliente_obj,
        data_hora=comanda.data_hora, itens=itens, subtotal=subtotal
    )

# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=List[RecebimentoDashboardItem],
    summary="Dashboard completo com comandas abertas")
@limiter.limit(get_rate_limit("moderate"))
async def get_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(_get_user)
):
    try:
        result = await db.execute(
            select(ComandaDB, ClienteDB)
            .outerjoin(ClienteDB, ClienteDB.id == ComandaDB.cliente_id)
            .where(ComandaDB.status == 0)
            .order_by(ComandaDB.data_hora)
        )
        items = []
        for comanda, cliente in result.all():
            total = await _total_comanda(db, comanda.id)
            qtd = await _count_produtos(db, comanda.id)
            items.append(RecebimentoDashboardItem(
                id=comanda.id, comanda=comanda.comanda, status=comanda.status,
                cliente=_cli(cliente) if cliente else None,
                total=total, quantidade_produtos=qtd, data_hora=comanda.data_hora
            ))
        return items
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dashboard: {str(e)}")

# ─── DETALHE ──────────────────────────────────────────────────────────────────

@router.get("/comandas/detalhe/{comandas_ids}", response_model=List[_ComandaDetalhe],
    summary="Detalhar comandas para recebimento")
@limiter.limit(get_rate_limit("moderate"))
async def get_detalhe(
    comandas_ids: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(_get_user)
):
    try:
        ids = [int(i.strip()) for i in comandas_ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs inválidos. Use formato: 1,2,3")
    if not ids:
        raise HTTPException(status_code=400, detail="Nenhum ID informado")
    try:
        r = await db.execute(select(ComandaDB).where(ComandaDB.id.in_(ids)))
        comandas = r.scalars().all()
        if len(comandas) != len(ids):
            encontrados = {c.id for c in comandas}
            raise HTTPException(status_code=404,
                detail=f"Comandas não encontradas: {[i for i in ids if i not in encontrados]}")
        return [await _detalhar(db, c) for c in comandas]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao detalhar comandas: {str(e)}")

# ─── RECEBIMENTO COMPLETO ─────────────────────────────────────────────────────

@router.post("/completo", response_model=RecebimentoCompletoResponse,
    status_code=status.HTTP_201_CREATED, summary="Recebimento completo com desconto/acréscimo")
@limiter.limit(get_rate_limit("restrictive"))
async def processar_recebimento(
    dados: RecebimentoCompletoRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(_get_user)
):
    try:
        if not dados.comandas_ids:
            raise HTTPException(status_code=400, detail="Nenhuma comanda informada")

        r = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == dados.funcionario_id))
        funcionario = r.scalar_one_or_none()
        if not funcionario:
            raise HTTPException(status_code=400, detail="Funcionário não encontrado")

        cliente = None
        if dados.cliente_id:
            r = await db.execute(select(ClienteDB).where(ClienteDB.id == dados.cliente_id))
            cliente = r.scalar_one_or_none()
            if not cliente:
                raise HTTPException(status_code=400, detail="Cliente não encontrado")

        r = await db.execute(select(ComandaDB).where(ComandaDB.id.in_(dados.comandas_ids)))
        comandas = r.scalars().all()
        if len(comandas) != len(dados.comandas_ids):
            encontrados = {c.id for c in comandas}
            raise HTTPException(status_code=404,
                detail=f"Comandas não encontradas: {[i for i in dados.comandas_ids if i not in encontrados]}")

        for c in comandas:
            if c.status != 0:
                raise HTTPException(status_code=400,
                    detail=f"Comanda {c.comanda} não está aberta (status={c.status})")

        subtotal_geral = 0.0
        comandas_pagas = []
        for c in comandas:
            total = await _total_comanda(db, c.id)
            subtotal_geral += total
            comandas_pagas.append(_ComandaPagaResumo(comanda_id=c.id, comanda=c.comanda, subtotal=total))

        desconto = float(dados.desconto_valor or 0)
        acrescimo = float(dados.acrescimo_valor or 0)
        valor_final = subtotal_geral - desconto + acrescimo

        if valor_final < 0:
            raise HTTPException(status_code=400, detail="Desconto maior que o total")

        agora = datetime.now()
        for c in comandas:
            c.status = 1
            c.funcionario_id = dados.funcionario_id
            if dados.cliente_id:
                c.cliente_id = dados.cliente_id

        novo = RecebimentoDB(
            funcionario_id=dados.funcionario_id, cliente_id=dados.cliente_id,
            desconto_valor=desconto, acrescimo_valor=acrescimo,
            subtotal_geral=subtotal_geral, desconto_total=desconto,
            acrescimo_total=acrescimo, valor_final=valor_final, data_hora=agora
        )
        db.add(novo)
        await db.flush()

        for c in comandas:
            db.add(RecebimentoComandaDB(recebimento_id=novo.id, comanda_id=c.id))

        await db.commit()
        await db.refresh(novo)

        return RecebimentoCompletoResponse(
            sucesso=True, mensagem="Recebimento realizado com sucesso",
            recebimento_id=novo.id, comandas_pagas=comandas_pagas,
            subtotal_geral=subtotal_geral, desconto_total=desconto,
            acrescimo_total=acrescimo, valor_final=valor_final,
            cliente=_cli(cliente) if cliente else None,
            funcionario=_func(funcionario), data_hora=agora
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao processar recebimento: {str(e)}")

# ─── COMPROVANTE ──────────────────────────────────────────────────────────────

@router.get("/comprovante/{recebimento_id}", response_model=ComprovanteRecebimento,
    summary="Gerar comprovante de recebimento")
@limiter.limit(get_rate_limit("moderate"))
async def get_comprovante(
    recebimento_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(_get_user)
):
    try:
        r = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == recebimento_id))
        recebimento = r.scalar_one_or_none()
        if not recebimento:
            raise HTTPException(status_code=404, detail="Recebimento não encontrado")

        r = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == recebimento.funcionario_id))
        func_obj = r.scalar_one_or_none()

        cliente_obj = None
        if recebimento.cliente_id:
            r = await db.execute(select(ClienteDB).where(ClienteDB.id == recebimento.cliente_id))
            c = r.scalar_one_or_none()
            if c:
                cliente_obj = _cli(c)

        r = await db.execute(
            select(RecebimentoComandaDB).where(RecebimentoComandaDB.recebimento_id == recebimento_id)
        )
        comanda_ids = [rel.comanda_id for rel in r.scalars().all()]

        r = await db.execute(select(ComandaDB).where(ComandaDB.id.in_(comanda_ids)))
        comandas = r.scalars().all()
        detalhes = [await _detalhar(db, c) for c in comandas]

        return ComprovanteRecebimento(
            cabecalho=_Cabecalho(), cliente=cliente_obj, funcionario=_func(func_obj),
            comandas=detalhes,
            resumo_valores=_ResumoValores(
                subtotal_geral=float(recebimento.subtotal_geral),
                desconto_total=float(recebimento.desconto_total),
                acrescimo_total=float(recebimento.acrescimo_total),
                valor_final=float(recebimento.valor_final)
            ),
            recebimento=_InfoRecebimento(id=recebimento.id, data_hora=recebimento.data_hora),
            rodape=_Rodape(), data_emissao=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar comprovante: {str(e)}")

# ─── CRUD BÁSICO ──────────────────────────────────────────────────────────────

@router.get("/", response_model=List[RecebimentoResponse],
    summary="Listar todos os recebimentos - grupos 1 e 3")
@limiter.limit(get_rate_limit("moderate"))
async def listar_recebimentos(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(_get_user)
):
    try:
        r = await db.execute(
            select(RecebimentoDB, FuncionarioDB, ClienteDB)
            .outerjoin(FuncionarioDB, FuncionarioDB.id == RecebimentoDB.funcionario_id)
            .outerjoin(ClienteDB, ClienteDB.id == RecebimentoDB.cliente_id)
            .order_by(RecebimentoDB.data_hora.desc())
        )
        result = []
        for rec, f, c in r.all():
            result.append(RecebimentoResponse(
                id=rec.id, funcionario_id=rec.funcionario_id, cliente_id=rec.cliente_id,
                subtotal_geral=float(rec.subtotal_geral), desconto_total=float(rec.desconto_total),
                acrescimo_total=float(rec.acrescimo_total), valor_final=float(rec.valor_final),
                data_hora=rec.data_hora,
                funcionario=_func(f) if f else None,
                cliente=_cli(c) if c else None
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar recebimentos: {str(e)}")


@router.get("/{id}", response_model=RecebimentoResponse,
    summary="Buscar recebimento por ID - grupos 1 e 3")
@limiter.limit(get_rate_limit("moderate"))
async def get_recebimento(
    id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(_get_user)
):
    try:
        r = await db.execute(
            select(RecebimentoDB, FuncionarioDB, ClienteDB)
            .outerjoin(FuncionarioDB, FuncionarioDB.id == RecebimentoDB.funcionario_id)
            .outerjoin(ClienteDB, ClienteDB.id == RecebimentoDB.cliente_id)
            .where(RecebimentoDB.id == id)
        )
        row = r.first()
        if not row:
            raise HTTPException(status_code=404, detail="Recebimento não encontrado")
        rec, f, c = row
        return RecebimentoResponse(
            id=rec.id, funcionario_id=rec.funcionario_id, cliente_id=rec.cliente_id,
            subtotal_geral=float(rec.subtotal_geral), desconto_total=float(rec.desconto_total),
            acrescimo_total=float(rec.acrescimo_total), valor_final=float(rec.valor_final),
            data_hora=rec.data_hora,
            funcionario=_func(f) if f else None,
            cliente=_cli(c) if c else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar recebimento: {str(e)}")


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover recebimento - grupo 1")
@limiter.limit(get_rate_limit("critical"))
async def deletar_recebimento(
    id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_user: FuncionarioAuth = Depends(_get_user)
):
    try:
        r = await db.execute(select(RecebimentoDB).where(RecebimentoDB.id == id))
        recebimento = r.scalar_one_or_none()
        if not recebimento:
            raise HTTPException(status_code=404, detail="Recebimento não encontrado")
        r2 = await db.execute(
            select(RecebimentoComandaDB).where(RecebimentoComandaDB.recebimento_id == id)
        )
        for rel in r2.scalars().all():
            await db.delete(rel)
        await db.delete(recebimento)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao remover recebimento: {str(e)}")
