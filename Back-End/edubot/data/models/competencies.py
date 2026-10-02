# Import the necessary classes
from edubot.data.models.base import BaseModel
from edubot.data.models.subjects import Subjects
from peewee import *

# Class representing the competencies table
class Competencies(BaseModel):
    # Unique identifier for the competency
    competency_id = IntegerField(primary_key=True)
    # Detailed description of the competency
    competency_description = TextField()
    # Tradução EN (Fase 4 — A12); NULL cai no PT (degradação segura)
    competency_description_en = TextField(null=True)
    # Foreign key linking to the subject associated with the competency
    subject_id = ForeignKeyField(Subjects, backref="competencies", on_delete="cascade", on_update="cascade")
