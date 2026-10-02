FROM python:3.10-slim

WORKDIR /api

COPY . .

RUN pip install -r requirements.txt

# Fase 2 (A14): backend virou o pacote `edubot/`. WORKDIR /api (= Back-End) fica
# na raiz do pacote, então `python -m edubot.api.app` resolve os imports absolutos
# sem nenhum sys.path.append.
CMD [ "python", "-m", "edubot.api.app" ]
