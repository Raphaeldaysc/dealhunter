from __future__ import annotations

import time

import httpx

TIMEOUT = httpx.Timeout(15.0, read=45.0)
HTTP_SEM_RETRY = frozenset({400, 401, 403, 404, 405, 410, 422})
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
COOKIES = {
    "birthtime": "0",
    "lastagecheckage": "1-0-1990",
    "wants_mature_content": "1",
    "mature_content": "1",
}


def criar_cliente() -> httpx.Client:
    return httpx.Client(
        timeout=TIMEOUT,
        headers=HEADERS,
        cookies=COOKIES,
        follow_redirects=True,
    )


def get(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, object] | None = None,
    tentativas: int = 5,
) -> httpx.Response:
    ultimo_erro: Exception | None = None
    for tentativa in range(tentativas):
        try:
            resposta = client.get(url, params=params)
            if resposta.status_code == 429:
                ultimo_erro = httpx.HTTPStatusError(
                    f"HTTP 429 em {url}",
                    request=resposta.request,
                    response=resposta,
                )
                time.sleep(1.5 * (tentativa + 1))
                continue
            resposta.raise_for_status()
            return resposta
        except httpx.HTTPStatusError as erro:
            ultimo_erro = erro
            if erro.response.status_code in HTTP_SEM_RETRY:
                raise
            time.sleep(0.8 * (tentativa + 1))
        except httpx.HTTPError as erro:
            ultimo_erro = erro
            time.sleep(0.8 * (tentativa + 1))
    if ultimo_erro is not None:
        raise ultimo_erro
    raise RuntimeError(f"Falha ao consultar {url}")
