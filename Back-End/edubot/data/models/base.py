import logging
import os

from peewee import *  # ORM

# Configuração do banco por variáveis de ambiente (A4).
#
# O comportamento antigo tentava resolver o host "ova_mysql" no *import* e, se
# falhasse (MySQL lento no boot, hiccup de DNS), caía silenciosamente num
# SQLite local vazio — o progresso do aluno era gravado no container e perdido,
# sem nenhum log. A env DB_HOST definida no compose era ignorada.
#
# Agora:
#   - Por padrão usamos MySQL, com host/credenciais lidos do ambiente.
#   - O SQLite só é usado com opt-in EXPLÍCITO (EDUBOT_DB=sqlite), útil para
#     desenvolvimento/testes locais, e sempre com log em nível WARNING.
#   - Não há mais fallback silencioso: se o MySQL não subir, a aplicação falha
#     de forma visível na primeira query, como deve.

logger = logging.getLogger("edubot.db")

DB_BACKEND = os.environ.get("EDUBOT_DB", "mysql").lower()

if DB_BACKEND == "sqlite":
    sqlite_path = os.environ.get("EDUBOT_SQLITE_PATH", "dev_ova.db")
    logger.warning(
        "EDUBOT_DB=sqlite: usando banco SQLite local em '%s'. "
        "NÃO use isto em produção — os dados ficam no container/máquina local.",
        sqlite_path,
    )
    db = SqliteDatabase(sqlite_path)
else:
    db = MySQLDatabase(
        os.environ.get("DB_NAME", "ova_db"),
        user=os.environ.get("DB_USER", "eduardo"),
        password=os.environ.get("DB_PASSWORD", "Password-1"),
        host=os.environ.get("DB_HOST", "ova_mysql"),
        port=int(os.environ.get("DB_PORT", "3306")),
    )


class BaseModel(Model):
    class Meta:
        database = db  # Define the database to be used for the model
