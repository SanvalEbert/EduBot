# MELHORIA (4.1/4.2) — Persistência do rastreamento de consumo.
#
# Antes destas rotas, read_time/perc_scrolled ficavam apenas no localStorage do
# navegador e as tabelas ova_progress/resource_progress nunca eram escritas.
# Estas rotas fecham o ciclo frontend -> backend -> banco:
#
#   GET  /ova/<id>/resources   -> recursos do OVA + progresso do aluno logado
#   POST /progress/ova         -> upsert de leitura/scroll/conclusão do OVA
#   POST /progress/resource    -> upsert de consumo de um recurso (vídeo/podcast/atividade)
#
# Todas exigem o token emitido no login (@require_auth) — o aluno é resolvido
# do token (g.student), nunca do payload, para impedir escrita em nome de outro.

from flask import Blueprint, request, g
from flask_cors import cross_origin
from edubot.api.http import get_payload
from peewee import PeeweeException, fn
import json
import datetime

from edubot.data.models.ovas import OVAs
from edubot.data.models.resources import Resources
from edubot.data.models.ova_progress import OVAProgress
from edubot.data.models.ova_section_progress import OVASectionProgress
from edubot.data.models.resource_progress import ResourceProgress

from edubot.api.auth import require_auth
from edubot.api.http import get_lang
from edubot.i18n import tr
from edubot.services.proactivity import trigger_evaluation
from edubot.services.events import emit as emit_event
from edubot.services.media import merge_bitmap, COVERAGE_COMPLETED_PERC
from edubot.services.reinforcement import suggest_for_ova

app_progress = Blueprint("progress", __name__)


# Lists every resource of an OVA along with the logged student's progress.
# The frontend uses this to render the media section (video/audio players).
@app_progress.route("/ova/<int:ova_id>/resources", methods=["GET"])
@cross_origin()
@require_auth
def ova_resources(ova_id):
    try:
        lang = get_lang()
        resource_list = []
        for resource in Resources.select().where(Resources.ova_id == ova_id):
            rp = ResourceProgress.get_or_none(
                (ResourceProgress.student_id == g.student) &
                (ResourceProgress.resource_id == resource.resource_id))
            resource_list.append({
                "resource_id": resource.resource_id,
                "resource_type": resource.resource_type,
                "resource_title": tr(resource.resource_title, resource.resource_title_en, lang),
                "resource_url": resource.resource_url,
                "media_type": resource.media_type,
                "duration_seconds": resource.duration_seconds,
                "perc_consumed": rp.perc_consumed if rp else 0,
                "seconds_consumed": rp.seconds_consumed if rp else 0,
                "completed": bool(rp.completed) if rp else False,
                # Fase 1: consumo real. O player usa `coverage_bitmap` para
                # retomar a cobertura já conquistada (sem recontar) e
                # `last_position_seconds` para oferecer "continuar de onde parou".
                "watched_seconds": rp.watched_seconds if rp else 0,
                "coverage_perc": rp.coverage_perc if rp else 0,
                "coverage_bitmap": (rp.coverage_bitmap if rp else None),
                "last_position_seconds": (rp.last_position_seconds if rp else None)
            })
        return json.dumps(resource_list), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


