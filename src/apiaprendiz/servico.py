from __future__ import annotations

from collections.abc import Callable

import httpx

from apiaprendiz.busca import buscar_candidatos, comparar_jogo
from apiaprendiz.cliente import criar_cliente
from apiaprendiz.cotacao import cotacao_usd_brl
from apiaprendiz.fontes import (
    buscar_deals_cheapshark,
    buscar_steam_lista,
    catalogo_gog,
    jogos_epic,
    mapear_lojas,
)
from apiaprendiz.formatacao import misturar_sem_duplicar, preco_em_brl, preco_normal_brl
from apiaprendiz.modelos import Candidato, ItemWishlist, Oferta, PontoHistorico
from apiaprendiz.persistencia import (
    adicionar_wishlist,
    carregar_wishlist,
    historico_do_jogo,
    registrar_historico,
    remover_wishlist,
)


def _seguro(acao: Callable[[], list[Oferta]]) -> list[Oferta]:
    try:
        return acao()
    except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError, RuntimeError):
        return []


def melhores_promocoes(client: httpx.Client) -> list[Oferta]:
    lojas: dict[str, str] = {}
    try:
        lojas = mapear_lojas(client)
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        lojas = {}

    steam = _seguro(lambda: buscar_steam_lista(client, so_gratis=False, max_itens=80))
    cheapshark = _seguro(
        lambda: buscar_deals_cheapshark(client, lojas, max_paginas=3, so_gratis=False)
    )
    gog = _seguro(
        lambda: catalogo_gog(client, extras={"discounted": "eq:true"}, max_paginas=2)
    )
    epic_promo: list[Oferta] = []
    try:
        _gratis, _proximos, epic_promo = jogos_epic(client)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError):
        epic_promo = []

    gog_paga = [item for item in gog if item["preco_atual"] > 0]
    juntos = misturar_sem_duplicar(steam, epic_promo, gog_paga, cheapshark)
    juntos.sort(key=lambda item: float(item["desconto"]), reverse=True)
    return juntos


def jogos_gratis(client: httpx.Client) -> tuple[list[Oferta], list[Oferta], list[Oferta]]:
    lojas: dict[str, str] = {}
    try:
        lojas = mapear_lojas(client)
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        lojas = {}

    epic_atuais: list[Oferta] = []
    epic_proximos: list[Oferta] = []
    try:
        epic_atuais, epic_proximos, _promo = jogos_epic(client)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError):
        pass

    cheapshark = _seguro(
        lambda: buscar_deals_cheapshark(client, lojas, max_paginas=2, so_gratis=True)
    )
    gog = _seguro(
        lambda: catalogo_gog(client, extras={"tags": "in:freegame"}, max_paginas=2)
    )
    steam_f2p = _seguro(lambda: buscar_steam_lista(client, so_gratis=True, max_itens=40))

    agora = misturar_sem_duplicar(epic_atuais, cheapshark)
    sempre = misturar_sem_duplicar(steam_f2p, gog)
    return agora, epic_proximos, sempre


def menor_oferta(ofertas: list[Oferta], taxa: float) -> Oferta | None:
    pagas = [item for item in ofertas if preco_em_brl(item, taxa) > 0]
    if pagas:
        return min(pagas, key=lambda item: preco_em_brl(item, taxa))
    if not ofertas:
        return None
    return min(ofertas, key=lambda item: preco_em_brl(item, taxa))


def economia(oferta_ref: Oferta, taxa: float) -> float:
    return max(preco_normal_brl(oferta_ref, taxa) - preco_em_brl(oferta_ref, taxa), 0.0)


def status_wishlist(preco_atual: float, desejado: float) -> str:
    if preco_atual <= 0:
        return "gratis"
    if preco_atual <= desejado:
        return "compre"
    if preco_atual <= desejado * 1.1:
        return "quase"
    return "espera"


def resumo_historico(pontos: list[PontoHistorico]) -> dict[str, float]:
    if not pontos:
        return {"atual": 0.0, "menor": 0.0, "maior": 0.0, "media": 0.0}
    precos = [ponto["preco"] for ponto in pontos]
    return {
        "atual": precos[-1],
        "menor": min(precos),
        "maior": max(precos),
        "media": sum(precos) / len(precos),
    }


__all__ = [
    "Candidato",
    "ItemWishlist",
    "Oferta",
    "PontoHistorico",
    "adicionar_wishlist",
    "buscar_candidatos",
    "carregar_wishlist",
    "comparar_jogo",
    "cotacao_usd_brl",
    "criar_cliente",
    "economia",
    "historico_do_jogo",
    "jogos_gratis",
    "melhores_promocoes",
    "menor_oferta",
    "preco_em_brl",
    "preco_normal_brl",
    "registrar_historico",
    "remover_wishlist",
    "resumo_historico",
    "status_wishlist",
]
