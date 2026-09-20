from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from dealhunter.modelos import ConfigAlerta, ItemWishlist, PontoHistorico

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DADOS = RAIZ / "data"
ARQUIVO_WISHLIST = PASTA_DADOS / "wishlist.json"
ARQUIVO_HISTORICO = PASTA_DADOS / "historico.csv"
ARQUIVO_CONFIG = PASTA_DADOS / "config.json"


def _garantir_pasta() -> None:
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)


def carregar_wishlist() -> list[ItemWishlist]:
    if not ARQUIVO_WISHLIST.exists():
        return []
    try:
        bruto = json.loads(ARQUIVO_WISHLIST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    itens: list[ItemWishlist] = []
    if not isinstance(bruto, list):
        return []
    for item in bruto:
        if not isinstance(item, dict) or "jogo" not in item:
            continue
        itens.append(
            {
                "jogo": str(item["jogo"]),
                "preco_desejado": float(item.get("preco_desejado") or 0),
                "steam_app_id": str(item.get("steam_app_id") or ""),
                "cheapshark_id": str(item.get("cheapshark_id") or ""),
            }
        )
    return itens


def salvar_wishlist(itens: list[ItemWishlist]) -> None:
    _garantir_pasta()
    ARQUIVO_WISHLIST.write_text(
        json.dumps(itens, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def adicionar_wishlist(item: ItemWishlist) -> None:
    atual = carregar_wishlist()
    chave = item["jogo"].casefold()
    atual = [existente for existente in atual if existente["jogo"].casefold() != chave]
    atual.append(item)
    salvar_wishlist(atual)


def remover_wishlist(nome: str) -> None:
    chave = nome.casefold()
    salvar_wishlist(
        [item for item in carregar_wishlist() if item["jogo"].casefold() != chave]
    )


def registrar_historico(jogo: str, loja: str, preco: float) -> None:
    _garantir_pasta()
    novo_arquivo = not ARQUIVO_HISTORICO.exists()
    with ARQUIVO_HISTORICO.open("a", encoding="utf-8", newline="") as arquivo:
        writer = csv.writer(arquivo)
        if novo_arquivo:
            writer.writerow(["data", "jogo", "loja", "preco"])
        writer.writerow(
            [
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                jogo,
                loja,
                f"{preco:.2f}",
            ]
        )


def historico_do_jogo(jogo: str) -> list[PontoHistorico]:
    if not ARQUIVO_HISTORICO.exists():
        return []
    pontos: list[PontoHistorico] = []
    with ARQUIVO_HISTORICO.open(encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha.get("jogo", "").casefold() != jogo.casefold():
                continue
            try:
                pontos.append(
                    {
                        "data": linha["data"],
                        "jogo": linha["jogo"],
                        "loja": linha["loja"],
                        "preco": float(linha["preco"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
    return pontos


def _config_padrao() -> ConfigAlerta:
    return {"discord_webhook": "", "desconto_minimo": 50.0, "avisos": {}}


def carregar_config() -> ConfigAlerta:
    if not ARQUIVO_CONFIG.exists():
        return _config_padrao()
    try:
        bruto = json.loads(ARQUIVO_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _config_padrao()
    if not isinstance(bruto, dict):
        return _config_padrao()
    avisos_brutos = bruto.get("avisos") or {}
    avisos: dict[str, float] = {}
    if isinstance(avisos_brutos, dict):
        for jogo, preco in avisos_brutos.items():
            try:
                avisos[str(jogo)] = float(preco)
            except (TypeError, ValueError):
                continue
    return {
        "discord_webhook": str(bruto.get("discord_webhook") or ""),
        "desconto_minimo": float(bruto.get("desconto_minimo") or 50),
        "avisos": avisos,
    }


def salvar_config(config: ConfigAlerta) -> None:
    _garantir_pasta()
    ARQUIVO_CONFIG.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
