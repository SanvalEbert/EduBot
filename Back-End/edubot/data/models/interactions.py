# Import the necessary classes
from edubot.data.models.base import BaseModel
from edubot.data.models.students import Students
from edubot.data.models.ovas import OVAs
from peewee import *

# Class representing the interactions table
class Interactions(BaseModel):
    # Unique identifier for the interaction
    interaction_id = AutoField()
    # Date on which the interaction occurred
    interaction_date = DateField()
    # Time at which the interaction occurred
    interaction_time = TimeField()
    # Description of the action performed by the student
    student_action = TextField()
    # Foreign key referencing the student who made the interaction
    student_id = ForeignKeyField(Students, backref="interactions", on_delete="cascade", on_update="cascade")
    # Foreign key referencing the OVA associated with the interaction
    ova_id = ForeignKeyField(OVAs, backref="interactions", on_delete="cascade", on_update="cascade")
