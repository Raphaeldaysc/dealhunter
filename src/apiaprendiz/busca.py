from __future__ import annotations

import httpx

from apiaprendiz.cliente import get
from apiaprendiz.fontes import (
    CHEAPSHARK_GAMES,
    GOG_CATALOG,
    STEAM_STORESEARCH,
    mapear_lojas,
    preco_steam_br,
)
from apiaprendiz.formatacao import misturar_sem_duplicar, mesmo_jogo, oferta, pontuar_candidato
from apiaprendiz.modelos import Candidato, Oferta

GOG_AJAX = "https://embed.gog.com/games/ajax/filtered"


def buscar_candidatos(client: httpx.Client, termo: str, limite: int = 8) -> list[Candidato]:
    termo = termo.strip()
    if not termo:
        return []

    por_chave: dict[str, Candidato] = {}

    try:
        cheapshark = get(
            client,
            CHEAPSHARK_GAMES,
            params={"title": termo, "limit": limite},
        ).json()
        if isinstance(cheapshark, list):
            for jogo in cheapshark:
                nome = str(jogo.get("external") or "").strip()
                if not nome:
                    continue
                steam_id = str(jogo.get("steamAppID") or "")
                chave = steam_id or nome.casefold()
                atual = por_chave.get(chave)
                candidato: Candidato = {
                    "nome": nome,
                    "steam_app_id": steam_id,
                    "cheapshark_id": str(jogo.get("gameID") or ""),
                    "thumb": str(jogo.get("thumb") or ""),
                }
                if atual is None:
                    por_chave[chave] = candidato
                else:
                    if not atual["cheapshark_id"]:
                        atual["cheapshark_id"] = candidato["cheapshark_id"]
                    if not atual["thumb"]:
                        atual["thumb"] = candidato["thumb"]
    except (httpx.HTTPError, TypeError, ValueError):
        pass

    try:
        steam = get(
            client,
            STEAM_STORESEARCH,
            params={"term": termo, "l": "brazilian", "cc": "BR"},
        ).json()
        for item in steam.get("items") or []:
            tipo = str(item.get("type") or "app")
            if tipo not in {"app", "dlc"}:
                continue
            nome = str(item.get("name") or "").strip()
            steam_id = str(item.get("id") or "")
            if not nome:
                continue
            chave = steam_id or nome.casefold()
            capa = str(item.get("tiny_image") or item.get("img") or "")
            if chave in por_chave:
                if not por_chave[chave]["steam_app_id"]:
                    por_chave[chave]["steam_app_id"] = steam_id
                if not por_chave[chave]["thumb"]:
                    por_chave[chave]["thumb"] = capa
            else:
                por_chave[chave] = {
                    "nome": nome,
                    "steam_app_id": steam_id,
                    "cheapshark_id": "",
                    "thumb": capa,
                }
    except (httpx.HTTPError, TypeError, ValueError, KeyError):
        pass

    ordenados = sorted(
        por_chave.values(),
        key=lambda item: pontuar_candidato(item["nome"], termo),
    )
    return ordenados[:limite]


def deals_cheapshark_jogo(client: httpx.Client, game_id: str) -> list[Oferta]:
    if not game_id:
        return []
    dados = get(client, CHEAPSHARK_GAMES, params={"id": game_id}).json()
    info = dados.get("info") or {}
    titulo = str(info.get("title") or "Jogo")
    thumb = str(info.get("thumb") or "")
    lojas = mapear_lojas(client)
    ofertas: list[Oferta] = []
    for deal in dados.get("deals") or []:
        ofertas.append(
            oferta(
                titulo=titulo,
                loja=lojas.get(str(deal.get("storeID")), f"Loja {deal.get('storeID')}"),
                preco_atual=float(deal.get("price") or 0),
                preco_normal=float(deal.get("retailPrice") or 0),
                desconto=float(deal.get("savings") or 0),
                link=f"https://www.cheapshark.com/redirect?dealID={deal.get('dealID')}",
                moeda="USD",
                thumb=thumb,
            )
        )
    return ofertas


