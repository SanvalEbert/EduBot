# MELHORIA (Roteiro Cena 4) — Recomendação de conteúdo EXTERNO.
#
# Além de remediar com o banco interno, o EduBot sugere materiais de fora da
# plataforma (artigos científicos) por competência, atendendo ao "explorar bases
# de dados científicas" do roteiro.
#
# Usa a API pública da Crossref (sem chave) — apenas leitura, com timeout curto e
# cache em memória por consulta. Se a rede falhar, devolve lista vazia (a tela
# simplesmente não mostra a seção).
import json
import urllib.parse
import urllib.request

CROSSREF_URL = "https://api.crossref.org/works"
TIMEOUT_S = 6
# "mailto" é a etiqueta de boa cidadania pedida pela Crossref (pool educado).
USER_AGENT = "EduBot/1.0 (mailto:edubot@example.edu)"

_cache = {}


def search_external(query, limit=3):
    """Busca artigos científicos relacionados a `query`. Retorna uma lista de
    dicts {titulo, url, fonte, ano} (no máximo `limit`)."""
    query = (query or "").strip()
    if not query:
        return []

    key = (query.lower(), limit)
    if key in _cache:
        return _cache[key]

    params = urllib.parse.urlencode({
        "query.bibliographic": query,
        "rows": limit,
        "select": "title,URL,published,container-title",
    })
    req = urllib.request.Request(f"{CROSSREF_URL}?{params}", headers={"User-Agent": USER_AGENT})

    out = []
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8", "ignore"))
        for item in data.get("message", {}).get("items", []):
            titulo = (item.get("title") or [None])[0]
            if not titulo:
                continue
            ano = None
            published = item.get("published") or {}
            parts = published.get("date-parts") or [[None]]
            if parts and parts[0]:
                ano = parts[0][0]
            fonte = (item.get("container-title") or ["Crossref"])[0]
            out.append({
                "titulo": titulo,
                "url": item.get("URL"),
                "fonte": fonte,
                "ano": ano,
            })
    except Exception as err:  # noqa: BLE001 — fonte externa é best-effort
        print(f"[external_sources] Crossref indisponível ({err}).")
        out = []

    _cache[key] = out
    return out
