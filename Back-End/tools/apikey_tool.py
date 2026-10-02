"""Gestão das chaves de API dos parceiros (criar, listar, revogar).

A chave em claro aparece UMA única vez — na criação. O banco guarda só o
SHA-256, então não existe comando "mostrar a chave do fulano": se o parceiro
perder, revoga-se a antiga e emite-se outra. Isso é proposital, não uma lacuna.

Uso (com a stack de pé):

    # criar
    docker exec -it ova_back_end python -m tools.apikey_tool criar \\
        --nome "Piloto UFBA" \\
        --escopos catalog:read,tracking:read,metrics:read \\
        --dias 90 --notas "contato: fulano@ufba.br"

    # listar (nunca mostra segredo)
    docker exec -it ova_back_end python -m tools.apikey_tool listar

    # revogar (por prefixo, que é o que aparece no `listar`)
    docker exec -it ova_back_end python -m tools.apikey_tool revogar --prefixo ek_live_3f9aK2

    # escopos disponíveis
    docker exec -it ova_back_end python -m tools.apikey_tool escopos

    # chave de coleta para o edubot-tracker.js (só grava; sozinha, sem leitura)
    docker exec -it ova_back_end python -m tools.apikey_tool criar \\
        --nome "Material de teste Lucas" --escopos events:write --dias 30
"""
import argparse
import datetime
import sys


def _parse_scopes(raw):
    """Valida os escopos contra o catálogo. Um escopo digitado errado seria
    aceito em silêncio pelo CSV e só apareceria como 403 inexplicável semanas
    depois — melhor falhar aqui."""
    from edubot.api.apikey import SCOPES
    pedidos = [s.strip() for s in (raw or "").split(",") if s.strip()]
    invalidos = [s for s in pedidos if s not in SCOPES]
    if invalidos:
        print(f"ERRO: escopo(s) desconhecido(s): {', '.join(invalidos)}", file=sys.stderr)
        print(f"Válidos: {', '.join(SCOPES)}", file=sys.stderr)
        sys.exit(1)
    if not pedidos:
        print("ERRO: informe ao menos um escopo (--escopos).", file=sys.stderr)
        sys.exit(1)
    from edubot.api.apikey import READ_SCOPES
    if "events:write" in pedidos and READ_SCOPES.intersection(pedidos):
        print("ERRO: events:write não pode ser combinado com escopos de leitura.",
              file=sys.stderr)
        print("A chave de coleta fica no HTML do material, visível para qualquer "
              "visitante. Emita uma chave separada para ler.", file=sys.stderr)
        sys.exit(1)
    return pedidos


def criar(args):
    from edubot.api.apikey import generate_key, SCOPES
    from edubot.data.models.api_keys import ApiKeys

    escopos = _parse_scopes(args.escopos)
    raw, prefix, key_hash = generate_key()
    expires = (datetime.datetime.now() + datetime.timedelta(days=args.dias)) if args.dias else None

    ApiKeys.create(name=args.nome, key_prefix=prefix, key_hash=key_hash,
                   scopes=",".join(escopos), active=True,
                   created_at=datetime.datetime.now(), expires_at=expires,
                   notes=args.notas)

    print()
    print("=" * 72)
    print(f"  CHAVE CRIADA PARA: {args.nome}")
    print("=" * 72)
    print(f"  {raw}")
    print("=" * 72)
    print("  Copie AGORA e entregue por canal seguro. Ela não será exibida de novo.")
    print(f"  Escopos : {', '.join(escopos)}")
    print(f"  Expira  : {expires.strftime('%Y-%m-%d') if expires else 'sem validade definida'}")
    if "students:pii" in escopos:
        print()
        print("  ATENÇÃO: esta chave libera NOME e RA de aluno (dado pessoal).")
        print("  Registre a base legal e o contrato/termo com o parceiro.")
    if "events:write" in escopos:
        print()
        print("  Chave de COLETA: vai no HTML do material (data-key do")
        print("  edubot-tracker.js). É pública por desenho — só grava eventos.")
    print()


def listar(args):
    from edubot.data.models.api_keys import ApiKeys

    linhas = list(ApiKeys.select().order_by(ApiKeys.key_id))
    if not linhas:
        print("Nenhuma chave cadastrada.")
        return
    agora = datetime.datetime.now()
    print(f"{'ID':<4} {'PREFIXO':<18} {'NOME':<22} {'STATUS':<10} {'USOS':>6}  ESCOPOS")
    print("-" * 110)
    for k in linhas:
        if not k.active:
            status = "revogada"
        elif k.expires_at and k.expires_at < agora:
            status = "expirada"
        else:
            status = "ativa"
        print(f"{k.key_id:<4} {k.key_prefix:<18} {k.name[:21]:<22} {status:<10} "
              f"{k.request_count:>6}  {k.scopes}")
    print()
    print("Segredos não são armazenados em claro — por isso não aparecem aqui.")


def revogar(args):
    from edubot.data.models.api_keys import ApiKeys

    query = ApiKeys.update(active=False)
    if args.prefixo:
        query = query.where(ApiKeys.key_prefix == args.prefixo)
    elif args.id:
        query = query.where(ApiKeys.key_id == args.id)
    else:
        print("ERRO: informe --prefixo ou --id.", file=sys.stderr)
        sys.exit(1)
    n = query.execute()
    print(f"{n} chave(s) revogada(s)." if n else
          "Nenhuma chave encontrada com esse identificador.")


def escopos(args):
    from edubot.api.apikey import SCOPES
    print("Escopos disponíveis:\n")
    for nome, descricao in SCOPES.items():
        print(f"  {nome:<16} {descricao}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Chaves de API dos parceiros do EduBot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("criar", help="emite uma chave nova")
    p.add_argument("--nome", required=True, help="quem é o parceiro")
    p.add_argument("--escopos", required=True, help="CSV, ex: catalog:read,tracking:read")
    p.add_argument("--dias", type=int, default=None, help="validade em dias (padrão: sem validade)")
    p.add_argument("--notas", default=None, help="contato, nº do processo etc.")
    p.set_defaults(func=criar)

    p = sub.add_parser("listar", help="lista as chaves (sem segredos)")
    p.set_defaults(func=listar)

    p = sub.add_parser("revogar", help="desativa uma chave")
    p.add_argument("--prefixo", default=None)
    p.add_argument("--id", type=int, default=None)
    p.set_defaults(func=revogar)

    p = sub.add_parser("escopos", help="lista os escopos disponíveis")
    p.set_defaults(func=escopos)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
