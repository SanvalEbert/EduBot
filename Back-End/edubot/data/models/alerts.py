from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from peewee import *
from playhouse.mysql_ext import JSONField


# MELHORIA (Roteiro Cena 4) — Alertas preventivos para o tutor.
# Cada linha é um aviso gerado quando um aluno entra em zona de risco (regra do
# EduBot disparada). Alimenta a Central de Alertas do painel do tutor.
#
# B.5: também é a FILA DE APROVAÇÃO. Ações de tier alto do agente entram com
# status='aguardando_aprovacao' e uma `proposed_action` (executada na aprovação).
class Alerts(BaseModel):
    alert_id = IntegerField(primary_key=True)
    student_id = ForeignKeyField(Students, backref="alerts", on_delete="cascade", on_update="cascade")
    type = CharField(max_length=50)
    message = TextField()
    severity = CharField(max_length=20)        # alta | media | baixa
    created_at = DateTimeField()
    read = BooleanField(default=False)
    # B.5 — fila de aprovação. aberto = alerta informativo comum (fluxo atual).
    status = CharField(max_length=30, default="aberto")  # aberto|aguardando_aprovacao|aprovado|rejeitado
    proposed_action = JSONField(null=True)     # ação a executar na aprovação (ou None)
    decision_id = IntegerField(null=True)      # liga à agent_decisions (justificativa)

    class Meta:
        table_name = "alerts"
