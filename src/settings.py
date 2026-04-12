from dotenv import load_dotenv, find_dotenv
import os

# localiza o arquivo de .env
dotenv_file = find_dotenv()

# carrega o arquivo .env
load_dotenv(dotenv_file)

# configurações da API
HOST = os.getenv("HOST", "0.0.0.0")
PORT = os.getenv("PORT", "8000")
RELOAD = os.getenv("RELOAD", True)

# configurações banco de dados
DB_SGDB = os.getenv("DB_SGDB")
DB_NAME = os.getenv("DB_NAME")

# caso seja diferente de sqlite
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# ajusta STR_DATABASE conforme gerenciador escolhido
if DB_SGDB == 'sqlite':  # SQLite
    # habilita foreign keys - integridade referencial
    STR_DATABASE = f"sqlite:///{DB_NAME}.db?foreign_keys=1"

elif DB_SGDB == 'mysql':  # MySQL
    import pymysql
    STR_DATABASE = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"

elif DB_SGDB == 'mssql':  # SQL Server
    import pymssql
    STR_DATABASE = f"mssql+pymssql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8"

elif DB_SGDB == 'postgresql':  # PostgreSQL
    import psycopg2
    STR_DATABASE = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

else:  # SQLite fallback
    STR_DATABASE = f"sqlite:///apiDatabase.db?foreign_keys=1"

# configurações de database assíncrono
if STR_DATABASE.startswith("sqlite:///"):
    ASYNC_STR_DATABASE = STR_DATABASE.replace("sqlite:///", "sqlite+aiosqlite:///")
elif STR_DATABASE.startswith("sqlite://"):
    ASYNC_STR_DATABASE = STR_DATABASE.replace("sqlite://", "sqlite+aiosqlite:///")
elif DB_SGDB == 'mysql':
    ASYNC_STR_DATABASE = STR_DATABASE.replace("mysql+pymysql://", "mysql+aiomysql://")
elif DB_SGDB == 'mssql':
    ASYNC_STR_DATABASE = STR_DATABASE  # aiomssql não disponível
elif DB_SGDB == 'postgresql':
    ASYNC_STR_DATABASE = STR_DATABASE.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_STR_DATABASE = STR_DATABASE

# configurações JWT
SECRET_KEY = os.getenv("SECRET_KEY", "03f011ec1fc4f6d21b37533d1e67acf18645278016ad779536f588dda6771b50")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# configurações de CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]