# Upserts the per-OVA reading progress.
#
# CONTRATO NOVO (A1) — tempo de leitura por DELTA, acumulado no servidor:
#   seconds_delta : segundos lidos DESDE o último sync (o servidor SOMA).
# O front envia o delta a cada ~15s e um último no unload. Antes o front
# mandava o tempo ABSOLUTO da sessão e o backend fazia max(): ler 10min hoje e
# 10min amanhã registrava 10min (a maior sessão), não 20 — a métrica central do
# rastreamento era estruturalmente errada.
#
# `read_time` (absoluto) ainda é aceito como caminho legado (leitor jQuery, que
# manda o valor absoluto): sem seconds_delta, cai no max() antigo até o legado
# ser aposentado (Fase 5). perc_scrolled continua sendo marca d'água (max).
@app_progress.route("/progress/ova", methods=["POST"])
@cross_origin()
@require_auth
def save_ova_progress():
    try:
        data = get_payload()
        ova = OVAs.get_or_none(OVAs.ova_id == data["ova_id"])
        if ova is None:
            return json.dumps({"Error": "Unknown ova_id"}), 400

        progress = OVAProgress.get_or_none(
            (OVAProgress.student_id == g.student) & (OVAProgress.ova_id == ova))
        was_completed = bool(progress.completed) if progress else False
        # delta é o caminho novo; read_time absoluto é o legado
        try:
            seconds_delta = data.get("seconds_delta")
            seconds_delta = max(0, int(seconds_delta)) if seconds_delta is not None else None
            read_time_abs = int(data.get("read_time", 0) or 0)
            perc_scrolled = min(100, int(data.get("perc_scrolled", 0) or 0))
        except (TypeError, ValueError):
            return json.dumps({"Error": "Campos numéricos inválidos"}), 400
        completed = bool(data.get("completed", False))

        if progress is None:
            initial_read = seconds_delta if seconds_delta is not None else read_time_abs
            OVAProgress.create(
                student_id=g.student, ova_id=ova,
                read_time=initial_read, perc_scrolled=perc_scrolled,
                completed=completed, last_access=datetime.datetime.now())
        else:
            # A.6: a acumulação de read_time é feita NO BANCO
            # (COALESCE(read_time,0) + delta), não em Python. Antes era
            # read-modify-write: dois syncs concorrentes (ex.: duas abas do mesmo
            # aluno) liam o mesmo valor e um sobrescrevia o outro, perdendo um
            # delta. COALESCE mantém a portabilidade SQLite/MySQL (evita NULL+n).
            # perc_scrolled/completed seguem por max do pré-read: uma corrida só
            # atrasa a marca d'água, que o próximo sync corrige (auto-heal).
            updates = {
                OVAProgress.perc_scrolled: max(progress.perc_scrolled or 0, perc_scrolled),
                OVAProgress.completed: bool(progress.completed) or completed,
                OVAProgress.last_access: datetime.datetime.now(),
            }
            if seconds_delta is not None:
                # acumula (contrato novo) — atômico
                updates[OVAProgress.read_time] = fn.COALESCE(OVAProgress.read_time, 0) + seconds_delta
            else:
                # legado: valor absoluto, nunca retrocede
                updates[OVAProgress.read_time] = max(progress.read_time or 0, read_time_abs)
            (OVAProgress
             .update(updates)
             .where((OVAProgress.student_id == g.student) & (OVAProgress.ova_id == ova))
             .execute())

        # A13 — proatividade por evento: ao CONCLUIR um OVA (transição), o agente
        # reavalia o aluno e pode empurrar o próximo passo (ex.: quiz pendente,
        # trilha mínima) sem esperar clique. Só na transição, não a cada delta,
        # para não repetir a montagem cara do perfil (A9).
        now_completed = completed or perc_scrolled >= 90
        if now_completed and not was_completed:
            # D.1 — `completed` na transição de conclusão: alimenta a contagem
            # por verbo e a janela de engajamento do outcome (B.6).
            emit_event(g.student, "completed", "ova", ova.ova_id,
                       perc=perc_scrolled)
            trigger_evaluation(g.student, lang=get_lang(), trigger_type="ova_completed")
            # Fase 4 — gatilho 2 do reforço: avalia as competências DESTE OVA
            # (não a mais fraca global), para o reforço ser sobre o que o aluno
            # acabou de estudar. Best-effort, já isolado dentro do serviço.
            suggest_for_ova(g.student.student_id, ova.ova_id)
            # G.1 (Plano 2) — concluir um módulo é esforço: concede XP (1x por
            # OVA/dia). Best-effort, flag-guarded dentro de award.
            try:
                from edubot.services.gamification import award, check_achievements
                award(g.student.student_id, "modulo_concluido", "ova", ova.ova_id)
                check_achievements(g.student.student_id)
            except Exception:
                pass
        # G.3 — ler/estudar conta para a sequência (dia de estudo), independentemente
        # de concluir. Idempotente por dia; best-effort.
        try:
            from edubot.services.gamification import register_daily_activity
            register_daily_activity(g.student.student_id)
        except Exception:
            pass
        return json.dumps("Progress saved"), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