def _oferta_gog_catalogo(produto: dict[str, object], termo: str) -> Oferta | None:
    titulo = str(produto.get("title", "Sem título"))
    if not mesmo_jogo(termo, titulo):
        return None
    price = produto.get("price") or {}
    if not isinstance(price, dict):
        return None
    final_money = price.get("finalMoney") or {}
    base_money = price.get("baseMoney") or {}
    if not isinstance(final_money, dict) or not isinstance(base_money, dict):
        return None
    atual = float(final_money.get("amount") or 0)
    normal = float(base_money.get("amount") or atual)
    currency = str(final_money.get("currency") or "USD")
    desconto = 0.0
    if normal > 0:
        desconto = (1 - atual / normal) * 100
    slug = produto.get("slug") or produto.get("id")
    return oferta(
        titulo=titulo,
        loja="GOG",
        preco_atual=atual,
        preco_normal=normal,
        desconto=desconto,
        link=str(produto.get("storeLink") or f"https://www.gog.com/en/game/{slug}"),
        moeda="BRL" if currency == "BRL" else "USD",
        thumb=str(produto.get("coverVertical") or ""),
    )


def _oferta_gog_ajax(produto: dict[str, object], termo: str) -> Oferta | None:
    titulo = str(produto.get("title", "Sem título"))
    if not mesmo_jogo(termo, titulo):
        return None
    price = produto.get("price") or {}
    if not isinstance(price, dict):
        return None
    atual_txt = str(price.get("finalAmount") or price.get("amount") or "0")
    normal_txt = str(price.get("baseAmount") or atual_txt)
    try:
        atual = float(atual_txt.replace(",", "."))
        normal = float(normal_txt.replace(",", "."))
    except ValueError:
        return None
    if atual >= 100 and normal >= 100 and atual == int(atual):
        atual /= 100
        normal /= 100
    desconto = float(price.get("discountPercentage") or 0)
    slug = produto.get("slug") or produto.get("id")
    return oferta(
        titulo=titulo,
        loja="GOG",
        preco_atual=atual,
        preco_normal=normal,
        desconto=desconto,
        link=str(produto.get("url") or f"https://www.gog.com/en/game/{slug}"),
        moeda="BRL" if "R$" in str(price.get("symbol") or "") else "USD",
        thumb=str(produto.get("image") or ""),
    )


def ofertas_gog_por_nome(client: httpx.Client, termo: str) -> list[Oferta]:
    ofertas: list[Oferta] = []
    dados = get(
        client,
        GOG_CATALOG,
        params={
            "query": termo,
            "limit": 48,
            "productType": "in:game",
            "countryCode": "BR",
            "currencyCode": "BRL",
        },
    ).json()
    for produto in dados.get("products") or []:
        if isinstance(produto, dict):
            item = _oferta_gog_catalogo(produto, termo)
            if item is not None:
                ofertas.append(item)
    if ofertas:
        return ofertas

    ajax = get(
        client,
        GOG_AJAX,
        params={"mediaType": "game", "search": termo, "limit": 20},
    ).json()
    for produto in ajax.get("products") or []:
        if isinstance(produto, dict):
            item = _oferta_gog_ajax(produto, termo)
            if item is not None:
                ofertas.append(item)
    return ofertas


def comparar_jogo(client: httpx.Client, candidato: Candidato) -> list[Oferta]:
    ofertas: list[Oferta] = []

    if candidato["cheapshark_id"]:
        try:
            ofertas.extend(deals_cheapshark_jogo(client, candidato["cheapshark_id"]))
        except (httpx.HTTPError, TypeError, ValueError, KeyError):
            pass

    if candidato["steam_app_id"]:
        try:
            steam_br = preco_steam_br(client, candidato["steam_app_id"])
            if steam_br is not None:
                ofertas = [item for item in ofertas if item["loja"] != "Steam"]
                ofertas.insert(0, steam_br)
        except (httpx.HTTPError, TypeError, ValueError, KeyError):
            pass

    try:
        ofertas.extend(ofertas_gog_por_nome(client, candidato["nome"]))
    except (httpx.HTTPError, TypeError, ValueError, KeyError):
        pass

    return [
        item
        for item in misturar_sem_duplicar(ofertas)
        if mesmo_jogo(candidato["nome"], item["titulo"])
    ]
