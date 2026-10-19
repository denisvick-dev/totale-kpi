"""
components/upload_base.py
=========================
Upload **manual** compartilhado da base operacional (exportação
"Atividades", .xlsx/.xls/.csv).

Um único envio alimenta os três painéis operacionais — o arquivo é lido
e tratado uma vez por :func:`components.base_operacional.gerar_bases_upload`
e cada base pronta é publicada na chave de sessão que o painel consome:

=======================  ==========================
Painel                   Chave em ``session_state``
=======================  ==========================
Quebra de Agenda         ``df_memoria``
Volumetria de O.S.       ``base_data``
Rota Inicial             ``df_master``
=======================  ==========================

Além disso, ficam na sessão os bytes do arquivo (``quebra_arquivo``,
para refazer o vínculo com a lista de ativos sem novo envio) e os
metadados do upload (``base_operacional_upload``), usados para exibir
o status e evitar reprocessar o mesmo arquivo a cada rerun.

O componente é exibido na Central de Atualização (``envio_excel.py``)
e, no estado vazio, em cada um dos três painéis — enviar por qualquer
um deles atualiza todos.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from components import base_operacional as bo
from components.componentes import render_section_header

FUSO = ZoneInfo("America/Sao_Paulo")

#: Chaves de sessão publicadas pelo upload (uma por painel).
CHAVE_QUEBRA = "df_memoria"
CHAVE_VOLUMETRIA = "base_data"
CHAVE_ROTA = "df_master"
#: Bytes do último arquivo enviado — permite refazer o vínculo de ativos.
CHAVE_ARQUIVO = "quebra_arquivo"
#: Metadados do último upload (arquivo, horário, hash, linhas, erros).
CHAVE_META = "base_operacional_upload"

EXTENSOES_UPLOAD = ["xlsx", "xls", "csv"]

#: (chave do resultado, rótulo, página) — ordem de exibição do status.
PAINEIS: tuple[tuple[str, str, str], ...] = (
    ("quebra", "Quebra de Agenda", "pages/quebra.py"),
    ("volumetria", "Volumetria de O.S.", "pages/volumetria.py"),
    ("rota_inicial", "Rota Inicial", "pages/rota_inicial.py"),
)

_CHAVES_POR_PAINEL = {
    "quebra": CHAVE_QUEBRA,
    "volumetria": CHAVE_VOLUMETRIA,
    "rota_inicial": CHAVE_ROTA,
}


def _fmt_int(valor: int) -> str:
    return f"{int(valor):,}".replace(",", ".")


@st.cache_data(ttl=300, show_spinner="🔗 Vinculando Lista de Ativos...")
def _carregar_lista_ativos() -> pd.DataFrame:
    """Aba ``lista_ativos`` usada no vínculo das três bases (cache de 5 min)."""
    return bo.carregar_lista_ativos(read_csv=pd.read_csv)


def limpar_cache_lista_ativos() -> None:
    """Força uma nova leitura da ``lista_ativos`` no próximo upload."""
    _carregar_lista_ativos.clear()


def metadados_upload() -> dict[str, Any]:
    """Metadados do último upload publicado (``{}`` se nenhum)."""
    meta = st.session_state.get(CHAVE_META)
    return meta if isinstance(meta, dict) else {}


def limpar_bases_operacionais() -> None:
    """Remove as três bases operacionais e os metadados do upload.

    Também avança a "geração" do widget de envio: sem isso, o
    ``file_uploader`` manteria o arquivo anterior e a troca de base
    reprocessaria o mesmo arquivo ao voltar ao estado vazio.
    """
    st.session_state[CHAVE_QUEBRA] = None
    st.session_state[CHAVE_VOLUMETRIA] = None
    st.session_state[CHAVE_ROTA] = None
    st.session_state.pop(CHAVE_ARQUIVO, None)
    st.session_state.pop(CHAVE_META, None)
    st.session_state["_upload_geracao"] = (
        int(st.session_state.get("_upload_geracao", 0) or 0) + 1
    )


def processar_e_publicar(conteudo: bytes, nome_arquivo: str) -> dict[str, Any]:
    """
    Processa o arquivo enviado e publica cada base na sessão.

    Retorna os metadados do upload (também gravados em ``CHAVE_META``);
    painéis que falharam aparecem em ``erros`` e não são publicados.
    """
    resultado = bo.gerar_bases_upload(
        conteudo, nome_arquivo, _carregar_lista_ativos()
    )

    linhas: dict[str, int] = {}
    for painel, _rotulo, _pagina in PAINEIS:
        base = resultado.get(painel)
        if isinstance(base, pd.DataFrame) and not base.empty:
            st.session_state[_CHAVES_POR_PAINEL[painel]] = base
            linhas[painel] = len(base)
    if "quebra" in linhas:
        st.session_state[CHAVE_ARQUIVO] = (conteudo, nome_arquivo)

    meta: dict[str, Any] = {
        "arquivo": nome_arquivo,
        "quando": datetime.now(FUSO),
        "hash": hashlib.sha256(conteudo).hexdigest(),
        "linhas_brutas": int(resultado.get("linhas_brutas", 0) or 0),
        "linhas": linhas,
        "erros": dict(resultado.get("erros", {}) or {}),
    }
    st.session_state[CHAVE_META] = meta
    return meta


def render_status_upload(*, mostrar_links: bool = False) -> bool:
    """Status compacto da base publicada (barra lateral e Central)."""
    meta = metadados_upload()
    if not meta:
        st.caption("📁 Nenhuma base operacional enviada nesta sessão.")
        return False

    quando = meta.get("quando")
    texto_quando = (
        quando.strftime("%d/%m/%Y às %H:%M:%S")
        if isinstance(quando, datetime)
        else "—"
    )
    st.caption(
        f"📄 `{meta.get('arquivo', '—')}`  \n"
        f"🕒 {texto_quando} · {_fmt_int(meta.get('linhas_brutas', 0))} "
        "linhas no arquivo"
    )

    linhas = meta.get("linhas", {}) or {}
    erros = meta.get("erros", {}) or {}
    for painel, rotulo, _pagina in PAINEIS:
        if painel in linhas:
            st.caption(f"✅ **{rotulo}:** {_fmt_int(linhas[painel])} registros")
        elif painel in erros:
            st.caption(f"⚠️ **{rotulo}:** {erros[painel]}")

    if mostrar_links and linhas:
        colunas = st.columns(len(linhas))
        publicados = [p for p in PAINEIS if p[0] in linhas]
        for coluna, (_painel, rotulo, pagina) in zip(colunas, publicados):
            with coluna:
                st.page_link(pagina, label=f"Abrir {rotulo}", icon="➡️")
    return bool(linhas)


def _alertar_vinculo_ativos() -> None:
    """Avisa quando a base publicada não vinculou nenhum login aos ativos."""
    quebra = st.session_state.get(CHAVE_QUEBRA)
    if not isinstance(quebra, pd.DataFrame) or quebra.empty:
        return
    if int(quebra.attrs.get("diag_vinculados", 0) or 0):
        return
    erro = str(quebra.attrs.get("erro_ativos", "") or "").strip()
    st.warning(
        "⚠️ A base publicada não vinculou nenhum login à `lista_ativos`"
        + (f" — {erro}" if erro else ".")
        + " Monitores e técnicos aparecem como `SEM MONITOR`/`NÃO MAPEADO` "
        "até o vínculo ser concluído; confira a coluna de login do arquivo "
        "e da planilha, ou use **🔗 Atualizar Lista de Ativos** na Quebra "
        "de Agenda após corrigir a planilha."
    )


def render_upload_base_operacional(
    key: str,
    *,
    titulo: str | None = "Enviar base operacional",
    recarregar_apos_envio: bool = False,
) -> bool:
    """
    Renderiza o upload manual e processa o arquivo escolhido.

    ``key`` diferencia o widget entre páginas. Com
    ``recarregar_apos_envio``, a página é recarregada logo após a
    publicação (usado pelos painéis, que exibem o upload apenas no
    estado vazio); na Central de Atualização o resumo e os links dos
    painéis aparecem na mesma tela. Retorna ``True`` se já existe ao
    menos uma base publicada nesta sessão.
    """
    if titulo:
        render_section_header("upload_file", titulo, "Excel / CSV")
    st.caption(
        "Envie a exportação de atividades (.xlsx, .xls ou .csv). O mesmo "
        "arquivo atualiza **Quebra de Agenda**, **Volumetria de O.S.** e "
        "**Rota Inicial** de uma vez, com vínculo à lista de ativos."
    )

    arquivo = st.file_uploader(
        "Selecione a base (Excel/CSV)",
        type=EXTENSOES_UPLOAD,
        key=f"upload_base_operacional_{key}",
    )

    if arquivo is not None:
        conteudo = arquivo.getvalue()
        meta = metadados_upload()
        mesmo_arquivo = meta.get("hash") == hashlib.sha256(conteudo).hexdigest()
        if mesmo_arquivo:
            erros = meta.get("erros", {}) or {}
            if "leitura" in erros:
                st.error(
                    f"❌ Não foi possível ler este arquivo: {erros['leitura']}"
                )
            elif meta.get("linhas"):
                st.success("✅ Este arquivo já foi processado nesta sessão.")
        else:
            with st.spinner(
                "🔄 Processando a base para Quebra, Volumetria e Rota Inicial..."
            ):
                meta = processar_e_publicar(conteudo, arquivo.name)

            erros = meta.get("erros", {}) or {}
            if "leitura" in erros:
                st.error(f"❌ Não foi possível ler o arquivo: {erros['leitura']}")
            else:
                linhas = meta.get("linhas", {}) or {}
                publicados = [
                    rotulo for painel, rotulo, _p in PAINEIS if painel in linhas
                ]
                if publicados:
                    st.success(
                        "✅ Base publicada para: " + ", ".join(publicados) + "."
                    )
                for painel, rotulo, _pagina in PAINEIS:
                    if painel in erros:
                        st.warning(f"⚠️ **{rotulo}:** {erros[painel]}")
                _alertar_vinculo_ativos()

            if recarregar_apos_envio and meta.get("linhas"):
                st.rerun()

    return render_status_upload(mostrar_links=True)


__all__ = [
    "CHAVE_ARQUIVO",
    "CHAVE_META",
    "CHAVE_QUEBRA",
    "CHAVE_ROTA",
    "CHAVE_VOLUMETRIA",
    "EXTENSOES_UPLOAD",
    "PAINEIS",
    "limpar_bases_operacionais",
    "limpar_cache_lista_ativos",
    "metadados_upload",
    "processar_e_publicar",
    "render_status_upload",
    "render_upload_base_operacional",
]
