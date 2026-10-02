# MELHORIA (OVA personalizada) — entidade da OVA de reforço gerada pelo agente.
#
# Diferente das OVAs estáticas (página HTML em `ovas`), uma OVA personalizada é
# montada dinamicamente PARA UM ALUNO a partir do banco de conteúdo (recursos +
# questões) filtrado por uma competência em que ele foi mal. Não tem página
# HTML própria: o frontend a renderiza a partir dos itens selecionados
# (personalized_ova_item), reaproveitando os mesmos players e o mesmo quiz das
# OVAs normais.
from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.competencies import Competencies
from peewee import *
import datetime


class PersonalizedOVA(BaseModel):
    personalized_ova_id = AutoField()
    # Aluno dono desta OVA (resolvido do token, nunca do payload).
    student_id = ForeignKeyField(Students, backref="personalized_ovas",
                                 on_delete="cascade", on_update="cascade")
    # Competência-alvo da remediação (o "assunto em que foi mal").
    target_competency_id = ForeignKeyField(Competencies, backref="personalized_ovas",
                                           null=True, on_delete="set null", on_update="cascade")
    title = CharField(max_length=255)
    # Mensagem motivacional dirigida ao aluno (escrita pelo agente/LLM).
    message = TextField(null=True)
    # Justificativa para o professor (qual diagnóstico disparou a OVA).
    rationale = TextField(null=True)
    # "ativa" | "concluida" | "arquivada"
    status = CharField(max_length=30, default="ativa")
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "personalized_ova"


class PersonalizedOVAItem(BaseModel):
    item_id = AutoField()
    personalized_ova_id = ForeignKeyField(PersonalizedOVA, backref="items",
                                          on_delete="cascade", on_update="cascade")
    # "resource" | "question" — qual coluna FK está preenchida.
    item_kind = CharField(max_length=20)
    # Apontam para o banco de conteúdo existente (sem duplicar o conteúdo).
    resource_id = IntegerField(null=True)
    question_id = IntegerField(null=True)
    # Ordem de exibição dentro da OVA personalizada.
    position = IntegerField(default=0)

    class Meta:
        table_name = "personalized_ova_item"
