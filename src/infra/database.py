from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from settings import STR_DATABASE, ASYNC_STR_DATABASE
from sqlalchemy.orm import Session

# engine síncrono (mantido para compatibilidade)
engine = create_engine(STR_DATABASE, echo=True)

# engine assíncrono
async_engine = create_async_engine(ASYNC_STR_DATABASE, echo=True)

# sessão síncrona (mantida para compatibilidade)
Session = sessionmaker(bind=engine, autocommit=False, autoflush=True)

# sessão assíncrona
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# base para trabalhar com tabelas
Base = declarative_base()

# cria as tabelas (agora assíncrono usa run_sync para compatibilidade com create_all)
async def cria_tabelas():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# dependência síncrona (mantida para compatibilidade)
def get_db():
    db_session = Session()
    try:
        yield db_session
    finally:
        db_session.close()

# dependência assíncrona
async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()