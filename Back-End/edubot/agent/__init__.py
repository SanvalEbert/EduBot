# EduBot Agent (MELHORIA 4.3)
#
# Módulo isolado do agente pedagógico. Recebe o perfil completo do aluno
# (montado por api/services/student_context.py) e devolve uma recomendação
# estruturada.
#
# A chamada real ao AWS Bedrock (Claude Sonnet) ainda NÃO é feita: o cliente é
# mockado em agent.py, mas o prompt definitivo já está escrito e parametrizado
# em prompt.py e o mock devolve a resposta no MESMO formato da API real, de
# modo que ligar o Bedrock depois seja só trocar a implementação de
# BedrockClientMock por boto3 ("bedrock-runtime".invoke_model).
from .agent import get_recommendation, BEDROCK_MODEL_ID
# MELHORIA (OVA personalizada): agente de tool-use que monta a OVA de reforço.
from .personalized import run_personalized_ova_agent

__all__ = ["get_recommendation", "BEDROCK_MODEL_ID", "run_personalized_ova_agent"]
