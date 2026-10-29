from __future__ import annotations

import httpx
import pytest
import respx

from dealhunter import afiliados

FEED = {
    "source": "byus-affiliate-engine",
    "generatedAt": "2026-10-29T16:00:00.000Z",
    "ref": "dealhunter",
    "niche": "games",
    "count": 2,
    "niches": [{"slug": "games", "label": "Games", "count": 2}],
    "disclosureText": "Este conteúdo contém links de afiliado.",
    "attributionNote": "Use trackedUrl.",
    "offers": [
        {
            "slug": "mercadolivre-mlb3712345678",
            "title": "Console PlayStation 5 Slim Digital 1TB",
            "marketplace": "Mercado Livre",
            "niche": "games",
            "trackedUrl": "https://shop.getbyus.io/ir/mercadolivre-mlb3712345678?ref=dealhunter",
            "affiliateUrl": "https://meli.la/1eERqGB",
            "rating": 4.5,
            "reviewCount": 1943,
            "price": {
                "show": True,
                "amountMinor": 134801,
                "currency": "BRL",
                "note": "fresh",
                "originalAmountMinor": 169800,
                "discountPercent": 21,
            },
        },
        {
            "slug": "mercadolivre-mlb0000000001",
            "title": "Gift Card Steam R$ 100",
            "marketplace": "Mercado Livre",
            "niche": "games",
            "trackedUrl": "https://shop.getbyus.io/ir/mercadolivre-mlb0000000001?ref=dealhunter",
            "price": {"show": False, "currency": "BRL", "note": "not_observed"},
        },
    ],
}

URL = "http://127.0.0.1:4040/v1/offers/feed"


@respx.mock
def test_buscar_feed_pede_nicho_games_e_canal_dealhunter() -> None:
    rota = respx.get(URL).mock(return_value=httpx.Response(200, json=FEED))

    with httpx.Client() as client:
        dados = afiliados.buscar_feed(client, limite=2)

    assert rota.called
    params = rota.calls[0].request.url.params
    assert params["niche"] == "games"
    assert params["ref"] == "dealhunter"
    assert params["limit"] == "2"
    assert params["sort"] == "score"
    assert dados["count"] == 2


@respx.mock
def test_ordenar_invalido_cai_para_score() -> None:
    rota = respx.get(URL).mock(return_value=httpx.Response(200, json=FEED))

    with httpx.Client() as client:
        afiliados.buscar_feed(client, ordenar="aleatorio")

    assert rota.calls[0].request.url.params["sort"] == "score"


@respx.mock
def test_feed_fora_do_ar_levanta_erro_explicito() -> None:
    respx.get(URL).mock(return_value=httpx.Response(503))

    with httpx.Client() as client, pytest.raises(afiliados.FeedIndisponivel):
        afiliados.buscar_feed(client)


@respx.mock
def test_json_invalido_nao_quebra_a_pagina() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, text="<html>erro</html>"))

    with httpx.Client() as client, pytest.raises(afiliados.FeedIndisponivel):
        afiliados.buscar_feed(client)


def test_ofertas_descarta_item_sem_link_clicavel() -> None:
    feed = {
        "offers": [
            FEED["offers"][0],
            {"title": "sem link"},
            "lixo",
        ]
    }
    assert len(afiliados.ofertas(feed)) == 1
    assert afiliados.ofertas({}) == []


def test_link_prefere_o_rastreado_e_cai_no_oficial() -> None:
    com_rastreio = FEED["offers"][0]
    assert afiliados.link_da_oferta(com_rastreio).endswith("?ref=dealhunter")

    so_oficial = {"affiliateUrl": "https://meli.la/1eERqGB"}
    assert afiliados.link_da_oferta(so_oficial) == "https://meli.la/1eERqGB"

    # portal local em http tambem vale (o clique precisa ser contado)
    assert afiliados.link_da_oferta({"trackedUrl": "http://localhost:3101/ir/x"}) == (
        "http://localhost:3101/ir/x"
    )

    assert afiliados.link_da_oferta({"trackedUrl": "javascript:alert(1)"}) == ""
    assert afiliados.link_da_oferta({}) == ""


def test_preco_formatado_em_real_e_preco_nao_observado() -> None:
    assert afiliados.preco_texto(FEED["offers"][0]) == "R$ 1.348,01"
    assert afiliados.preco_original_texto(FEED["offers"][0]) == "R$ 1.698,00"
    assert afiliados.desconto_pct(FEED["offers"][0]) == 21

    sem_preco = FEED["offers"][1]
    assert afiliados.preco_texto(sem_preco) == "Ver preço no site"
    assert afiliados.preco_original_texto(sem_preco) == ""
    assert afiliados.desconto_pct(sem_preco) is None
    assert afiliados.preco_texto({}) == "Ver preço no site"


def test_rotulos_de_origem_e_avaliacao() -> None:
    assert afiliados.origem_texto(FEED["offers"][0]) == "Mercado Livre · games"
    assert afiliados.avaliacao_texto(FEED["offers"][0]) == "4,5 ★ (1.943)"
    assert afiliados.avaliacao_texto({}) == ""
    assert afiliados.aviso(FEED).startswith("Este conteúdo")
    assert "links de afiliado" in afiliados.aviso({})


def test_resolver_url_prefere_argumento_e_depois_ambiente(monkeypatch) -> None:
    monkeypatch.delenv(afiliados.VARIAVEL_URL, raising=False)
    assert afiliados.resolver_url() == afiliados.URL_PADRAO

    monkeypatch.setenv(afiliados.VARIAVEL_URL, "https://feed.exemplo/v1/offers/feed")
    assert afiliados.resolver_url() == "https://feed.exemplo/v1/offers/feed"
    assert afiliados.resolver_url("https://outro.exemplo/x") == "https://outro.exemplo/x"
    assert afiliados.resolver_url("   ") == "https://feed.exemplo/v1/offers/feed"
