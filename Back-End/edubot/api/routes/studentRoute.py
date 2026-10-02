# Import necessary libraries
from flask import Blueprint, request, g
from flask_cors import cross_origin
from peewee import PeeweeException # ORM library
import json

# Import the necessary ORM classes
from edubot.data.models.students import Students

# MELHORIA (4.2): autenticação + perfil completo do aluno logado
from edubot.api.auth import require_auth, require_roles
from edubot.api.http import get_lang, get_payload
from edubot.services.student_context import build_student_profile
from edubot.services.gamification import PERSONA_IDS

# Create a route blueprint as a reusable component
app_student = Blueprint("student", __name__)

# AV.2 (Plano 3): personas válidas = mascote livre + cientistas (catálogo único no
# gamification). A persona é ferramenta de estudo, disponível a todos.
VALID_PERSONAS = {"edubot", *PERSONA_IDS}


# MELHORIA (4.2): devolve o contexto completo do aluno autenticado (quem está
# logado, recursos consumidos, desempenho por competência, inatividade...).
# É o mesmo perfil consumido pelo edubot_agent e pelo painel (painel.html).
@app_student.route("/student/me", methods=["GET"])
@cross_origin()
@require_auth
def student_me():
    try:
        # Fase 4 (A12): conteúdo (OVAs, recursos, competências) no idioma pedido
        return json.dumps(build_student_profile(g.student, lang=get_lang()), default=str), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500

# AV.2 (Plano 3): grava a persona do companheiro de estudo do aluno logado. A
# escolha antes vivia só no localStorage; agora é atributo do aluno (segue entre
# dispositivos e o tutor IA sabe qual persona "fala"). Desacoplada da gamificação:
# funciona mesmo com EDUBOT_GAMIFICATION=off.
@app_student.route("/student/persona", methods=["POST"])
@cross_origin()
@require_auth
def set_persona():
    persona = (get_payload().get("persona") or "").strip().lower()
    if persona not in VALID_PERSONAS:
        return json.dumps({"error": "invalid_persona"}), 400
    try:
        g.student.persona = persona
        g.student.save()
        return json.dumps({"persona": persona}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


# Given a course id, return all the students of this course
# A.3: expõe nome + ID de alunos (dado pessoal — LGPD). Restrito a tutor/admin;
# antes era anônimo.
@app_student.route("/student/course/<int:course_id>", methods=["GET"])
@cross_origin()
@require_roles("tutor", "admin")
def student_by_course(course_id):
    if request.method == "GET":
        try:
            # Query the students of the course
            students = Students.select().where(Students.course_id == course_id)
            student_list = []
            # For each student, append its id and name to the list
            for student in students:
                student_dict = {
                    "student_id": student.student_id,
                    "student_name": student.student_name
                }
                student_list.append(student_dict.copy())
            return json.dumps(student_list)
        # Handle the error by returning the description of the error
        except PeeweeException as err:
            return json.dumps({"Error": f"{err}"}), 500
    else:
        # Return this if the HTTP method is not GET
        return "Wrong Request Methods. Only GET Allowed", 405
