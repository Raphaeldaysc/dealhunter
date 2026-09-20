from __future__ import annotations

import re
import time
from html import unescape

import httpx

from dealhunter.cliente import get
from dealhunter.formatacao import misturar_sem_duplicar, oferta
from dealhunter.modelos import Oferta

CHEAPSHARK_DEALS = "https://www.cheapshark.com/api/1.0/deals"
CHEAPSHARK_STORES = "https://www.cheapshark.com/api/1.0/stores"
CHEAPSHARK_GAMES = "https://www.cheapshark.com/api/1.0/games"
EPIC_GRATIS = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
STEAM_BUSCA = "https://store.steampowered.com/search/results/"
STEAM_APPDETAILS = "https://store.steampowered.com/api/appdetails"
STEAM_STORESEARCH = "https://store.steampowered.com/api/storesearch/"
GOG_CATALOG = "https://catalog.gog.com/v1/catalog"

STEAM_POR_PAGINA = 100
GOG_POR_PAGINA = 48
CHEAPSHARK_POR_PAGINA = 60

LINHA_STEAM_RE = re.compile(
    r'<a[^>]*class="[^"]*search_result_row[\s\S]*?</a>',
    re.IGNORECASE,
)
APP_ID_RE = re.compile(r'data-ds-appid="(\d+)"')
TITULO_RE = re.compile(r'class="title">([^<]+)')
PRECO_FINAL_RE = re.compile(r'data-price-final="(\d+)"')
DESCONTO_RE = re.compile(r'discount_pct">\s*-?(\d+)\s*%')
PRECO_ORIGINAL_TXT_RE = re.compile(r'discount_original_price">([^<]+)')
HREF_APP_RE = re.compile(r'href="(https://store\.steampowered\.com/app/\d+[^"]*)"')
PRECO_BRL_TXT_RE = re.compile(r"R\$\s*([\d.]+),(\d{2})")
THUMB_RE = re.compile(r'<img[^>]+src="([^"]+)"')


def mapear_lojas(client: httpx.Client) -> dict[str, str]:
    lojas: dict[str, str] = {}
    for loja in get(client, CHEAPSHARK_STORES).json():
        if loja.get("isActive"):
            lojas[str(loja["storeID"])] = str(loja["storeName"])
    return lojas


def buscar_deals_cheapshark(
    client: httpx.Client,
    lojas: dict[str, str],
    *,
    max_paginas: int = 3,
    so_gratis: bool = False,
) -> list[Oferta]:
    itens: list[Oferta] = []
    pagina = 0
    while pagina < max_paginas:
        params: dict[str, object] = {
            "pageSize": CHEAPSHARK_POR_PAGINA,
            "pageNumber": pagina,
            "sortBy": "Savings",
        }
        if so_gratis:
            params["upperPrice"] = 0
        else:
            params["onSale"] = 1
        lote = get(client, CHEAPSHARK_DEALS, params=params).json()
        if not lote:
            break
        for deal in lote:
            preco_atual = float(deal["salePrice"])
            preco_normal = float(deal["normalPrice"])
            if so_gratis and preco_atual > 0:
                continue
            itens.append(
                oferta(
                    titulo=str(deal["title"]),
                    loja=lojas.get(str(deal["storeID"]), f"Loja {deal['storeID']}"),
                    preco_atual=preco_atual,
                    preco_normal=preco_normal,
                    desconto=float(deal["savings"]),
                    link=f"https://www.cheapshark.com/redirect?dealID={deal['dealID']}",
                    moeda="USD",
                    thumb=str(deal.get("thumb") or ""),
                )
            )
        if len(lote) < CHEAPSHARK_POR_PAGINA:
            break
        pagina += 1
        time.sleep(0.12)
    return itens


def slug_epic(element: dict[str, object]) -> str:
    catalog = element.get("catalogNs")
    if isinstance(catalog, dict):
        mappings = catalog.get("mappings") or []
        if isinstance(mappings, list) and mappings:
            slug = mappings[0].get("pageSlug")
            if slug:
                return str(slug)
    offers = element.get("offerMappings") or []
    if isinstance(offers, list) and offers:
        slug = offers[0].get("pageSlug")
        if slug:
            return str(slug)
    return str(element.get("productSlug") or element.get("urlSlug") or "")


