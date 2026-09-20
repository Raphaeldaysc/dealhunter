from __future__ import annotations

from types import SimpleNamespace

from dealhunter.cotacao import cotacao_usd_brl
from dealhunter.discord_alerta import webhook_valido


def test_cotacao_usa_proxima_fonte_quando_awesomeapi_quebra(monkeypatch) -> None:
    import dealhunter.cotacao as cotacao

    def _quebra(_client: object) -> float:
        raise RuntimeError(
            "Falha ao consultar https://economia.awesomeapi.com.br/json/last/USD-BRL"
        )

    monkeypatch.setattr(cotacao, "ler_cache_cotacao", lambda: None)
    monkeypatch.setattr(cotacao, "salvar_cache_cotacao", lambda *_args: None)
    monkeypatch.setattr(cotacao, "_taxa_awesome", _quebra)
    monkeypatch.setattr(cotacao, "_taxa_open_er", lambda _client: 5.42)

    taxa, fonte = cotacao_usd_brl(SimpleNamespace())
    assert taxa == 5.42
    assert fonte == "ExchangeRate-API"


def test_webhook_discord_so_aceita_url_oficial() -> None:
    assert webhook_valido("https://discord.com/api/webhooks/123/abc")
    assert not webhook_valido("https://example.com/webhooks/123")