# Upserts the consumption of one resource:
#   video    -> tempo assistido REAL + cobertura da linha do tempo (Fase 1)
#   podcast  -> seconds_consumed (listening time) + perc/completed when known
#   atividade-> completed (checklist button)
#
# CONTRATO NOVO (Plano de Rastreabilidade — Fase 1), todos os campos OPCIONAIS
# (degradação segura: um front antigo continua funcionando com os 3 de sempre):
#   watched_seconds_delta : segundos assistidos DESDE o último sync (o servidor
#                           SOMA, atomicamente — mesmo padrão do read_time).
#   coverage_bitmap       : 100 baldes '0'/'1' ACUMULADOS na sessão; o servidor
#                           faz OR com o salvo e recalcula coverage_perc.
#   last_position_s       : onde o player parou (retomada + ponto de abandono).
#   playback_rate         : velocidade de reprodução corrente.
#
# `perc_consumed` continua sendo aceito e guardado como POSIÇÃO máxima (legado):
# quem quer saber consumo de verdade lê coverage_perc/watched_seconds.
@app_progress.route("/progress/resource", methods=["POST"])
@cross_origin()
@require_auth
def save_resource_progress():
    try:
        data = get_payload()
        resource = Resources.get_or_none(Resources.resource_id == data["resource_id"])
        if resource is None:
            return json.dumps({"Error": "Unknown resource_id"}), 400

        rp = ResourceProgress.get_or_none(
            (ResourceProgress.student_id == g.student) &
            (ResourceProgress.resource_id == resource))
        try:
            perc = min(100, int(data.get("perc_consumed", 0) or 0))
            seconds = int(data.get("seconds_consumed", 0) or 0)
            watched_delta = max(0, int(data.get("watched_seconds_delta", 0) or 0))
            last_position = data.get("last_position_s")
            last_position = max(0, int(last_position)) if last_position is not None else None
            playback_rate = data.get("playback_rate")
            playback_rate = float(playback_rate) if playback_rate is not None else None
        except (TypeError, ValueError):
            return json.dumps({"Error": "Campos numéricos inválidos"}), 400
        completed = bool(data.get("completed", False))

        merged_bitmap, coverage_perc = merge_bitmap(
            rp.coverage_bitmap if rp else None, data.get("coverage_bitmap"))
        # Cobertura real manda na conclusão de vídeo/podcast; a flag explícita do
        # cliente (ex.: botão "concluir atividade", evento `ended`) segue valendo.
        completed = completed or coverage_perc >= COVERAGE_COMPLETED_PERC

        now = datetime.datetime.now()
        if rp is None:
            ResourceProgress.create(
                student_id=g.student, resource_id=resource,
                perc_consumed=perc, seconds_consumed=seconds,
                completed=completed, last_access=now,
                watched_seconds=watched_delta, coverage_bitmap=merged_bitmap,
                coverage_perc=coverage_perc,
                last_position_seconds=last_position,
                max_position_seconds=last_position,
                playback_rate_last=playback_rate)
        else:
            # watched_seconds acumula NO BANCO (COALESCE + delta), como o
            # read_time do OVA: dois syncs concorrentes (duas abas) não se
            # sobrescrevem. As demais colunas são marca d'água/último valor,
            # cuja pior consequência numa corrida é atrasar um sync (auto-heal).
            updates = {
                ResourceProgress.perc_consumed: max(rp.perc_consumed or 0, perc),
                ResourceProgress.seconds_consumed: max(rp.seconds_consumed or 0, seconds),
                ResourceProgress.completed: bool(rp.completed) or completed,
                ResourceProgress.last_access: now,
                ResourceProgress.coverage_bitmap: merged_bitmap,
                ResourceProgress.coverage_perc: max(rp.coverage_perc or 0, coverage_perc),
            }
            if watched_delta:
                updates[ResourceProgress.watched_seconds] = (
                    fn.COALESCE(ResourceProgress.watched_seconds, 0) + watched_delta)
            if last_position is not None:
                updates[ResourceProgress.last_position_seconds] = last_position
                updates[ResourceProgress.max_position_seconds] = max(
                    rp.max_position_seconds or 0, last_position)
            if playback_rate is not None:
                updates[ResourceProgress.playback_rate_last] = playback_rate
            (ResourceProgress
             .update(updates)
             .where((ResourceProgress.student_id == g.student) &
                    (ResourceProgress.resource_id == resource))
             .execute())
        return json.dumps("Resource progress saved"), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500


