"""
Cria regras de roteamento de e-mail no Cloudflare (Email Routing) em lote.

Uso:
    python src/cloudflare_email_routing.py                # cria as regras da lista EMAILS
    python src/cloudflare_email_routing.py --list         # lista regras existentes
    python src/cloudflare_email_routing.py --dry-run      # mostra o que seria criado

Variaveis de ambiente (.env):
    CLOUDFLARE_API_TOKEN   -> token com permissao "Zone / Email Routing Rules: Edit"
    CLOUDFLARE_ZONE_ID     -> id da zona (dominio) no Cloudflare
    CLOUDFLARE_DEST_EMAIL  -> destino padrao (opcional, default abaixo)
"""

import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.cloudflare.com/client/v4"

def _clean(value):
    """Remove aspas e espacos que costumam vir coladas no .env."""
    if value is None:
        return None
    return value.strip().strip('"').strip("'").strip()


API_TOKEN = _clean(os.getenv("CLOUDFLARE_API_TOKEN"))
ZONE_ID = _clean(os.getenv("CLOUDFLARE_ZONE_ID"))
DESTINATION = _clean(os.getenv("CLOUDFLARE_DEST_EMAIL")) or "apogeunexus@gmail.com"

# ---------------------------------------------------------------------------
# Lista de e-mails a rotear. Todos apontam para DESTINATION.
# ---------------------------------------------------------------------------
EMAILS = [
    "tech-igor22@tech-tria-events.uk",
    "tech-igor33@tech-tria-events.uk",
]


def _headers():
    return {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }


def _check_env():
    missing = [n for n, v in (("CLOUDFLARE_API_TOKEN", API_TOKEN),
                              ("CLOUDFLARE_ZONE_ID", ZONE_ID)) if not v]
    if missing:
        sys.exit(f"[ERRO] Variaveis ausentes no .env: {', '.join(missing)}")


def _request(method, path, **kwargs):
    resp = requests.request(method, f"{API_BASE}{path}", headers=_headers(),
                            timeout=30, **kwargs)
    try:
        data = resp.json()
    except ValueError:
        resp.raise_for_status()
        raise
    if not data.get("success"):
        errs = "; ".join(f"{e.get('code')}: {e.get('message')}"
                         for e in data.get("errors", []))
        raise RuntimeError(errs or f"HTTP {resp.status_code}")
    return data


def check_credentials():
    """Diagnostica o token e o acesso a zona. Retorna True se estiver tudo ok."""
    masked = f"{API_TOKEN[:4]}...{API_TOKEN[-4:]} ({len(API_TOKEN)} chars)"
    print(f"Token   : {masked}")
    print(f"Zone ID : {ZONE_ID}")

    if len(API_TOKEN) == 37 and API_TOKEN.isalnum():
        print("\n[AVISO] Isso parece ser a Global API Key, nao um API Token.")
        print("        Crie um API Token em: My Profile > API Tokens > Create Token.")

    print("\n1) Verificando o token...")
    try:
        data = _request("GET", "/user/tokens/verify")
        print(f"   OK - status: {data['result'].get('status')}")
    except RuntimeError as exc:
        print(f"   FALHOU: {exc}")
        print("   -> O token e invalido, expirou ou foi copiado incompleto.")
        print("      Gere um novo em: dash.cloudflare.com > My Profile > API Tokens")
        print("      Permissoes necessarias:")
        print("        - Zone / Email Routing Rules  : Edit")
        print("        - Zone / Zone                 : Read")
        print("        - Account / Email Routing Addresses : Read (opcional)")
        return False

    print("2) Verificando acesso a zona...")
    try:
        zone = _request("GET", f"/zones/{ZONE_ID}")["result"]
        print(f"   OK - zona: {zone['name']} (conta: {zone['account']['id']})")
    except RuntimeError as exc:
        print(f"   FALHOU: {exc}")
        print("   -> O token e valido mas nao tem acesso a essa zona, ou o")
        print("      CLOUDFLARE_ZONE_ID esta errado. Pegue o Zone ID no painel do")
        print("      dominio (Visao geral, coluna da direita) e confira se o token")
        print("      inclui essa zona em 'Zone Resources'.")
        return False

    print("3) Verificando permissao de Email Routing...")
    try:
        _request("GET", f"/zones/{ZONE_ID}/email/routing/rules",
                 params={"per_page": 1})
        print("   OK")
    except RuntimeError as exc:
        print(f"   FALHOU: {exc}")
        print("   -> Falta a permissao 'Zone / Email Routing Rules' no token.")
        return False

    print("\nTudo certo.")
    return True


