from dotenv import load_dotenv
import os
from pathlib import Path

# Carrega sempre o .env do mesmo diretório que settings.py
dotenv_file = Path(__file__).parent / ".env"
load_dotenv(dotenv_file, override=True)

# configurações da API
HOST = os.getenv("HOST", "0.0.0.0")
PORT = os.getenv("PORT", "8000")
RELOAD = os.getenv("RELOAD", True)

# configurações banco de dados
DB_SGDB = os.getenv("DB_SGDB")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT", "3306")

# ajusta STR_DATABASE conforme gerenciador escolhido
if DB_SGDB == 'sqlite':
    STR_DATABASE = f"sqlite:///{DB_NAME}.db?foreign_keys=1"

elif DB_SGDB == 'mysql':
    import pymysql
    STR_DATABASE = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

elif DB_SGDB == 'mssql':
    import pymssql
    STR_DATABASE = f"mssql+pymssql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8"

elif DB_SGDB == 'postgresql':
    import psycopg2
    STR_DATABASE = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

else:
    STR_DATABASE = f"sqlite:///apiDatabase.db?foreign_keys=1"

# configurações de database assíncrono
if STR_DATABASE.startswith("sqlite:///"):
    ASYNC_STR_DATABASE = STR_DATABASE.replace("sqlite:///", "sqlite+aiosqlite:///")
elif STR_DATABASE.startswith("sqlite://"):
    ASYNC_STR_DATABASE = STR_DATABASE.replace("sqlite://", "sqlite+aiosqlite:///")
elif DB_SGDB == 'mysql':
    ASYNC_STR_DATABASE = STR_DATABASE.replace("mysql+pymysql://", "mysql+aiomysql://")
elif DB_SGDB == 'mssql':
    ASYNC_STR_DATABASE = STR_DATABASE
elif DB_SGDB == 'postgresql':
    ASYNC_STR_DATABASE = STR_DATABASE.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_STR_DATABASE = STR_DATABASE

# configurações JWT
SECRET_KEY = os.getenv("SECRET_KEY", "03f011ec1fc4f6d21b37533d1e67acf18645278016ad779536f588dda6771b50")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# configurações de Rate Limiting
RATE_LIMIT_CRITICAL = os.getenv("RATE_LIMIT_CRITICAL", "5/minute")
RATE_LIMIT_MODERATE = os.getenv("RATE_LIMIT_MODERATE", "100/minute")
RATE_LIMIT_RESTRICTIVE = os.getenv("RATE_LIMIT_RESTRICTIVE", "20/minute")
RATE_LIMIT_LOW = os.getenv("RATE_LIMIT_LOW", "200/minute")
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "50/minute")
RATE_LIMIT_LIGHT = os.getenv("RATE_LIMIT_LIGHT", "300/minute")

# configurações de CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]