"""Calibração de dificuldade (D.4) — a partir da proporção de erro histórica.

Após a migration_010 (todas as questões em `difficulty=2`), este job estima o
nível de cada questão pela taxa de erro global em `attempts`:
    < 25% erro  -> 1 (fácil)
    25%–60%     -> 2 (média)
    > 60%       -> 3 (difícil)
Questões sem tentativas ficam na média (2). IDEMPOTENTE (recomputa do histórico).
Recalibrar periodicamente (mensal) no scheduler.

Uso:
    docker exec ova_back_end python -m tools.calibrate_difficulty
"""
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edubot.calibrate_difficulty")

EASY_MAX = 0.25
HARD_MIN = 0.60


def _level(error_rate):
    if error_rate < EASY_MAX:
        return 1
    if error_rate > HARD_MIN:
        return 3
    return 2


def run():
    from peewee import fn, Case
    from edubot.data.models.base import db
    from edubot.data.models.attempts import Attempts
    from edubot.data.models.questions import Questions

    if db.is_closed():
        db.connect(reuse_if_open=True)

    # taxa de erro por questão, numa query agregada
    rows = (Attempts
            .select(Attempts.question_id,
                    fn.COUNT(Attempts.attempt_id).alias("total"),
                    fn.SUM(Case(None, [(Attempts.is_correct == False, 1)], 0)).alias("wrong"))
            .group_by(Attempts.question_id)
            .dicts())

    updated = 0
    seen = set()
    for r in rows:
        total = r["total"] or 0
        if total == 0:
            continue
        wrong = int(r["wrong"] or 0)
        level = _level(wrong / total)
        qid = r["question_id"]
        seen.add(qid)
        Questions.update(difficulty=level).where(Questions.question_id == qid).execute()
        updated += 1

    logger.info("Calibração concluída: %s questões calibradas por histórico "
                "(as demais permanecem em dificuldade 2).", updated)
    return updated


if __name__ == "__main__":
    run()
