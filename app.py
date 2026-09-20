from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import httpx
import streamlit as st

from apiaprendiz.discord_alerta import enviar_alerta_discord, webhook_valido
from apiaprendiz.formatacao import formatar_brl, preco_em_brl, preco_normal_brl
from apiaprendiz.modelos import Candidato, Oferta
from apiaprendiz.persistencia import carregar_config, salvar_config
from apiaprendiz.servico import (
    adicionar_wishlist,
    buscar_candidatos,
    carregar_wishlist,
    comparar_jogo,
    cotacao_usd_brl,
    criar_cliente,
    economia,
    historico_do_jogo,
    jogos_gratis,
    melhores_promocoes,
    menor_oferta,
    registrar_historico,
    remover_wishlist,
    resumo_historico,
    status_wishlist,
)

st.set_page_config(page_title="DealHunter", page_icon="🎮", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.4rem; }
      .dh-hero {
        background: linear-gradient(135deg, #111827 0%, #1f2937 60%, #0f766e 100%);
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        color: #f9fafb;
        margin-bottom: 1.2rem;
      }
      .dh-card {
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 0.9rem 1rem;
        background: #0b1220;
        height: 100%;
      }
      .dh-price { font-size: 1.35rem; font-weight: 700; color: #34d399; }
      .dh-old { text-decoration: line-through; color: #94a3b8; }
    </style>
    """,
    unsafe_allow_html=True,
)


CACHE_VERSAO = "v3"


def brl_html(valor: float) -> str:
    return formatar_brl(valor).replace("$", "&#36;")


def brl_md(valor: float) -> str:
    return formatar_brl(valor).replace("$", r"\$")


@st.cache_data(ttl=300, show_spinner=False)
def _cotacao(_v: str = CACHE_VERSAO) -> tuple[float, str]:
    with criar_cliente() as client:
        return cotacao_usd_brl(client)


@st.cache_data(ttl=600, show_spinner="Buscando as melhores promoções...")
def _promocoes(_v: str = CACHE_VERSAO) -> list[Oferta]:
    with criar_cliente() as client:
        return melhores_promocoes(client)


@st.cache_data(ttl=600, show_spinner="Buscando jogos grátis...")
def _gratis(_v: str = CACHE_VERSAO) -> tuple[list[Oferta], list[Oferta], list[Oferta]]:
    with criar_cliente() as client:
        return jogos_gratis(client)


@st.cache_data(ttl=180, show_spinner="Procurando o jogo...")
def _buscar(termo: str, _v: str = CACHE_VERSAO) -> list[Candidato]:
    with criar_cliente() as client:
        return buscar_candidatos(client, termo)


@st.cache_data(ttl=180, show_spinner="Comparando lojas...")
def _comparar(candidato: Candidato, _v: str = CACHE_VERSAO) -> list[Oferta]:
    with criar_cliente() as client:
        return comparar_jogo(client, candidato)


def _card_oferta(item: Oferta, taxa: float) -> None:
    atual = preco_em_brl(item, taxa)
    normal = preco_normal_brl(item, taxa)
    with st.container(border=True):
        if item.get("thumb"):
            cols = st.columns([1, 3])
            cols[0].image(item["thumb"], use_container_width=True)
            alvo = cols[1]
        else:
            alvo = st
        alvo.caption(item["loja"])
        alvo.markdown(f"**{item['titulo']}**")
        if atual <= 0:
            alvo.markdown('<p class="dh-price">Grátis</p>', unsafe_allow_html=True)
        elif normal > atual:
            alvo.markdown(
                f'<span class="dh-old">{brl_html(normal)}</span> '
                f'<span class="dh-price">{brl_html(atual)}</span>',
                unsafe_allow_html=True,
            )
        else:
            alvo.markdown(
                f'<p class="dh-price">{brl_html(atual)}</p>',
                unsafe_allow_html=True,
            )
        if atual > 0 and item["desconto"] > 0:
            alvo.write(f"Desconto: **{item['desconto']:.0f}%**")
        alvo.link_button("Ver oferta", item["link"], use_container_width=True)


def _grade(itens: list[Oferta], taxa: float, limite: int = 12) -> None:
    if not itens:
        st.info("Nada encontrado nesta fonte agora.")
        return
    visiveis = itens[:limite]
    for inicio in range(0, len(visiveis), 3):
        colunas = st.columns(3)
        for coluna, item in zip(colunas, visiveis[inicio : inicio + 3], strict=False):
            with coluna:
                _card_oferta(item, taxa)


def _pagina_busca(taxa: float) -> None:
    st.subheader("Buscar jogo")
    termo = st.text_input("Digite o jogo", placeholder="cyberpunk, hogwarts, elden ring...")
    if not termo:
        return

    candidatos = _buscar(termo)
    if not candidatos:
        st.warning("Nenhum resultado. Tente um nome mais curto.")
        return

    rotulos = [item["nome"] for item in candidatos]
    escolhido_nome = st.radio("Resultados encontrados", rotulos, index=0)
    candidato = next(item for item in candidatos if item["nome"] == escolhido_nome)

    ofertas = _comparar(candidato)
    if not ofertas:
        st.error("Não achei preço nas lojas para esse título.")
        return

    melhor = menor_oferta(ofertas, taxa)
    if melhor is None:
        return

    chave_hist = f"hist_{candidato['nome']}"
    if chave_hist not in st.session_state:
        for oferta_ref in ofertas:
            registrar_historico(
                candidato["nome"],
                oferta_ref["loja"],
                preco_em_brl(oferta_ref, taxa),
            )
        st.session_state[chave_hist] = True

    atual = preco_em_brl(melhor, taxa)
    st.markdown(f"### {candidato['nome']}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Menor preço atual", formatar_brl(atual), melhor["loja"])
    c2.metric("Economia", formatar_brl(economia(melhor, taxa)))
    c3.metric("Desconto", f"{melhor['desconto']:.0f}%")

    st.markdown("#### Comparar preços")
    ofertas_ord = sorted(ofertas, key=lambda item: preco_em_brl(item, taxa))
    _grade(ofertas_ord, taxa, limite=12)

    st.markdown("#### Wishlist e histórico")
    desejado = st.number_input(
        "Preço máximo desejado (R$)",
        min_value=0.0,
        value=float(max(atual, 1)),
        step=5.0,
    )
    if st.button("Adicionar à wishlist", type="primary"):
        adicionar_wishlist(
            {
                "jogo": candidato["nome"],
                "preco_desejado": float(desejado),
                "steam_app_id": candidato["steam_app_id"],
                "cheapshark_id": candidato["cheapshark_id"],
            }
        )
        st.success("Salvo em data/wishlist.json")

    pontos = historico_do_jogo(candidato["nome"])
    if pontos:
        stats = resumo_historico(pontos)
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Atual observado", formatar_brl(stats["atual"]))
        h2.metric("Menor observado", formatar_brl(stats["menor"]))
        h3.metric("Maior observado", formatar_brl(stats["maior"]))
        h4.metric("Média", formatar_brl(stats["media"]))
        st.line_chart({"Preço (R$)": [ponto["preco"] for ponto in pontos]})


def _pagina_promocoes(taxa: float) -> None:
    st.subheader("Melhores promoções")
    st.caption("Steam (preço BR), Epic, GOG e CheapShark, ordenadas pelo maior desconto.")
    itens = _promocoes()
    minimo = st.slider("Desconto mínimo", 0, 100, 50)
    if st.session_state.get("promo_filtro") != minimo:
        st.session_state.promo_filtro = minimo
        st.session_state.promo_pagina = 0

    filtrados = [item for item in itens if item["desconto"] >= minimo]
    por_pagina = 12
    total = len(filtrados)
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = int(st.session_state.get("promo_pagina", 0))
    pagina = max(0, min(pagina, total_paginas - 1))
    st.session_state.promo_pagina = pagina

    inicio = pagina * por_pagina
    lote = filtrados[inicio : inicio + por_pagina]
    st.write(
        f"{total} ofertas com pelo menos {minimo}% off · "
        f"página {pagina + 1} de {total_paginas}"
    )
    _grade(lote, taxa, limite=por_pagina)

    anterior, indicador, proxima = st.columns([1, 2, 1])
    if anterior.button("Anterior", disabled=pagina <= 0, use_container_width=True):
        st.session_state.promo_pagina = pagina - 1
        st.rerun()
    indicador.markdown(
        f"<p style='text-align:center;margin-top:0.4rem'>Página {pagina + 1} / {total_paginas}</p>",
        unsafe_allow_html=True,
    )
    if proxima.button("Próxima", disabled=pagina >= total_paginas - 1, use_container_width=True):
        st.session_state.promo_pagina = pagina + 1
        st.rerun()


def _pagina_gratis(taxa: float) -> None:
    st.subheader("Jogos grátis")
    agora, proximos, sempre = _gratis()
    aba1, aba2, aba3 = st.tabs(
        ["Giveaway agora", "Próximos da Epic", "Sempre grátis / F2P"]
    )
    with aba1:
        _grade(agora, taxa, limite=18)
    with aba2:
        _grade(proximos, taxa, limite=12)
    with aba3:
        _grade(sempre, taxa, limite=18)


def _pagina_wishlist(taxa: float) -> None:
    st.subheader("Minha wishlist")
    config = carregar_config()

    with st.expander("Alerta no Discord", expanded=not bool(config["discord_webhook"])):
        st.caption(
            "Crie um webhook no canal do Discord (Editar canal → Integrações → Webhooks) "
            "e cole a URL aqui. O DealHunter avisa quando o preço-alvo ou o desconto mínimo bater."
        )
        webhook = st.text_input(
            "URL do webhook",
            value=config["discord_webhook"],
            type="password",
            placeholder="https://discord.com/api/webhooks/...",
        )
        desconto_alerta = st.slider(
            "Desconto mínimo para avisar no Discord",
            0,
            100,
            int(config["desconto_minimo"]),
        )
        salvar, testar = st.columns(2)
        if salvar.button("Salvar webhook", use_container_width=True):
            url = webhook.strip()
            if url and not webhook_valido(url):
                st.error("Essa URL não parece um webhook do Discord.")
            else:
                config["discord_webhook"] = url
                config["desconto_minimo"] = float(desconto_alerta)
                salvar_config(config)
                st.success("Configuração salva em data/config.json")
        if testar.button("Enviar teste", use_container_width=True):
            try:
                enviar_alerta_discord(
                    webhook.strip() or config["discord_webhook"],
                    jogo="DealHunter (teste)",
                    loja="—",
                    preco=0.0,
                    desconto=float(desconto_alerta),
                    link="https://www.raphaeldias.dev.br/",
                    motivo="Webhook configurado. Os alertas da wishlist chegam neste canal.",
                )
                st.success("Teste enviado no Discord.")
            except (ValueError, httpx.HTTPError) as erro:
                st.error(str(erro))

    itens = carregar_wishlist()
    if not itens:
        st.info("Sua lista está vazia. Busque um jogo e defina o preço desejado.")
        return

    if st.button("Checar preços agora", type="primary"):
        alertas: list[str] = []
        discord_enviados = 0
        with criar_cliente() as client:
            for item in itens:
                candidato: Candidato = {
                    "nome": item["jogo"],
                    "steam_app_id": item["steam_app_id"],
                    "cheapshark_id": item["cheapshark_id"],
                    "thumb": "",
                }
                ofertas = comparar_jogo(client, candidato)
                melhor = menor_oferta(ofertas, taxa)
                if melhor is None:
                    st.session_state[f"wl_{item['jogo']}"] = None
                    continue
                preco = preco_em_brl(melhor, taxa)
                desconto = float(melhor["desconto"])
                registrar_historico(item["jogo"], melhor["loja"], preco)
                st.session_state[f"wl_{item['jogo']}"] = {
                    "preco": preco,
                    "loja": melhor["loja"],
                    "link": melhor["link"],
                    "status": status_wishlist(preco, item["preco_desejado"]),
                    "desconto": desconto,
                }
                bateu_preco = preco <= item["preco_desejado"]
                bateu_desconto = desconto >= config["desconto_minimo"]
                if bateu_preco:
                    alertas.append(
                        f"{item['jogo']}: {formatar_brl(preco)} na {melhor['loja']}"
                    )
                deve_avisar = bateu_preco or bateu_desconto
                chave_aviso = item["jogo"].casefold()
                ultimo = config["avisos"].get(chave_aviso)
                preco_melhorou = ultimo is None or preco < ultimo - 0.009
                if (
                    deve_avisar
                    and preco_melhorou
                    and webhook_valido(config["discord_webhook"])
                ):
                    motivo = (
                        f"Preço-alvo {formatar_brl(item['preco_desejado'])} atingido."
                        if bateu_preco
                        else f"Desconto de {desconto:.0f}% (mínimo {config['desconto_minimo']:.0f}%)."
                    )
                    try:
                        enviar_alerta_discord(
                            config["discord_webhook"],
                            jogo=item["jogo"],
                            loja=melhor["loja"],
                            preco=preco,
                            desconto=desconto,
                            link=melhor["link"],
                            motivo=motivo,
                        )
                        config["avisos"][chave_aviso] = preco
                        salvar_config(config)
                        discord_enviados += 1
                    except httpx.HTTPError as erro:
                        st.warning(f"Discord não recebeu o alerta de {item['jogo']}: {erro}")
        if alertas:
            st.success("Alerta de preço\n\n" + "\n".join(f"- {msg}" for msg in alertas))
            st.balloons()
        elif discord_enviados:
            st.success(f"{discord_enviados} alerta(s) enviados no Discord.")

    for item in itens:
        info = st.session_state.get(f"wl_{item['jogo']}")
        with st.container(border=True):
            topo, acao = st.columns([4, 1])
            topo.markdown(f"**{item['jogo']}**")
            topo.caption(f"Preço desejado: {formatar_brl(item['preco_desejado'])}")
            if acao.button("Remover", key=f"rm_{item['jogo']}"):
                remover_wishlist(item["jogo"])
                st.rerun()
            if not info:
                st.write("Ainda não checado nesta sessão.")
                continue
            preco = float(info["preco"])
            st.write(f"Preço atual: **{brl_md(preco)}** — {info['loja']}")
            status = str(info["status"])
            if status == "compre":
                st.success("COMPRE AGORA")
            elif status == "gratis":
                st.success("Está de graça")
            elif status == "quase":
                st.warning("Quase lá")
            else:
                st.info("Ainda acima do desejado")
            st.link_button("Abrir oferta", str(info["link"]))


def main() -> None:
    try:
        taxa, fonte = _cotacao()
    except RuntimeError as erro:
        st.error(str(erro))
        return

    st.markdown(
        f"""
        <div class="dh-hero">
          <h1>DealHunter</h1>
          <p>Onde e quando vale a pena comprar. Cotação USD→BRL: <b>{brl_html(taxa)}</b> · {fonte}</p>
          <p>Feito por <a href="https://www.raphaeldias.dev.br/" target="_blank" rel="noopener noreferrer">Raphael Dias</a></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pagina = st.sidebar.radio(
        "Menu",
        [
            "Buscar jogo",
            "Melhores promoções",
            "Jogos grátis",
            "Minha wishlist",
        ],
        index=0,
    )
    st.sidebar.caption("Dados em `data/wishlist.json` e `data/historico.csv`.")
    st.sidebar.markdown(
        "Feito por [Raphael Dias](https://www.raphaeldias.dev.br/)"
    )

    if pagina == "Buscar jogo":
        _pagina_busca(taxa)
    elif pagina == "Melhores promoções":
        _pagina_promocoes(taxa)
    elif pagina == "Jogos grátis":
        _pagina_gratis(taxa)
    else:
        _pagina_wishlist(taxa)


if __name__ == "__main__":
    main()
else:
    main()
