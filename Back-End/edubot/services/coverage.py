"""Cobertura de conteúdo por competência (Plano de Rastreabilidade — §6.2).

A auditoria encontrou competências que o reforço não consegue atender de fato:
umas com pouquíssimas questões (o quiz de verificação repete as mesmas que o
aluno acabou de errar) e várias com remediação em um único formato (o que anula
a personalização por preferência de formato — não há alternativa a oferecer).

Este serviço expõe o INVARIANTE de conteúdo para que a lacuna seja visível no
painel do gestor e para que um teste possa travar a regressão. Ele reporta —
não inventa conteúdo: produzir as questões/recursos que faltam é trabalho
editorial, não de código.
"""
from peewee import JOIN, fn

from edubot.data.models.competencies import Competencies
from edubot.data.models.offerings import Offerings
from edubot.data.models.questions import Questions
from edubot.data.models.resources import Resources
from edubot.data.models.subjects import Subjects

# Mínimos para uma competência ser "remediável" de verdade.
MIN_QUESTIONS = 3   # abaixo disso o BKT converge mal e o reforço repete questões
MIN_FORMATS = 2     # sem 2 formatos não há o que personalizar por preferência


def competency_coverage(course_id=None):
    """Cobertura por competência: questões e formatos de remediação disponíveis.

    `course_id` restringe às competências ofertadas no curso (é o recorte que o
    gestor enxerga). Sem ele, avalia todas as competências cadastradas.

    Retorna lista de dicts com `ok` já calculado — quem consome (painel ou teste)
    não repete a regra."""
    questoes_por_comp = {
        row["competency_id"]: row["total"]
        for row in (Questions
                    .select(Questions.competency_id.alias("competency_id"),
                            fn.COUNT(Questions.question_id).alias("total"))
                    .group_by(Questions.competency_id)
                    .dicts())
    }
    formatos_por_comp = {}
    for row in (Resources
                .select(Resources.competency_id.alias("competency_id"),
                        Resources.resource_type.alias("tipo"))
                .where(Resources.competency_id.is_null(False))
                .distinct()
                .dicts()):
        formatos_por_comp.setdefault(row["competency_id"], set()).add(row["tipo"])

    query = (Competencies
             .select(Competencies.competency_id, Competencies.competency_description,
                     Subjects.subject_name.alias("assunto"))
             .join(Subjects, on=(Competencies.subject_id == Subjects.subject_id)))
    if course_id is not None:
        query = (query
                 .join(Offerings, JOIN.INNER, on=(Offerings.subject_id == Subjects.subject_id))
                 .where(Offerings.course_id == course_id))

    cobertura = []
    for row in query.dicts():
        competency_id = row["competency_id"]
        questoes = questoes_por_comp.get(competency_id, 0)
        formatos = sorted(formatos_por_comp.get(competency_id, set()))
        cobertura.append({
            "competency_id": competency_id,
            "nome": row["competency_description"],
            "assunto": row["assunto"],
            "questoes": questoes,
            "formatos": formatos,
            "ok": questoes >= MIN_QUESTIONS and len(formatos) >= MIN_FORMATS,
        })
    cobertura.sort(key=lambda item: (item["ok"], item["competency_id"]))
    return cobertura


def coverage_gaps(course_id=None):
    """Só as competências que violam o invariante — o que o gestor precisa agir."""
    return [item for item in competency_coverage(course_id) if not item["ok"]]
