from edubot.data.models.base import BaseModel
from peewee import *
import datetime


# Integração externa (migration_021) — credencial de MÁQUINA, não de aluno.
#
# O `auth.py` autentica aluno: token HMAC de sessão emitido no /login, carregando
# um student_id. Um sistema parceiro não tem (nem deve ter) aluno: ele apresenta
# uma chave longa no header X-API-Key, e o que ela pode ler é decidido pelos
# `scopes` — ver api/apikey.py, que é onde a regra vive.
#
# A chave em claro NÃO é armazenada: só o SHA-256. Ver a migration para o porquê
# de cada coluna.
class ApiKeys(BaseModel):
    key_id = AutoField()
    name = CharField(max_length=100)
    key_prefix = CharField(max_length=16)
    key_hash = CharField(max_length=64)
    scopes = CharField(max_length=255, default="")
    active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    expires_at = DateTimeField(null=True)
    last_used_at = DateTimeField(null=True)
    request_count = IntegerField(default=0)
    notes = CharField(max_length=255, null=True)

    class Meta:
        table_name = "api_keys"

    def scope_list(self):
        """Escopos concedidos, normalizados (o CSV é o formato de armazenamento,
        não o de uso)."""
        return [s.strip() for s in (self.scopes or "").split(",") if s.strip()]
