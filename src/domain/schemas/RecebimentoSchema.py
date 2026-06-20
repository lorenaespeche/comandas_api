from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── Schema auxiliar reutilizado internamente ─────────────────────────────────

class _FuncionarioMin(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    matricula: str

class _ClienteMin(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    cpf: str
    telefone: Optional[str] = None

class _ProdutoMin(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    foto: Optional[bytes] = None
    valor_unitario: float

class _ItemComanda(BaseModel):
    produto_id: int
    produto_nome: str
    produto_foto: Optional[bytes] = None
    quantidade: int
    valor_unitario: float
    subtotal: float

class _ComandaDetalhe(BaseModel):
    comanda_id: int
    comanda: str
    cliente: Optional[_ClienteMin] = None
    data_hora: datetime
    itens: List[_ItemComanda]
    subtotal: float


# ── Dashboard ─────────────────────────────────────────────────────────────────

class RecebimentoDashboardItem(BaseModel):
    """Item do dashboard simplificado — produtos são mostrados no detalhe."""
    id: int
    comanda: str
    status: int
    cliente: Optional[_ClienteMin] = None
    total: float
    quantidade_produtos: int
    data_hora: datetime


# ── Recebimento completo ──────────────────────────────────────────────────────

class RecebimentoCompletoRequest(BaseModel):
    """Request completa para recebimento com desconto/acréscimo por valor."""
    comandas_ids: List[int]
    cliente_id: Optional[int] = None
    funcionario_id: int
    desconto_valor: Optional[float] = None
    acrescimo_valor: Optional[float] = None


class _ComandaPagaResumo(BaseModel):
    comanda_id: int
    comanda: str
    subtotal: float


class RecebimentoCompletoResponse(BaseModel):
    """Response completa do recebimento realizado."""
    sucesso: bool
    mensagem: str
    recebimento_id: int
    comandas_pagas: List[_ComandaPagaResumo]
    subtotal_geral: float
    desconto_total: float
    acrescimo_total: float
    valor_final: float
    cliente: Optional[_ClienteMin] = None
    funcionario: _FuncionarioMin
    data_hora: datetime


# ── Comprovante ───────────────────────────────────────────────────────────────

class _ResumoValores(BaseModel):
    subtotal_geral: float
    desconto_total: float
    acrescimo_total: float
    valor_final: float

class _InfoRecebimento(BaseModel):
    id: int
    data_hora: datetime

class _Rodape(BaseModel):
    mensagem: str = "Obrigado pela preferência!"
    sistema: str = "Comandas do Zé"

class _Cabecalho(BaseModel):
    titulo: str = "Comprovante de Recebimento"
    sistema: str = "Comandas do Zé"

class ComprovanteRecebimento(BaseModel):
    """Comprovante detalhado do recebimento."""
    cabecalho: _Cabecalho
    cliente: Optional[_ClienteMin] = None
    funcionario: _FuncionarioMin
    comandas: List[_ComandaDetalhe]
    resumo_valores: _ResumoValores
    recebimento: _InfoRecebimento
    rodape: _Rodape
    data_emissao: datetime


# ── CRUD básico de recebimento ────────────────────────────────────────────────

class RecebimentoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    funcionario_id: int
    cliente_id: Optional[int] = None
    subtotal_geral: float
    desconto_total: float
    acrescimo_total: float
    valor_final: float
    data_hora: datetime
    funcionario: Optional[_FuncionarioMin] = None
    cliente: Optional[_ClienteMin] = None
