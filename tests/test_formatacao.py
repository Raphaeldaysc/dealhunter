from __future__ import annotations

from dealhunter.formatacao import (
    formatar_brl,
    misturar_sem_duplicar,
    mesmo_jogo,
    normalizar_titulo,
    oferta,
    preco_em_brl,
)
from dealhunter.servico import menor_oferta, status_wishlist


def test_formatar_brl_usa_virgula_decimal() -> None:
    assert formatar_brl(89.9) == "R$ 89,90"
    assert formatar_brl(1250.5) == "R$ 1.250,50"


def test_preco_em_brl_converte_so_usd() -> None:
    steam = oferta(
        titulo="Jogo",
        loja="Steam",
        preco_atual=100.0,
        preco_normal=200.0,
        desconto=50.0,
        link="https://store.steampowered.com",
        moeda="BRL",
    )
    cheapshark = oferta(
        titulo="Jogo",
        loja="Steam",
        preco_atual=10.0,
        preco_normal=20.0,
        desconto=50.0,
        link="https://cheapshark.com",
        moeda="USD",
    )
    assert preco_em_brl(steam, 5.5) == 100.0
    assert preco_em_brl(cheapshark, 5.5) == 55.0


def test_normalizar_titulo_remove_acento_e_pontuacao() -> None:
    assert normalizar_titulo("Cyberpunk 2077: Ultimate Edition") == (
        "cyberpunk 2077 ultimate edition"
    )
    assert normalizar_titulo("Pokémon Legends") == "pokemon legends"


def test_mesmo_jogo_rejeita_demo_e_outro_titulo() -> None:
    assert mesmo_jogo("Cyberpunk 2077", "Cyberpunk 2077")
    assert mesmo_jogo("Cyberpunk 2077", "Cyberpunk 2077 Ultimate Edition")
    assert not mesmo_jogo("Cyberpunk 2077", "Cyberpunk 2077 Demo")
    assert not mesmo_jogo("Hogwarts Legacy", "Dex Demo")


def test_misturar_sem_duplicar_por_titulo_e_loja() -> None:
    a = oferta(
        titulo="Hades",
        loja="Steam",
        preco_atual=20.0,
        preco_normal=40.0,
        desconto=50.0,
        link="https://a",
        moeda="BRL",
    )
    b = oferta(
        titulo="Hades",
        loja="Steam",
        preco_atual=18.0,
        preco_normal=40.0,
        desconto=55.0,
        link="https://b",
        moeda="BRL",
    )
    c = oferta(
        titulo="Hades",
        loja="GOG",
        preco_atual=22.0,
        preco_normal=40.0,
        desconto=45.0,
        link="https://c",
        moeda="BRL",
    )
    juntos = misturar_sem_duplicar([a], [b, c])
    assert len(juntos) == 2
    assert juntos[0]["link"] == "https://a"
    assert juntos[1]["loja"] == "GOG"


def test_menor_oferta_ignora_preco_zero_se_houver_pago() -> None:
    gratis = oferta(
        titulo="Jogo",
        loja="GOG",
        preco_atual=0.0,
        preco_normal=0.0,
        desconto=100.0,
        link="https://gog",
        moeda="BRL",
    )
    pago = oferta(
        titulo="Jogo",
        loja="Steam",
        preco_atual=50.0,
        preco_normal=100.0,
        desconto=50.0,
        link="https://steam",
        moeda="BRL",
    )
    melhor = menor_oferta([gratis, pago], taxa=1.0)
    assert melhor is not None
    assert melhor["loja"] == "Steam"


def test_status_wishlist() -> None:
    assert status_wishlist(0.0, 80.0) == "gratis"
    assert status_wishlist(74.9, 80.0) == "compre"
    assert status_wishlist(85.0, 80.0) == "quase"
    assert status_wishlist(120.0, 80.0) == "espera"
