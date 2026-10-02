# Import the main libraries
import logging
import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from flask_cors import CORS

# Import the API routes
from edubot.api.routes.loginRoute import app_login
from edubot.api.routes.ovaRoute import app_ova
from edubot.api.routes.courseRoute import app_course
from edubot.api.routes.interactionRoute import app_interaction
from edubot.api.routes.studentRoute import app_student
from edubot.api.routes.questionRoute import app_question
# MELHORIA (4.1/4.2/4.3): rastreamento de consumo e agente EduBot
from edubot.api.routes.progressRoute import app_progress
from edubot.api.routes.edubotRoute import app_edubot
# MELHORIA (OVA personalizada): agente de tool-use que monta OVA de reforço
from edubot.api.routes.personalizedOvaRoute import app_personalized_ova
# MELHORIA (Roteiro Cena 4): painel do tutor + central de alertas
from edubot.api.routes.tutorRoute import app_tutor
# ETAPA 3: eventos de aprendizado (D.1) e consentimento/LGPD (D.5)
from edubot.api.routes.eventRoute import app_event
from edubot.api.routes.consentRoute import app_consent
# ETAPA 4: revisão espaçada (D.3)
from edubot.api.routes.reviewRoute import app_review
# ETAPA 5: voz do EduBot (V.1 — Polly + visemas)
from edubot.api.routes.speechRoute import app_speech
# ETAPA 7 (Plano 2): tendência de domínio do aluno (H.1)
from edubot.api.routes.masteryRoute import app_mastery
# ETAPA 8 (Plano 2): gamificação (XP, nível, sequência, conquistas, ranking)
from edubot.api.routes.gamificationRoute import app_gamification
# ETAPA 9 (Plano 2): metas semanais (E.3)
from edubot.api.routes.goalsRoute import app_goals
# INTEGRACAO EXTERNA: API publica /api/v1 para sistemas parceiros (chave + escopo)
from edubot.api.routes.publicApiRoute import app_public_api
# INTEGRACAO EXTERNA: coleta de eventos do edubot-tracker.js (/api/v1/collect)
from edubot.api.routes.collectRoute import app_collect

# Create the Flask app and configure CORS
# A.3: CORS restrito à(s) origem(ns) do frontend por env (antes liberava
# qualquer origem). Default = Apache local do compose; produção define
# EDUBOT_CORS_ORIGINS. "*" ainda é possível explicitamente para dev.
#
# A API publica de parceiros (/api/v1) fica DELIBERADAMENTE fora dessa lista: ela
# e' autenticada por chave de API, e uma chave so' existe em servidor. Se o CORS
# permitisse chamar /api/v1 de um front de terceiro, a chave teria de viajar no
# JavaScript do navegador - ou seja, ficaria publica. A integracao do parceiro e'
# servidor-a-servidor (o PHP dele chama o Flask); CORS nao se aplica.
#
# A unica excecao e' POST /api/v1/collect (collectRoute), que existe justamente
# para ser chamado do navegador: ele abre CORS na propria rota, e a chave dele
# (escopo events:write) e' publica por desenho - so' grava, nunca le.
app = Flask(__name__)
_cors_origins = os.environ.get("EDUBOT_CORS_ORIGINS", "http://localhost:8010")
cors = CORS(app, origins=[o.strip() for o in _cors_origins.split(",") if o.strip()])

logger = logging.getLogger("edubot.api")


# Error handler global (A10) — respostas de erro coerentes em JSON.
#
# Antes, cada rota capturava só PeeweeException e devolvia 501 (Not Implemented);
# qualquer outro erro (payload malformado, IndexError do envelope [data], etc.)
# virava um 500 sem corpo. Estes handlers garantem que TODA falha volte como
# JSON com o status HTTP correto.
@app.errorhandler(HTTPException)
def handle_http_exception(err):
    return jsonify({"error": err.description, "status": err.code}), err.code


@app.errorhandler(Exception)
def handle_unexpected_exception(err):
    # Erros inesperados: loga o stack trace no servidor, devolve 500 genérico
    # ao cliente (sem vazar detalhes internos).
    logger.exception("Erro não tratado na requisição")
    return jsonify({"error": "Erro interno do servidor", "status": 500}), 500

# Register the API routes as blueprints
app.register_blueprint(app_login)
app.register_blueprint(app_ova)
app.register_blueprint(app_course)
app.register_blueprint(app_interaction)
app.register_blueprint(app_student)
app.register_blueprint(app_question)
app.register_blueprint(app_progress)
app.register_blueprint(app_edubot)
app.register_blueprint(app_personalized_ova)
app.register_blueprint(app_tutor)
app.register_blueprint(app_event)
app.register_blueprint(app_consent)
app.register_blueprint(app_review)
app.register_blueprint(app_speech)
app.register_blueprint(app_mastery)
app.register_blueprint(app_gamification)
app.register_blueprint(app_goals)
app.register_blueprint(app_public_api)
app.register_blueprint(app_collect)

# Start the application
if __name__ == "__main__":
    import os

    # Scheduler in-process (A13). Só no processo que serve de fato: sob o
    # reloader do Flask debug, o Werkzeug reexecuta o script num filho com
    # WERKZEUG_RUN_MAIN=true — iniciar só ali evita rodar a varredura duas vezes.
    debug = os.environ.get("EDUBOT_DEBUG", "1").lower() in ("1", "true", "on", "yes")
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not debug:
        from edubot.services.scheduler import start_scheduler
        start_scheduler()

    app.run(debug=debug, host="0.0.0.0", port=8090)
