"""Backfill do mastery (D.2) — reprocessa o histórico de `attempts`.

Após rodar a migration_008, o modelo do aluno (student_mastery) ainda está vazio
para os alunos que já responderam quizzes. Este script reprocessa TODAS as
tentativas em ordem cronológica, aplicando o BKT com o timestamp real de cada
tentativa (o decaimento entre elas fica correto).

IDEMPOTENTE: apaga o mastery existente e recomputa do zero — rodar duas vezes
produz exatamente o mesmo estado. O índice (student_id, attempt_time) da A.2
torna a leitura ordenada barata.

Uso:
    docker exec -i ova_back_end python -m tools.backfill_mastery
"""
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edubot.backfill_mastery")


def run():
    from edubot.data.models.base import db
    from edubot.data.models.attempts import Attempts
    from edubot.data.models.questions import Questions
    from edubot.data.models.student_mastery import StudentMastery
    from edubot.services.mastery import update_on_attempt

    if db.is_closed():
        db.connect(reuse_if_open=True)

    # Recompute do zero -> idempotência.
    deleted = StudentMastery.delete().execute()
    logger.info("Mastery anterior apagado: %s linhas.", deleted)

    processed = 0
    # dicts() devolve os ids crus das FKs (student_id, competency_id) — evita
    # lazy-load por linha. Ordem cronológica global para o decaimento bater.
    query = (Attempts
             .select(Attempts.student_id, Attempts.is_correct,
                     Attempts.attempt_time,
                     Questions.competency_id.alias("competency_id"))
             .join(Questions, on=(Attempts.question_id == Questions.question_id))
             .order_by(Attempts.attempt_time, Attempts.attempt_id)
             .dicts())
    for att in query:
        update_on_attempt(att["student_id"], att["competency_id"],
                          att["is_correct"], now=att["attempt_time"])
        processed += 1

    logger.info("Backfill concluído: %s tentativas reprocessadas, %s pares (aluno, competência).",
                processed, StudentMastery.select().count())
    return processed


if __name__ == "__main__":
    run()
