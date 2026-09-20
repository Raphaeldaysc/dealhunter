from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from apiaprendiz.cliente import get

TTL_COTACAO = 5 * 60
CACHE_COTACAO = Path(__file__).resolve().parents[2] / ".cache_cotacao.json"

AWESOME_USD_BRL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
OPEN_ER_USD = "https://open.er-api.com/v6/latest/USD"
FAWAZ_USD = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.min.json"
FRANKFURTER_USD_BRL = "https://api.frankfurter.app/latest"
BCB_PTAX = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
)


def ler_cache_cotacao() -> tuple[float, str] | None:
    if not CACHE_COTACAO.exists():
        return None
    try:
        cache = json.loads(CACHE_COTACAO.read_text(encoding="utf-8"))
        if time.time() - float(cache["ts"]) < TTL_COTACAO:
            return float(cache["taxa"]), f"{cache['fonte']} (cache {TTL_COTACAO // 60} min)"
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    return None


def salvar_cache_cotacao(taxa: float, fonte: str) -> None:
    CACHE_COTACAO.write_text(
        json.dumps({"ts": time.time(), "taxa": taxa, "fonte": fonte}),
        encoding="utf-8",
    )


def cotacao_usd_brl(client: httpx.Client) -> tuple[float, str]:
    cache = ler_cache_cotacao()
    if cache is not None:
        return cache

    fontes: list[tuple[str, Callable[[httpx.Client], float]]] = [
        ("AwesomeAPI (comercial)", _taxa_awesome),
        ("ExchangeRate-API", _taxa_open_er),
        ("currency-api (diária)", _taxa_fawaz),
        ("Banco Central PTAX", _taxa_bcb),
        ("Frankfurter / BCE", _taxa_frankfurter),
    ]
    erros: list[str] = []
    for nome, coletor in fontes:
        try:
            taxa = coletor(client)
            if taxa > 0:
                salvar_cache_cotacao(taxa, nome)
                return taxa, nome
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError) as erro:
            erros.append(f"{nome}: {erro}")

    raise RuntimeError("Nenhuma API de cotação respondeu. " + " | ".join(erros))


def _taxa_awesome(client: httpx.Client) -> float:
    dados = get(client, AWESOME_USD_BRL).json()["USDBRL"]
    return float(dados["bid"])


def _taxa_open_er(client: httpx.Client) -> float:
    dados = get(client, OPEN_ER_USD).json()
    if dados.get("result") != "success":
        raise ValueError("resposta inválida")
    return float(dados["rates"]["BRL"])


def _taxa_fawaz(client: httpx.Client) -> float:
    return float(get(client, FAWAZ_USD).json()["usd"]["brl"])


def _taxa_frankfurter(client: httpx.Client) -> float:
    dados = get(client, FRANKFURTER_USD_BRL, params={"from": "USD", "to": "BRL"}).json()
    return float(dados["rates"]["BRL"])


def _taxa_bcb(client: httpx.Client) -> float:
    fim = datetime.now()
    inicio = fim - timedelta(days=10)
    dados = get(
        client,
        BCB_PTAX,
        params={
            "@dataInicial": inicio.strftime("'%m-%d-%Y'"),
            "@dataFinalCotacao": fim.strftime("'%m-%d-%Y'"),
            "$top": "1",
            "$orderby": "dataHoraCotacao desc",
            "$format": "json",
        },
    ).json()
    return float(dados["value"][0]["cotacaoVenda"])
