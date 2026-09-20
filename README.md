# DealHunter

App Streamlit para achar **onde o jogo está mais barato** (Steam, Epic, GOG e lojas da CheapShark), listar **promoções** e **jogos grátis**, montar **wishlist** e avisar no **Discord** quando o desconto (ou o preço-alvo) bater.

Feito por [Raphael Dias](https://www.raphaeldias.dev.br/).

## O que o app faz

- **Buscar jogo** — compara preços entre lojas, em reais.
- **Melhores promoções** — filtro de desconto mínimo + paginação.
- **Jogos grátis** — giveaways, próximos da Epic e títulos sempre grátis.
- **Wishlist** — preço desejado, histórico e webhook do Discord.

Preços da Steam, Epic e GOG vêm em BRL. O restante (CheapShark) chega em USD e é convertido na hora.

## Rodar localmente (uv)

Python **3.14+** e [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run streamlit run app.py
```

Abre em `http://localhost:8501`.

## Streamlit Community Cloud

O Cloud lê o `uv.lock` (não usa `requirements.txt`).

1. Publique este repositório no GitHub.
2. Em [share.streamlit.io](https://share.streamlit.io), faça deploy com:
   - Main file path: `app.py`
   - Branch: `main`
3. Se pedir a versão do Python, escolha **3.14** (a mesma do `pyproject.toml`).

Wishlist, histórico e webhook ficam só na instância do Cloud (`data/`). Cada deploy tem a própria lista.

## Alerta no Discord

Na página **Minha wishlist** → **Alerta no Discord**:

1. No canal: **Editar canal → Integrações → Webhooks → Novo webhook**
2. Cole a URL e defina o desconto mínimo
3. **Salvar webhook** e, se quiser, **Enviar teste**
4. **Checar preços agora** dispara o aviso quando o preço-alvo **ou** o desconto mínimo for atingido

A URL do webhook é senha do canal. Ela fica em `data/config.json` (fora do git). Não compartilhe e não commite esse arquivo.

## Estrutura

```
app.py                 # interface Streamlit
pyproject.toml         # projeto e dependências
uv.lock                # lock do uv (o Cloud usa este arquivo)
src/apiaprendiz/       # busca, cotação, lojas, persistência, Discord
data/                  # wishlist, histórico e config (locais, gitignored)
```

## Aviso

Os preços vêm de APIs públicas (Steam, Epic, GOG, CheapShark, cotação USD/BRL). Podem atrasar, falhar ou divergir da loja. Confira no site oficial antes de comprar.