def list_rules():
    """Retorna todas as regras de roteamento da zona (paginado)."""
    rules, page = [], 1
    while True:
        data = _request("GET", f"/zones/{ZONE_ID}/email/routing/rules",
                        params={"page": page, "per_page": 50})
        rules.extend(data["result"])
        info = data.get("result_info") or {}
        if page >= (info.get("total_pages") or 1):
            break
        page += 1
    return rules


def existing_addresses(rules):
    """Extrai os enderecos 'to' ja configurados nas regras existentes."""
    found = set()
    for rule in rules:
        for matcher in rule.get("matchers") or []:
            if matcher.get("field") == "to" and matcher.get("value"):
                found.add(matcher["value"].lower())
    return found


def verify_destination(address):
    """Garante que o endereco de destino existe e esta verificado na conta."""
    account_id = _clean(os.getenv("CLOUDFLARE_ACCOUNT_ID"))
    if not account_id:
        return None  # sem account id nao da pra checar; segue mesmo assim
    try:
        data = _request("GET", f"/accounts/{account_id}/email/routing/addresses",
                        params={"per_page": 50})
    except RuntimeError as exc:
        # Checagem opcional: sem a permissao de conta seguimos sem validar.
        print(f"[AVISO] Nao foi possivel validar o destino ({exc}).")
        print("        Adicione 'Account / Email Routing Addresses: Read' ao token")
        print("        para habilitar essa checagem. Seguindo mesmo assim.")
        return None
    for dest in data["result"]:
        if dest["email"].lower() == address.lower():
            return bool(dest.get("verified"))
    return False


def create_rule(source, destination):
    payload = {
        "name": source,
        "enabled": True,
        "matchers": [{"type": "literal", "field": "to", "value": source}],
        "actions": [{"type": "forward", "value": [destination]}],
        "priority": 0,
    }
    return _request("POST", f"/zones/{ZONE_ID}/email/routing/rules",
                    json=payload)["result"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true",
                        help="apenas lista as regras existentes")
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra o que seria criado sem chamar a API de escrita")
    parser.add_argument("--check", action="store_true",
                        help="diagnostica token, zona e permissoes")
    parser.add_argument("--destination", default=DESTINATION,
                        help="e-mail de destino (default: %(default)s)")
    args = parser.parse_args()

    _check_env()

    if args.check:
        sys.exit(0 if check_credentials() else 1)

    try:
        rules = list_rules()
    except RuntimeError as exc:
        print(f"[ERRO] {exc}\n")
        check_credentials()
        sys.exit(1)

    if args.list:
        print(f"{len(rules)} regra(s) na zona {ZONE_ID}:")
        for r in rules:
            src = next((m.get("value") for m in r.get("matchers") or []
                        if m.get("field") == "to"), r.get("name"))
            dst = next((a.get("value") for a in r.get("actions") or []), [])
            status = "ativo" if r.get("enabled") else "desabilitado"
            print(f"  - {src} -> {', '.join(dst) if dst else '-'} ({status})")
        return

    verified = verify_destination(args.destination)
    if verified is False:
        sys.exit(f"[ERRO] Destino {args.destination} nao esta verificado no "
                 f"Cloudflare. Verifique em Email Routing > Enderecos de destino.")

    already = existing_addresses(rules)
    to_create = [e for e in EMAILS if e.lower() not in already]
    skipped = [e for e in EMAILS if e.lower() in already]

    for e in skipped:
        print(f"[SKIP] {e} ja possui regra")

    if args.dry_run:
        for e in to_create:
            print(f"[DRY-RUN] criaria {e} -> {args.destination}")
        print(f"\nTotal: {len(to_create)} a criar, {len(skipped)} ignorado(s).")
        return

    ok, fail = 0, 0
    for i, email in enumerate(to_create, 1):
        try:
            create_rule(email, args.destination)
            ok += 1
            print(f"[OK {i}/{len(to_create)}] {email} -> {args.destination}")
        except RuntimeError as exc:
            fail += 1
            print(f"[FALHA {i}/{len(to_create)}] {email}: {exc}")
        time.sleep(0.35)  # respeita o rate limit (~1200 req / 5 min)

    print(f"\nResumo: {ok} criada(s), {fail} falha(s), {len(skipped)} ignorada(s).")


if __name__ == "__main__":
    main()
