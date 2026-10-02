# Import the necessary classes
from edubot.data.models.base import BaseModel
from edubot.data.models.competencies import Competencies
from edubot.data.models.ovas import OVAs
from peewee import *
from playhouse.mysql_ext import JSONField

# Class representing the questions table
class Questions(BaseModel):
    # Unique identifier for the question
    question_id = IntegerField(primary_key=True)
    # Text of the question
    statement = TextField()
    # Possible answers for the question
    alternatives = JSONField()
    # Traduções EN (Fase 4 — A12); NULL cai no PT. As alternativas EN mantêm a
    # MESMA ordem do PT, então o gabarito por letra continua válido.
    statement_en = TextField(null=True)
    alternatives_en = JSONField(null=True)
    # Correct answer for the question
    answer = TextField()
    # Foreign key referencing the OVA to which the question belongs
    ova_id = ForeignKeyField(OVAs, backref="questions", on_delete="cascade", on_update="cascade")
    # Foreign key referencing the competency to which the question belongs
    competency_id = ForeignKeyField(Competencies, backref="questions", on_delete="cascade", on_update="cascade")
    # D.4 — nível de dificuldade: 1 fácil · 2 média · 3 difícil. Alimenta o pool
    # adaptativo de /question/ova (dificuldade vs. domínio da competência).
    difficulty = IntegerField(default=2)