def jogos_epic(
    client: httpx.Client,
) -> tuple[list[Oferta], list[Oferta], list[Oferta]]:
    elementos = (
        get(
            client,
            EPIC_GRATIS,
            params={"locale": "pt-BR", "country": "BR", "allowCountries": "BR"},
        )
        .json()
        .get("data", {})
        .get("Catalog", {})
        .get("searchStore", {})
        .get("elements", [])
    )
    atuais: list[Oferta] = []
    proximos: list[Oferta] = []
    promocoes: list[Oferta] = []

    for element in elementos:
        preco = element.get("price", {}).get("totalPrice", {})
        atual_centavos = int(preco.get("discountPrice") or 0)
        normal_centavos = int(preco.get("originalPrice") or 0)
        promotions = element.get("promotions") or {}
        offers = promotions.get("promotionalOffers") or []
        upcoming = promotions.get("upcomingPromotionalOffers") or []
        slug = slug_epic(element)
        link = (
            f"https://store.epicgames.com/pt-BR/p/{slug}"
            if slug
            else "https://store.epicgames.com/pt-BR/free-games"
        )
        desconto = 0.0
        if normal_centavos > 0:
            desconto = (1 - (atual_centavos / normal_centavos)) * 100
        imagens = element.get("keyImages") or []
        thumb = ""
        if isinstance(imagens, list) and imagens:
            thumb = str(imagens[0].get("url") or "")
        item = oferta(
            titulo=str(element.get("title", "Sem título")),
            loja="Epic Games Store",
            preco_atual=atual_centavos / 100,
            preco_normal=normal_centavos / 100,
            desconto=desconto,
            link=link,
            moeda="BRL",
            thumb=thumb,
        )
        if offers and atual_centavos == 0:
            atuais.append(item)
        elif offers and atual_centavos < normal_centavos:
            promocoes.append(item)
        elif upcoming:
            primeira = upcoming[0].get("promotionalOffers") or []
            vai_ser_gratis = any(
                int(oferta_ep.get("discountSetting", {}).get("discountPercentage", 1)) == 0
                for oferta_ep in primeira
            )
            if vai_ser_gratis:
                proximos.append(item)
    return atuais, proximos, promocoes


def _texto_brl_para_float(texto: str) -> float | None:
    achado = PRECO_BRL_TXT_RE.search(texto)
    if not achado:
        return None
    inteiro = achado.group(1).replace(".", "")
    return float(f"{inteiro}.{achado.group(2)}")


def parse_linhas_steam(html: str, so_gratis: bool) -> list[Oferta]:
    itens: list[Oferta] = []
    for bloco in LINHA_STEAM_RE.findall(html):
        app = APP_ID_RE.search(bloco)
        titulo = TITULO_RE.search(bloco)
        if not app or not titulo:
            continue
        href = HREF_APP_RE.search(bloco)
        link = (
            unescape(href.group(1)).split("?")[0]
            if href
            else f"https://store.steampowered.com/app/{app.group(1)}"
        )
        thumb_m = THUMB_RE.search(bloco)
        thumb = unescape(thumb_m.group(1)) if thumb_m else ""
        texto_preco = unescape(bloco)
        e_gratis = bool(
            re.search(r"Gratuito|Free to Play|Free To Play", texto_preco, re.I)
        )
        nome = unescape(titulo.group(1)).strip()
        if so_gratis:
            if e_gratis:
                itens.append(
                    oferta(
                        titulo=nome,
                        loja="Steam",
                        preco_atual=0.0,
                        preco_normal=0.0,
                        desconto=100.0,
                        link=link,
                        moeda="BRL",
                        thumb=thumb,
                    )
                )
            continue
        if e_gratis:
            continue
        final_centavos = PRECO_FINAL_RE.search(bloco)
        desconto = DESCONTO_RE.search(bloco)
        original_txt = PRECO_ORIGINAL_TXT_RE.search(bloco)
        if not final_centavos or not desconto:
            continue
        atual = int(final_centavos.group(1)) / 100
        if original_txt:
            normal = _texto_brl_para_float(unescape(original_txt.group(1))) or atual
        else:
            pct = int(desconto.group(1))
            normal = atual / (1 - pct / 100) if pct < 100 else atual
        itens.append(
            oferta(
                titulo=nome,
                loja="Steam",
                preco_atual=atual,
                preco_normal=normal,
                desconto=float(desconto.group(1)),
                link=link,
                moeda="BRL",
                thumb=thumb,
            )
        )
    return itens


