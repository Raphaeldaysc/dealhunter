from __future__ import annotations

import httpx

from dealhunter.formatacao import formatar_brl

WEBHOOK_PREFIXOS = (
    "https://discord.com/api/webhooks/",
    "https://discordapp.com/api/webhooks/",
)


def webhook_valido(url: str) -> bool:
    return url.startswith(WEBHOOK_PREFIXOS)


def enviar_alerta_discord(
    webhook: str,
    *,
    jogo: str,
    loja: str,
    preco: float,
    desconto: float,
    link: str,
    motivo: str,
) -> None:
    if not webhook_valido(webhook):
        raise ValueError("URL de webhook do Discord inválida.")
    payload = {
        "username": "DealHunter",
        "embeds": [
            {
                "title": jogo,
                "url": link,
                "color": 2013486,
                "description": motivo,
                "fields": [
                    {"name": "Preço", "value": formatar_brl(preco), "inline": True},
                    {"name": "Loja", "value": loja, "inline": True},
                    {"name": "Desconto", "value": f"{desconto:.0f}%", "inline": True},
                ],
            }
        ],
    }
    resposta = httpx.post(webhook, json=payload, timeout=15.0)
    resposta.raise_for_status()
