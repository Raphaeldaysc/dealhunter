from typing import TypedDict


class Oferta(TypedDict):
    titulo: str
    loja: str
    preco_atual: float
    preco_normal: float
    desconto: float
    link: str
    moeda: str
    thumb: str


class Candidato(TypedDict):
    nome: str
    steam_app_id: str
    cheapshark_id: str
    thumb: str


class ItemWishlist(TypedDict):
    jogo: str
    preco_desejado: float
    steam_app_id: str
    cheapshark_id: str


class ConfigAlerta(TypedDict):
    discord_webhook: str
    desconto_minimo: float
    avisos: dict[str, float]


class PontoHistorico(TypedDict):
    data: str
    jogo: str
    loja: str
    preco: float