def buscar_steam_lista(
    client: httpx.Client,
    *,
    so_gratis: bool,
    max_itens: int = 100,
) -> list[Oferta]:
    itens: list[Oferta] = []
    start = 0
    total: int | None = None
    params: dict[str, object] = {
        "cc": "BR",
        "l": "brazilian",
        "category1": 998,
        "infinite": 1,
        "count": STEAM_POR_PAGINA,
        "start": 0,
    }
    if so_gratis:
        params["maxprice"] = "free"
    else:
        params["specials"] = 1

    while len(itens) < max_itens:
        params["start"] = start
        dados = get(client, STEAM_BUSCA, params=params).json()
        if total is None:
            total = int(dados.get("total_count") or 0)
        html = dados.get("results_html") or ""
        lote = parse_linhas_steam(html, so_gratis=so_gratis)
        if not lote:
            break
        itens.extend(lote)
        start += STEAM_POR_PAGINA
        if total is not None and start >= total:
            break
        time.sleep(0.12)
    return misturar_sem_duplicar(itens)[:max_itens]


def catalogo_gog(
    client: httpx.Client,
    *,
    extras: dict[str, object],
    max_paginas: int = 2,
) -> list[Oferta]:
    itens: list[Oferta] = []
    pagina = 1
    total_paginas = 1
    while pagina <= min(total_paginas, max_paginas):
        params: dict[str, object] = {
            "limit": GOG_POR_PAGINA,
            "page": pagina,
            "order": "desc:trending",
            "productType": "in:game",
            "countryCode": "BR",
            "currencyCode": "BRL",
            **extras,
        }
        dados = get(client, GOG_CATALOG, params=params).json()
        total_paginas = int(dados.get("pages") or 1)
        for produto in dados.get("products") or []:
            price = produto.get("price") or {}
            final_money = price.get("finalMoney") or {}
            base_money = price.get("baseMoney") or {}
            atual = float(final_money.get("amount") or 0)
            normal = float(base_money.get("amount") or atual)
            currency = str(final_money.get("currency") or "USD")
            desconto = 0.0
            if normal > 0:
                desconto = (1 - atual / normal) * 100
            slug = produto.get("slug") or produto.get("id")
            capa = str(produto.get("coverVertical") or produto.get("coverHorizontal") or "")
            itens.append(
                oferta(
                    titulo=str(produto.get("title", "Sem título")),
                    loja="GOG",
                    preco_atual=atual,
                    preco_normal=normal,
                    desconto=desconto,
                    link=str(
                        produto.get("storeLink")
                        or f"https://www.gog.com/en/game/{slug}"
                    ),
                    moeda="BRL" if currency == "BRL" else "USD",
                    thumb=capa,
                )
            )
        pagina += 1
        time.sleep(0.12)
    return itens


def preco_steam_br(client: httpx.Client, app_id: str) -> Oferta | None:
    if not app_id:
        return None
    dados = get(
        client,
        STEAM_APPDETAILS,
        params={"appids": app_id, "cc": "BR", "l": "brazilian"},
    ).json()
    app = dados.get(str(app_id))
    if not app or not app.get("success"):
        return None
    info = app.get("data") or {}
    nome = str(info.get("name") or "Steam")
    header = str(info.get("header_image") or "")
    link = f"https://store.steampowered.com/app/{app_id}"
    if info.get("is_free"):
        return oferta(
            titulo=nome,
            loja="Steam",
            preco_atual=0.0,
            preco_normal=0.0,
            desconto=100.0,
            link=link,
            moeda="BRL",
            thumb=header,
        )
    overview = info.get("price_overview")
    if not isinstance(overview, dict):
        return None
    return oferta(
        titulo=nome,
        loja="Steam",
        preco_atual=int(overview.get("final") or 0) / 100,
        preco_normal=int(overview.get("initial") or 0) / 100,
        desconto=float(overview.get("discount_percent") or 0),
        link=link,
        moeda="BRL",
        thumb=header,
    )
