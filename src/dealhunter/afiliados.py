"""Ofertas com comissão do portal by.us (nicho games).

DealHunter responde "onde está mais barato" com Steam, Epic, GOG e CheapShark.
Nenhuma dessas lojas tem programa de afiliado acessível por link: o usuário
compra e o projeto não recebe nada. O que **paga** em games — console, gift
card, controle, cadeira, placa de vídeo — vive no feed do by.us, e cada item já
vem com `trackedUrl`: o clique é contado no portal e o visitante cai no link
oficial do programa (Mercado Livre / Shopee / Amazon), que é quem credita a
comissão.

Regra de ouro deste módulo: **não monta link de afiliado**. Ele usa o que o
feed entrega. Inventar parâmetro de afiliado na URL é o caminho mais curto para
comissão não creditada (ou para violar os termos do programa).

Degradação: se o feed não estiver configurado ou estiver fora do ar, a função
levanta `FeedIndisponivel` — a página mostra o aviso e o resto do DealHunter
(que não depende disso) segue funcionando.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# Local (docker compose) por padrão; em produção aponte para o portal público.
URL_PADRAO = "http://127.0.0.1:4040/v1/offers/feed"
VARIAVEL_URL = "BYUS_FEED_URL"
VARIAVEL_TOKEN = "BYUS_FEED_TOKEN"
NICHO_PADRAO = "games"
REF_PADRAO = "dealhunter"
TIMEOUT = 8.0

#: Ordens aceitas pelo feed (senão o portal usa curadoria por score).
ORDENS = frozenset({"score", "desconto", "preco", "recentes"})


class FeedIndisponivel(RuntimeError):
    """Feed do by.us fora do ar, sem URL configurada ou resposta inválida."""


def resolver_url(explicita: str | None = None) -> str:
    """URL do feed: argumento > variável de ambiente > padrão local."""
    for candidata in (explicita, os.getenv(VARIAVEL_URL)):
        if candidata and candidata.strip():
            return candidata.strip()
    return URL_PADRAO


def _cabecalhos() -> dict[str, str]:
    token = (os.getenv(VARIAVEL_TOKEN) or "").strip()
    return {"X-BYUS-Feed-Token": token} if token else {}


def buscar_feed(
    client: httpx.Client,
    *,
    url: str | None = None,
    nicho: str = NICHO_PADRAO,
    limite: int = 12,
    ref: str = REF_PADRAO,
    ordenar: str = "score",
    min_desconto: int | None = None,
) -> dict[str, Any]:
    """Busca o feed e devolve o dicionário cru (ofertas + aviso + nichos)."""
    if ordenar not in ORDENS:
        ordenar = "score"

    params: dict[str, str] = {
        "niche": nicho,
        "limit": str(max(1, min(int(limite), 100))),
        "ref": ref,
        "sort": ordenar,
    }
    if min_desconto is not None and min_desconto > 0:
        params["minDiscount"] = str(int(min_desconto))

    destino = resolver_url(url)
    try:
        resposta = client.get(destino, params=params, timeout=TIMEOUT, headers=_cabecalhos())
        resposta.raise_for_status()
        dados = resposta.json()
    except httpx.HTTPError as erro:
        raise FeedIndisponivel(f"Feed indisponível em {destino}: {erro}") from erro
    except ValueError as erro:  # JSON inválido
        raise FeedIndisponivel(f"Resposta inválida do feed em {destino}") from erro

    if not isinstance(dados, dict):
        raise FeedIndisponivel(f"Resposta inesperada do feed em {destino}")
    return dados


def ofertas(feed: dict[str, Any]) -> list[dict[str, Any]]:
    """Só o que dá para clicar: item com `trackedUrl` (clique contado)."""
    itens = feed.get("offers")
    if not isinstance(itens, list):
        return []
    validos: list[dict[str, Any]] = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        if not link_da_oferta(item):
            continue
        validos.append(item)
    return validos


def link_da_oferta(item: dict[str, Any]) -> str:
    """Link rastreado do portal; cai no link oficial se o portal não expôs."""
    for chave in ("trackedUrl", "affiliateUrl"):
        valor = item.get(chave)
        if isinstance(valor, str) and valor.startswith("https://"):
            return valor
    return ""


def _brl(centavos: int) -> str:
    reais = centavos / 100
    texto = f"{reais:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def preco_texto(item: dict[str, Any]) -> str:
    """Preço observado, ou o convite honesto quando o preço não foi observado."""
    preco = item.get("price") or {}
    if not isinstance(preco, dict) or not preco.get("show"):
        return "Ver preço no site"
    valor = preco.get("amountMinor")
    if isinstance(valor, int) and valor > 0:
        return _brl(valor)
    return "Ver preço no site"


def preco_original_texto(item: dict[str, Any]) -> str:
    """Preço "de" só quando existe desconto real observado."""
    preco = item.get("price") or {}
    if not isinstance(preco, dict):
        return ""
    original = preco.get("originalAmountMinor")
    if isinstance(original, int) and original > 0 and preco.get("show"):
        return _brl(original)
    return ""


def desconto_pct(item: dict[str, Any]) -> int | None:
    preco = item.get("price") or {}
    if not isinstance(preco, dict):
        return None
    valor = preco.get("discountPercent")
    return valor if isinstance(valor, int) and valor > 0 else None


def avaliacao_texto(item: dict[str, Any]) -> str:
    """Nota + volume de avaliações, quando observados."""
    nota = item.get("rating")
    total = item.get("reviewCount")
    if not isinstance(nota, (int, float)):
        return ""
    rotulo = f"{nota:.1f}".replace(".", ",") + " ★"
    if isinstance(total, int) and total > 0:
        rotulo += f" ({total:,})".replace(",", ".")
    return rotulo


def origem_texto(item: dict[str, Any]) -> str:
    marketplace = item.get("marketplace") or "Marketplace"
    nicho = item.get("niche") or NICHO_PADRAO
    return f"{marketplace} · {nicho}"


def aviso(feed: dict[str, Any]) -> str:
    texto = feed.get("disclosureText")
    if isinstance(texto, str) and texto.strip():
        return texto.strip()
    return (
        "Este conteúdo contém links de afiliado. Podemos receber comissão por "
        "compras feitas através deles, sem custo adicional para você."
    )