# Máximo de seções aceitas num lote — um OVA real tem poucas dezenas; o limite
# só evita que um cliente defeituoso mande um payload gigante.
MAX_SECTIONS_PER_BATCH = 60


# Plano de Rastreabilidade — Fase 2: leitura por SEÇÃO do OVA.
#
#   POST /progress/ova-section
#   body: {ova_id, sections: [{section_id, section_index, seconds_delta,
#                              max_scroll_perc, visits_delta}, ...]}
#
# Mesmo contrato de acumulação do /progress/ova (o servidor SOMA os deltas), só
# que por seção — é o que responde "ONDE o aluno travou", e não apenas "quanto
# ele leu". O lote existe porque o leitor sincroniza várias seções de uma vez.
@app_progress.route("/progress/ova-section", methods=["POST"])
@cross_origin()
@require_auth
def save_ova_section_progress():
    try:
        data = get_payload()
        ova = OVAs.get_or_none(OVAs.ova_id == data.get("ova_id"))
        if ova is None:
            return json.dumps({"Error": "Unknown ova_id"}), 400

        sections = data.get("sections")
        if not isinstance(sections, list):
            return json.dumps({"Error": "Campo 'sections' deve ser uma lista"}), 400

        now = datetime.datetime.now()
        saved = 0
        for item in sections[:MAX_SECTIONS_PER_BATCH]:
            if not isinstance(item, dict):
                continue
            section_id = str(item.get("section_id") or "").strip()[:120]
            if not section_id:
                continue
            try:
                seconds_delta = max(0, int(item.get("seconds_delta", 0) or 0))
                visits_delta = max(0, int(item.get("visits_delta", 0) or 0))
                section_index = int(item.get("section_index", 0) or 0)
                scroll_perc = min(100, max(0, int(item.get("max_scroll_perc", 0) or 0)))
            except (TypeError, ValueError):
                continue  # item ruim não derruba o lote (mesma política de /events)

            row = OVASectionProgress.get_or_none(
                (OVASectionProgress.student_id == g.student) &
                (OVASectionProgress.ova_id == ova) &
                (OVASectionProgress.section_id == section_id))
            if row is None:
                OVASectionProgress.create(
                    student_id=g.student, ova_id=ova, section_id=section_id,
                    section_index=section_index, active_seconds=seconds_delta,
                    max_scroll_perc=scroll_perc, visits=visits_delta,
                    last_access=now)
            else:
                # Acumulação NO BANCO (COALESCE + delta): duas abas do mesmo OVA
                # somam em vez de se sobrescrever — igual ao read_time (A.6).
                (OVASectionProgress
                 .update({
                     OVASectionProgress.active_seconds:
                         fn.COALESCE(OVASectionProgress.active_seconds, 0) + seconds_delta,
                     OVASectionProgress.visits:
                         fn.COALESCE(OVASectionProgress.visits, 0) + visits_delta,
                     OVASectionProgress.max_scroll_perc:
                         max(row.max_scroll_perc or 0, scroll_perc),
                     OVASectionProgress.section_index: section_index,
                     OVASectionProgress.last_access: now,
                 })
                 .where((OVASectionProgress.student_id == g.student) &
                        (OVASectionProgress.ova_id == ova) &
                        (OVASectionProgress.section_id == section_id))
                 .execute())
            saved += 1

        return json.dumps({"saved": saved}), 200
    except PeeweeException as err:
        return json.dumps({"Error": f"{err}"}), 500
