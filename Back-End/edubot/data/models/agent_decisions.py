from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from peewee import *
from playhouse.mysql_ext import JSONField
import datetime


# B.2 — trilha de decisões do agente EduBot.
# Uma linha por decisão do "cérebro" (mock ou LLM real). É a base de
# auditabilidade, observabilidade (custo/latência) e do sinal de aprendizado
# (outcome, preenchido depois em B.6).
class AgentDecisions(BaseModel):
    decision_id = AutoField()
    student_id = ForeignKeyField(Students, backref="agent_decisions",
                                 on_delete="cascade", on_update="cascade", null=True)
    trigger_type = CharField(max_length=40)   # quiz_failed | ova_completed | sweep | on_demand | chat | personalized_ova
    input_digest = JSONField(null=True)        # digest minimizado (sem RA/nome completo)
    model_id = CharField(max_length=80, null=True)
    mock = BooleanField(default=True)
    tools_called = JSONField(null=True)        # [{name, ok}, ...]
    actions = JSONField(null=True)             # [{type, id}, ...]
    latency_ms = IntegerField(default=0)
    input_tokens = IntegerField(default=0)
    output_tokens = IntegerField(default=0)
    outcome = CharField(max_length=30, null=True)  # aceita | dispensada | expirada | melhorou
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "agent_decisions"
