from __future__ import annotations

import re
import unicodedata

from dealhunter.modelos import Oferta

_STOP = {"the", "a", "an", "of", "and"}
_EDICOES = {
    "edition",
    "goty",
    "complete",
    "definitive",
    "standard",
    "ultimate",
    "deluxe",
    "windows",
    "pc",
    "game",
}
_EXTRAS_PROIBIDOS = {
    "demo",
    "soundtrack",
    "ost",
    "prologue",
    "playtest",
    "beta",
    "sfx",
    "pack",
    "dlc",
    "bundle",
}


def formatar_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl_html(valor: float) -> str:
    return formatar_brl(valor).replace("$", "&#36;")


def brl_md(valor: float) -> str:
    return formatar_brl(valor).replace("$", r"\$")


def formatar_usd(valor: float) -> str:
    return f"US$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def preco_em_brl(oferta: Oferta, taxa: float) -> float:
    if oferta["moeda"] == "BRL":
        return float(oferta["preco_atual"])
    return float(oferta["preco_atual"]) * taxa


def preco_normal_brl(oferta: Oferta, taxa: float) -> float:
    if oferta["moeda"] == "BRL":
        return float(oferta["preco_normal"])
    return float(oferta["preco_normal"]) * taxa


def chave_jogo(item: Oferta) -> tuple[str, str]:
    return item["titulo"].casefold(), item["loja"].casefold()


def misturar_sem_duplicar(*listas: list[Oferta]) -> list[Oferta]:
    vistos: set[tuple[str, str]] = set()
    resultado: list[Oferta] = []
    for lista in listas:
        for item in lista:
            chave = chave_jogo(item)
            if chave in vistos:
                continue
            vistos.add(chave)
            resultado.append(item)
    return resultado


def oferta(
    *,
    titulo: str,
    loja: str,
    preco_atual: float,
    preco_normal: float,
    desconto: float,
    link: str,
    moeda: str,
    thumb: str = "",
) -> Oferta:
    return {
        "titulo": titulo,
        "loja": loja,
        "preco_atual": preco_atual,
        "preco_normal": preco_normal,
        "desconto": desconto,
        "link": link,
        "moeda": moeda,
        "thumb": thumb,
    }


def normalizar_titulo(titulo: str) -> str:
    texto = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    texto = texto.casefold()
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return " ".join(texto.split())


def _tokens(titulo: str) -> set[str]:
    return {
        parte
        for parte in normalizar_titulo(titulo).split()
        if parte not in _STOP and len(parte) > 1
    }


def mesmo_jogo(escolhido: str, encontrado: str) -> bool:
    alvo = normalizar_titulo(escolhido)
    outro = normalizar_titulo(encontrado)
    if not alvo or not outro:
        return False
    if alvo == outro:
        return True
    if alvo not in outro:
        return False
    resto = outro.replace(alvo, " ", 1)
    extras = {parte for parte in resto.split() if parte not in _STOP} - _EDICOES
    if extras & _EXTRAS_PROIBIDOS:
        return False
    return len(extras) <= 1


def pontuar_candidato(nome: str, termo: str) -> tuple[int, int, int]:
    normal_nome = normalizar_titulo(nome)
    normal_termo = normalizar_titulo(termo)
    extras = _tokens(nome) - _tokens(termo) - _EDICOES
    if normal_nome == normal_termo:
        return (0, 0, 0)
    if extras & _EXTRAS_PROIBIDOS:
        return (8, len(extras), len(normal_nome))
    if normal_nome.startswith(normal_termo):
        return (1, len(extras), len(normal_nome))
    if normal_termo in normal_nome:
        return (2, len(extras), len(normal_nome))
    if mesmo_jogo(termo, nome):
        return (3, len(extras), len(normal_nome))
    return (9, len(extras), len(normal_nome))
