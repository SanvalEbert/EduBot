"""Scheduler in-process do EduBot (A13).

Roda a varredura da turma periodicamente (por padrão 1×/dia), avaliando as
regras de cada aluno e criando intervenções/alertas — a camada proativa que não
depende de clique. Usa APScheduler em processo, suficiente para 1 réplica de
protótipo. Para multi-réplica, mover para um worker/cron dedicado (documentado
na auditoria).

Ativação por ambiente (não liga sozinho em import/teste):
  EDUBOT_SCHEDULER=on                     -> liga o agendamento
  EDUBOT_SCHEDULER_HOUR=3                 -> hora do job diário (cron)
  EDUBOT_SCHEDULER_INTERVAL_MINUTES=10    -> se definido, roda a cada N min
                                            (modo demo, tem precedência)
"""
import logging
import os

logger = logging.getLogger("edubot.scheduler")

_scheduler = None


def _run_sweep():
    """Executa a varredura numa conexão própria (thread do scheduler)."""
    from edubot.data.models.base import db
    from edubot.services.proactivity import run_class_evaluation
    try:
        if db.is_closed():
            db.connect(reuse_if_open=True)
        created = run_class_evaluation()
        logger.info("Varredura EduBot concluída: %s intervenções/alertas criados.", created)
    except Exception:
        logger.exception("Falha na varredura agendada do EduBot.")
    finally:
        if not db.is_closed():
            db.close()


def start_scheduler():
    """Inicia o scheduler (idempotente). Retorna a instância ou None se desligado
    ou se o APScheduler não estiver instalado."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    if os.environ.get("EDUBOT_SCHEDULER", "").lower() not in ("1", "true", "on", "yes"):
        logger.info("Scheduler EduBot desativado (defina EDUBOT_SCHEDULER=on para ligar).")
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("APScheduler não instalado; scheduler desativado. "
                       "Instale com `pip install APScheduler`.")
        return None

    sched = BackgroundScheduler(daemon=True)
    interval = os.environ.get("EDUBOT_SCHEDULER_INTERVAL_MINUTES")
    if interval:
        sched.add_job(_run_sweep, "interval", minutes=int(interval),
                      id="edubot_sweep", replace_existing=True)
        logger.info("Scheduler EduBot iniciado (a cada %s min).", interval)
    else:
        hour = int(os.environ.get("EDUBOT_SCHEDULER_HOUR", "3"))
        sched.add_job(_run_sweep, "cron", hour=hour,
                      id="edubot_sweep", replace_existing=True)
        logger.info("Scheduler EduBot iniciado (diário às %02d:00).", hour)

    sched.start()
    _scheduler = sched
    return sched
