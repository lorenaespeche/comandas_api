from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from infra.database import get_db
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.security import verify_access_token

from domain.schemas.AuthSchema import FuncionarioAuth

# scheme para extrair token do header Authorization: Bearer <token>
security = HTTPBearer()

# dependency para validar token e retornar usuário atual
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> FuncionarioAuth:
    """Dependency que valida o token e retorna o usuário atual"""
    # extrai e valida o token
    payload = verify_access_token(credentials.credentials)
    cpf: str = payload.get("sub")
    id_funcionario: int = payload.get("id")

    if cpf is None or id_funcionario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido - dados incompletos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # busca o funcionário no banco
    funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.id == id_funcionario).first()

    if not funcionario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Funcionário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # verifica se o CPF do token corresponde ao do banco
    if funcionario.cpf != cpf:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido - CPF não corresponde",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return FuncionarioAuth(
        id=funcionario.id,
        nome=funcionario.nome,
        matricula=funcionario.matricula,
        cpf=funcionario.cpf,
        grupo=funcionario.grupo
    )

# dependency para verificar se o usuário está ativo
def get_current_active_user(
    current_user: FuncionarioAuth = Depends(get_current_user)
) -> FuncionarioAuth:
    """Dependency que verifica se o usuário está ativo (pode ser expandida)"""
    # aqui você pode adicionar lógica para verificar se o usuário está ativo
    # por exemplo, verificar um campo 'ativo' no banco de dados
    return current_user

# dependency para verificar se o usuário tem um grupo específico
def require_group(group_required: list[int] = None):
    """
    Factory function que cria dependency para verificar grupo do usuário
    Args:
    group_required: list[int] or None
    - list[int]: Verifica se usuário pertence a qualquer um dos grupos listados
    - None: Permite qualquer usuário autenticado
    Returns:
    Dependency function para uso em rotas
    """
    def check_group(current_user: FuncionarioAuth = Depends(get_current_active_user)) -> FuncionarioAuth:
        # se group_required for None, permite qualquer usuário autenticado
        if group_required is None:
            return current_user

        # verifica se o grupo do usuário está na lista permitida
        if current_user.grupo not in group_required:
            groups_str = ", ".join(map(str, group_required))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão negada - requerido um dos grupos: {groups_str}"
            )

        return current_user

    return check_group

# exemplos de uso:
# @router.get("/admin/dashboard")
# async def admin_dashboard(current_user: FuncionarioAuth = Depends(require_group([1]))):
# # Apenas grupo 1 (admin)
#
# @router.get("/shared/reports")
# async def shared_reports(current_user: FuncionarioAuth = Depends(require_group([1, 3]))):
# # Grupo 1 ou 3
#
# @router.get("/user/profile")
# async def user_profile(current_user: FuncionarioAuth = Depends(require_group(None))):
# # Qualquer usuário autenticado