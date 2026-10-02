from edubot.data.models.base import BaseModel
from edubot.data.models.api_keys import ApiKeys
from peewee import *
from playhouse.mysql_ext import JSONField
import datetime


# Integração externa (migration_022) — evento enviado pelo edubot-tracker.js a
# partir de uma página de TERCEIRO (material de parceiro, página de teste,
# futuramente o Canvas). Fica separado de `learning_events` de propósito: aqui
# não há aluno do EduBot nem verbo do enum — ver a migration para o porquê.
class CollectedEvents(BaseModel):
    event_id = BigAutoField()
    api_key = ForeignKeyField(ApiKeys, column_name="key_id", backref="collected_events")
    event_type = CharField(max_length=40)
    target = CharField(max_length=120, null=True)
    visitor_id = CharField(max_length=64)
    session_id = CharField(max_length=64, null=True)
    user_ref = CharField(max_length=64, null=True)
    page_url = CharField(max_length=500, null=True)
    page_title = CharField(max_length=200, null=True)
    context = JSONField(null=True)
    origin = CharField(max_length=200, null=True)
    occurred_at = DateTimeField()
    received_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "collected_events"
