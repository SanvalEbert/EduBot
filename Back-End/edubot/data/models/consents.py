from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from peewee import *
import datetime


# D.5 — consentimento (LGPD). Uma linha por (aluno, finalidade); o estado atual é
# `granted` mais o par granted_at/revoked_at para a trilha temporal. As três
# finalidades são constantes em services/consents.py (fonte da verdade).
class Consents(BaseModel):
    consent_id = AutoField()
    student_id = ForeignKeyField(Students, backref="consents",
                                 on_delete="cascade", on_update="cascade")
    purpose = CharField(max_length=40)   # tracking_pedagogico | ia_sobre_dados | imagem_voz
    granted = BooleanField()
    granted_at = DateTimeField(default=datetime.datetime.now)
    revoked_at = DateTimeField(null=True)

    class Meta:
        table_name = "consents"
        indexes = ((("student_id", "purpose"), True),)  # UNIQUE (uc_consent)
