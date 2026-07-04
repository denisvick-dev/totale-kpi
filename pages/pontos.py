import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
import numpy as np
import datetime
import calendar
from io import BytesIO
from typing import Any, Optional, Literal, cast
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS
# ====================================================
class Configuracoes:
    TEMAS_CARD = {
        "azul": {
            "fundo": "#F0F9FF",
            "texto": "#0369A1",
            "borda": "#0EA5E9",
            "titulo": "#075985",
        },
        "verde": {
            "fundo": "#F0FDF4",
            "texto": "#15803D",
            "borda": "#22C55E",
            "titulo": "#166534",
        },
        "laranja": {
            "fundo": "#FFF7ED",
            "texto": "#C2410C",
            "borda": "#F97316",
            "titulo": "#9A3412",
        },
        "cinza": {
            "fundo": "#F8FAFC",
            "texto": "#334155",
            "borda": "#94A3B8",
            "titulo": "#64748B",
        },
    }

    PAGINA = {"titulo": "📈 Ranking Geral de Pontos", "icon": "📈"}


# ====================================================
# BLOCO 2: COMPONENTES VISUAIS (FRONT-END)
# ====================================================
class ComponenteVisual:
    @staticmethod
    def criar_card(
        titulo: str, valor: str, tema: str = "azul", delta: Optional[str] = None
    ) -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])

        if delta:
            if delta.startswith("+") or delta.startswith("▲"):
                cor_delta, simbolo = "#22c55e", "▲"
            elif delta.startswith("-") or delta.startswith("▼"):
                cor_delta, simbolo = "#ef4444", "▼"
            elif "do Total" in delta:
                cor_delta, simbolo = "#0ea5e9", "◴"
            else:
                cor_delta, simbolo = "#94a3b8", "■"

            delta_html = f'<span style="font-size: 13px; color: {cor_delta}; margin-left: 10px;">{simbolo} {delta}</span>'
        else:
            delta_html = ""

        html = f"""
        <div style="
            background-color: {cores['fundo']}; padding: 20px; border-radius: 10px;
            border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px;
            transition: transform 0.2s;
        " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
            <p style="margin: 0; font-size: 14px; color: {cores['titulo']};"><b>{titulo}</b></p>
            <h2 style="margin: 5px 0 0 0; color: {cores['texto']}; font-weight: 900;">{valor}{delta_html}</h2>
        </div>
        """
        return html

    @staticmethod
    def exibir_ticker(dados: list) -> str:
        if not dados:
            return ""

        html_itens = ""
        for item in dados:
            if item.get("variacao") == "positiva":
                cor, simbolo = "#22c55e", "▲"
            elif item.get("variacao") == "negativa":
                cor, simbolo = "#ef4444", "▼"
            elif item.get("variacao") == "share":
                cor, simbolo = "#38bdf8", "◴"
            else:
                cor, simbolo = "#94a3b8", "■"

            # Tudo em uma linha só para não quebrar o Markdown do Streamlit
            html_itens += f'<span style="margin: 0 40px; font-family: \'Roboto\', sans-serif; font-size: 15px; white-space: nowrap;"><span style="color: #94a3b8; font-weight: 500;">{item.get("label", "")}:</span><span style="font-weight: 700; color: #FFFFFF; margin-left: 8px;">{item.get("valor", "")}</span><span style="color: {cor}; font-weight: 700; margin-left: 6px; font-size: 13px;">{simbolo} {item.get("delta", "")}</span></span><span style="color: #334155; margin: 0 15px;">|</span>'

        # O bloco de texto abaixo deve ficar encostado na margem!
        ticker_html = f"""<style>
.ticker-wrapper {{ width: 100%; overflow: hidden; background: linear-gradient(90deg, #0f172a 0%, #1e293b 50%, #0f172a 100%); padding: 12px 0; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); margin-bottom: 25px; position: relative; }}
.ticker-wrapper::before, .ticker-wrapper::after {{ content: ''; position: absolute; top: 0; bottom: 0; width: 60px; z-index: 2; }}
.ticker-wrapper::before {{ left: 0; background: linear-gradient(90deg, #0f172a, transparent); }}
.ticker-wrapper::after {{ right: 0; background: linear-gradient(90deg, transparent, #0f172a); }}
.ticker-content {{ display: flex; width: max-content; animation: scroll 35s linear infinite; }}
.ticker-wrapper:hover .ticker-content {{ animation-play-state: paused; }}
@keyframes scroll {{ 0% {{ transform: translate3d(0, 0, 0); }} 100% {{ transform: translate3d(-50%, 0, 0); }} }}
</style>
<div class="ticker-wrapper"><div class="ticker-content">{html_itens}{html_itens}</div></div>"""

        return ticker_html


# ====================================================
# BLOCO 3: FUNÇÕES UTILITÁRIAS E ESTILOS
# ====================================================
class Utilitarios:

    @staticmethod
    def calcular_variacao(valor_filtrado: float, valor_geral: float) -> tuple:
        if valor_geral == 0 or pd.isna(valor_geral):
            return "neutra", "S/D"
        if abs(valor_filtrado - valor_geral) < 0.0001:
            return "neutra", "Visão Geral"
        diferenca = valor_filtrado - valor_geral
        percentual = (diferenca / valor_geral) * 100
        if percentual > 0:
            return "positiva", f"+{percentual:.1f}%"
        elif percentual < 0:
            return "negativa", f"{percentual:.1f}%"
        return "neutra", "0%"

    @staticmethod
    def calcular_share(valor_filtrado: float, valor_geral: float) -> tuple:
        if valor_geral == 0 or pd.isna(valor_geral):
            return "neutra", "0%"
        if abs(valor_filtrado - valor_geral) < 0.0001:
            return "neutra", "Visão Geral"
        share = (valor_filtrado / valor_geral) * 100
        return "share", f"{share:.1f}% do Total"

    @staticmethod
    def formatar_numero(valor: float) -> str:
        return f"{valor:,.0f}".replace(",", ".")

    @staticmethod
    def colorir_metas(valor):
        if 275 <= valor < 300:
            return "background-color: #FEF08A; color: #9A3412; font-weight: bold"
        if 300 <= valor < 400:
            return "background-color: #BBF7D0; color: #166534; font-weight: bold"
        if valor >= 400:
            return "background-color: #1E3A8A; color: #FFFFFF; font-weight: bold"
        return "background-color: #F8FAFC"

    @staticmethod
    def colorir_projecao(valor):
        return "background-color: #334155; color: white; font-weight: bold"

    @staticmethod
    def negrito(valor):
        return "font-weight: bold"

    @staticmethod
    def calcular_dias_uteis(df: pd.DataFrame) -> tuple:
        ultima_atualizacao = (
            df["Data Agendamento"].max() if "Data Agendamento" in df.columns else None
        )
        hoje = datetime.date.today()
        ano_atual, mes_atual = hoje.year, hoje.month

        _, ultimo_dia_num = calendar.monthrange(ano_atual, mes_atual)
        ult_dia = datetime.date(ano_atual, mes_atual, ultimo_dia_num)

        data_inicio_np = np.datetime64(
            ultima_atualizacao.date() if pd.notna(ultima_atualizacao) else hoje
        )
        data_fim_np = np.datetime64(ult_dia) + np.timedelta64(1, "D")

        dias_brutos = np.busday_count(data_inicio_np, data_fim_np, weekmask="1111110")
        dias_seguros = max(1, dias_brutos)
        return dias_brutos, dias_seguros, ultima_atualizacao

    @staticmethod
    def exportar_excel(dataframe: pd.DataFrame) -> bytes:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Ranking")
            ws = writer.sheets["Ranking"]

            cor_cabecalho = PatternFill(
                start_color="FF012869", end_color="FF012869", fill_type="solid"
            )
            f_cabecalho = Font("Calibri", size=10.5, bold=True, color="FFFFFFFF")
            f_padrao = Font("Calibri", size=10.5, color="FF000000")
            borda = Border(
                left=Side(style="thin", color="FFD9D9D9"),
                right=Side(style="thin", color="FFD9D9D9"),
                top=Side(style="thin", color="FFD9D9D9"),
                bottom=Side(style="thin", color="FFD9D9D9"),
            )
            c_amarelo = PatternFill(
                start_color="FFFFEB9C", end_color="FFFFEB9C", fill_type="solid"
            )
            f_amarelo = Font("Calibri", size=10.5, bold=True, color="FF9C5700")
            c_verde = PatternFill(
                start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid"
            )
            f_verde = Font("Calibri", size=10.5, bold=True, color="FF006100")
            c_azul = PatternFill(
                start_color="FF1F497D", end_color="FF1F497D", fill_type="solid"
            )
            f_azul = Font("Calibri", size=10.5, bold=True, color="FFFFFFFF")
            c_escuro = PatternFill(
                start_color="FF181818", end_color="FF181818", fill_type="solid"
            )
            f_escuro = Font("Calibri", size=10.5, bold=True, color="FFFFFFFF")

            for row in ws.iter_rows(
                min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column
            ):
                for celula in row:
                    celula.border = borda
                    if celula.row == 1:
                        celula.fill, celula.font, celula.alignment = (
                            cor_cabecalho,
                            f_cabecalho,
                            Alignment(horizontal="center", vertical="center"),
                        )
                    else:
                        celula.font, celula.alignment = f_padrao, Alignment(
                            horizontal="center", vertical="center"
                        )

            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[get_column_letter(col[0].column)].width = max(
                    max_len + 4, 12
                )

            for lin in range(2, ws.max_row + 1):
                celula_pontos = ws.cell(row=lin, column=5)
                celula_pontos.number_format = "#,##0.00"
                if 275 <= celula_pontos.value < 300:
                    celula_pontos.fill, celula_pontos.font = c_amarelo, f_amarelo
                elif 300 <= celula_pontos.value < 400:
                    celula_pontos.fill, celula_pontos.font = c_verde, f_verde
                elif celula_pontos.value >= 400:
                    celula_pontos.fill, celula_pontos.font = c_azul, f_azul

                for col in [6, 7, 8, 9]:
                    ws.cell(row=lin, column=col).number_format = "#,##0.00"
                celula_proj = ws.cell(row=lin, column=10)
                celula_proj.number_format, celula_proj.fill, celula_proj.font = (
                    "#,##0.00",
                    c_escuro,
                    f_escuro,
                )

        return output.getvalue()


# ====================================================
# BLOCO 4: PROCESSAMENTO DE NEGÓCIO E MATEMÁTICA
# ====================================================
class ProcessamentoDados:
    @staticmethod
    def calcular_rankings(
        df: pd.DataFrame, dias_brutos: int, dias_seguros: int
    ) -> tuple:
        base_ranking = (
            df.groupby(["CódAuxEquipe", "Nome Equipe", "Supervisor"])["Pontos"]
            .sum()
            .reset_index()
            .sort_values("Pontos", ascending=False)
        )

        if "Dias Trab Tecnico" in df.columns:
            max_por_tecnico = df.groupby("Nome Equipe")["Dias Trab Tecnico"].max()
            dias_trabalhados = (
                base_ranking["Nome Equipe"].map(max_por_tecnico).fillna(0).astype(int)
            )
        else:
            dias_trabalhados = pd.Series(0, index=base_ranking.index)

        media_pontos = base_ranking["Pontos"] / dias_trabalhados.replace(0, np.nan)
        projecao = base_ranking["Pontos"] + (media_pontos * dias_brutos)

        ranking = base_ranking.copy()
        ranking.insert(0, "Posição", range(1, len(ranking) + 1))
        ranking["Meta | 300"] = ranking["Pontos"] - 300
        ranking["Meta | 350"] = ranking["Pontos"] - 350
        ranking["Meta | 375"] = ranking["Pontos"] - 375
        ranking["Meta | 400"] = ranking["Pontos"] - 400
        ranking["Projeção"] = projecao

        ranking_dia = base_ranking.copy()
        ranking_dia.insert(0, "Posição", range(1, len(ranking_dia) + 1))
        ranking_dia["Meta Dia | 300"] = (ranking_dia["Pontos"] - 300) / dias_seguros
        ranking_dia["Meta Dia | 350"] = (ranking_dia["Pontos"] - 350) / dias_seguros
        ranking_dia["Meta Dia | 375"] = (ranking_dia["Pontos"] - 375) / dias_seguros
        ranking_dia["Meta Dia | 400"] = (ranking_dia["Pontos"] - 400) / dias_seguros
        ranking_dia["Projeção"] = projecao

        return ranking, ranking_dia


# ====================================================
# BLOCO 5: COMPONENTES DE GRÁFICOS
# ====================================================
class Graficos:
    @staticmethod
    def grafico_barras(df: pd.DataFrame, x: str, y: str) -> Figure:
        fig = px.bar(
            df, x=x, y=y, text_auto=True, color=y, color_continuous_scale="Oryel"
        )
        fig.update_layout(
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Roboto"),
            xaxis=dict(showgrid=False, title=""),
            yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.1)", title=""),
        )
        fig.update_traces(
            textposition="outside", textfont_size=12, textfont_color="#334155"
        )
        return fig

    @staticmethod
    def mapa_pontos(df: pd.DataFrame, titulo_hover: str) -> Optional[Figure]:
        if "lat" not in df.columns or "lon" not in df.columns:
            return None

        fig = px.scatter_mapbox(
            df,
            lat="lat",
            lon="lon",
            size="Pontos",
            color="Pontos",
            color_continuous_scale="Oryel",
            hover_name=titulo_hover,
            hover_data={
                "lat": False, 
                "lon": False, 
                "Pontos": ":.2f"
            },
            zoom=10, 
            height=600
        )

        fig.update_layout(
            mapbox_style="open-street-map",
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig


# ====================================================
# BLOCO 6: INICIALIZAÇÃO DA PÁGINA E DADOS BRUTOS
# ====================================================
st.set_page_config(
    page_title=Configuracoes.PAGINA["titulo"],
    page_icon=Configuracoes.PAGINA["icon"],
    layout=cast(Literal["wide"], "wide"),
)
st.title(Configuracoes.PAGINA["titulo"])

if "dados_prod" not in st.session_state:
    st.warning("⚠️ Carregue os dados na página principal primeiro.")
    st.stop()

try:
    prod = st.session_state["dados_prod"]["Prod"].copy()
    gpon = st.session_state["dados_prod"]["Gpon"].copy()
except KeyError as erro:
    st.error(f"❌ Aba não encontrada: {erro}")
    st.stop()

prod["Pontos"] = pd.to_numeric(prod["Pontos"], errors="coerce").fillna(0)
gpon["Pontos"] = pd.to_numeric(gpon["Pontos"], errors="coerce").fillna(0)

df = pd.concat([prod, gpon], ignore_index=True)

# --- DICIONÁRIO DE COORDENADAS DA REGIÃO SP / GRU / ABCDM ---
COORDENADAS_CIDADES = {
    "SAO PAULO": {"lat": -23.5505, "lon": -46.6333},
    "GUARULHOS": {"lat": -23.4555, "lon": -46.5333},
    "SANTO ANDRE": {"lat": -23.6611, "lon": -46.5333},
    "SAO BERNARDO DO CAMPO": {"lat": -23.7000, "lon": -46.5600},
    "SAO CAETANO DO SUL": {"lat": -23.6250, "lon": -46.5500},
    "DIADEMA": {"lat": -23.6800, "lon": -46.6300},
    "MAUA": {"lat": -23.6700, "lon": -46.4700},
    "ABCDM": {"lat": -23.6600, "lon": -46.5500}, # Ponto central da região ABC
}

def atribuir_coords(cidade):
    if pd.isna(cidade):
        return None, None
    
    # Remove espaços extras e garante que a comparação funcione
    cidade_limpa = str(cidade).strip()
    
    if cidade_limpa in COORDENADAS_CIDADES:
        return COORDENADAS_CIDADES[cidade_limpa]["lat"], COORDENADAS_CIDADES[cidade_limpa]["lon"]
    
    return None, None

# Aplicando ao DataFrame
if "Cidade" in df.columns:
    df[['lat', 'lon']] = df['Cidade'].apply(lambda x: pd.Series(atribuir_coords(x)))

# Guardar os valores BRUTOS antes de qualquer filtro para o Ticker/Cards comparar
TOTAL_GERAL_PONTOS = df["Pontos"].sum()
TOTAL_GERAL_OS = len(df)
TOTAL_GERAL_EQUIPES = df["Nome Equipe"].nunique() if "Nome Equipe" in df.columns else 0
MEDIA_GERAL_PONTOS = (
    TOTAL_GERAL_PONTOS / TOTAL_GERAL_EQUIPES if TOTAL_GERAL_EQUIPES > 0 else 0
)

# ====================================================
# BLOCO 7: FILTROS (SIDEBAR)
# ====================================================
st.sidebar.header("🎯 Filtros Avançados")

if "Projeto" in df.columns:
    opcoes_projeto = ["Todos"] + sorted(df["Projeto"].dropna().astype(str).unique())
    proj_sel = st.sidebar.selectbox("Filtrar por Projeto:", opcoes_projeto)
    if proj_sel != "Todos":
        df = df[df["Projeto"] == proj_sel]

if "Supervisor" in df.columns:
    opcoes_sup = ["Todos"] + sorted(df["Supervisor"].dropna().astype(str).unique())
    sup_sel = st.sidebar.selectbox("Filtrar por Supervisor:", opcoes_sup)
    if sup_sel != "Todos":
        df = df[df["Supervisor"] == sup_sel]

if "Nome Equipe" in df.columns:
    opcoes_equipe = ["Todos"] + sorted(df["Nome Equipe"].dropna().astype(str).unique())
    equipe_sel = st.sidebar.selectbox("Filtrar por Nome Equipe:", opcoes_equipe)
    if equipe_sel != "Todos":
        df = df[df["Nome Equipe"] == equipe_sel]

if st.sidebar.button("🔄 Limpar Filtros"):
    st.rerun()

# ====================================================
# BLOCO 8: CÁLCULOS PÓS-FILTRO E FAIXA FINANCEIRA
# ====================================================
total_equipes_filtro = df["Nome Equipe"].nunique() if "Nome Equipe" in df.columns else 0
total_os_filtro = len(df)
total_pontos_filtro = df["Pontos"].sum() if "Pontos" in df.columns else 0
media_pontos_filtro = (
    total_pontos_filtro / total_equipes_filtro if total_equipes_filtro > 0 else 0
)

# Compara o filtrado com o geral
var_pontos = Utilitarios.calcular_share(total_pontos_filtro, TOTAL_GERAL_PONTOS)
var_os = Utilitarios.calcular_share(total_os_filtro, TOTAL_GERAL_OS)
var_equipes = Utilitarios.calcular_share(total_equipes_filtro, TOTAL_GERAL_EQUIPES)
var_media = Utilitarios.calcular_variacao(media_pontos_filtro, MEDIA_GERAL_PONTOS)

# Renderiza Ticker
dados_ticker = [
    {
        "label": "Pontos",
        "valor": Utilitarios.formatar_numero(total_pontos_filtro),
        "variacao": var_pontos[0],
        "delta": var_pontos[1],
    },
    {
        "label": "Ordens de Serviço",
        "valor": Utilitarios.formatar_numero(total_os_filtro),
        "variacao": var_os[0],
        "delta": var_os[1],
    },
    {
        "label": "Equipes Trabalhando",
        "valor": str(total_equipes_filtro),
        "variacao": var_equipes[0],
        "delta": var_equipes[1],
    },
    {
        "label": "Média Pontos/Equipe",
        "valor": Utilitarios.formatar_numero(media_pontos_filtro),
        "variacao": var_media[0],
        "delta": var_media[1],
    },
]
st.markdown(ComponenteVisual.exibir_ticker(dados_ticker), unsafe_allow_html=True)

# Renderiza Cards (Agora com os Deltas de Share)
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        ComponenteVisual.criar_card(
            "Total Pontos (Geral)",
            Utilitarios.formatar_numero(TOTAL_GERAL_PONTOS),
            "cinza",
        ),
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        ComponenteVisual.criar_card(
            "Total Pontos (Filtro)",
            Utilitarios.formatar_numero(total_pontos_filtro),
            "azul",
            var_pontos[1],
        ),
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        ComponenteVisual.criar_card(
            "Equipes (Filtro)", str(total_equipes_filtro), "verde", var_equipes[1]
        ),
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        ComponenteVisual.criar_card(
            "Total O.S. (Filtro)",
            Utilitarios.formatar_numero(total_os_filtro),
            "laranja",
            var_os[1],
        ),
        unsafe_allow_html=True,
    )

st.divider()

# ====================================================
# BLOCO 9: CÁLCULOS DE TEMPO E RANKING
# ====================================================
dias_brutos, dias_seguros, ultima_atualizacao = Utilitarios.calcular_dias_uteis(df)

ranking = pd.DataFrame()
ranking_dia = pd.DataFrame()

if "Nome Equipe" in df.columns:
    ranking, ranking_dia = ProcessamentoDados.calcular_rankings(
        df, dias_brutos, dias_seguros
    )
else:
    st.warning(
        "⚠️ A coluna 'Nome Equipe' não foi encontrada. O ranking não pode ser gerado."
    )
    st.stop()

# ====================================================
# BLOCO 10: EXIBIÇÃO DA TABELA E TOGGLE
# ====================================================
col_titulo, col_toggle = st.columns([3, 1])
with col_titulo:
    st.subheader("📊 Pontos, Metas e Projeção")
with col_toggle:
    por_dia = st.toggle("Modo: Meta Diária")

df_exibir = ranking_dia if por_dia else ranking
colunas_formatar = [
    c for c in df_exibir.columns if "Meta" in c or c in ["Pontos", "Projeção"]
]
formato_dict = {col: "{:,.1f}" for col in colunas_formatar}

st.dataframe(
    df_exibir.style.format(formatter=cast(Any, formato_dict))
    .map(Utilitarios.negrito, subset=["Pontos"])
    .map(Utilitarios.colorir_metas, subset=["Pontos"])
    .map(Utilitarios.colorir_projecao, subset=["Projeção"]),
    use_container_width=True,
    height=450,
    hide_index=True,
)

# ====================================================
# BLOCO 11: EXPORTAÇÃO EXCEL, MAPAS E GRÁFICO
# ====================================================
nome_arq = "ranking_meta_por_dia.xlsx" if por_dia else "ranking_meta_geral.xlsx"
st.download_button(
    label=f"📥 Baixar {nome_arq.replace('.xlsx', '').replace('_', ' ').title()}",
    data=Utilitarios.exportar_excel(df_exibir),
    file_name=nome_arq,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.divider()

# ====================================================
# SEÇÃO DE MAPAS (CIDADE vs EQUIPE)
# ====================================================
st.subheader("🌍 Análise Geográfica")

if "lat" in df.columns and "lon" in df.columns:
    tab_cidade, tab_equipe = st.tabs(["📍 Visão por Cidade", "👥 Visão por Equipe"])

    with tab_cidade:
        if "Cidade" in df.columns:
            df_cidades = df.groupby("Cidade").agg({
                "lat": "mean",
                "lon": "mean",
                "Pontos": "sum"
            }).reset_index()
            
            fig_cidade = Graficos.mapa_pontos(df_cidades, "Cidade")
            if fig_cidade:
                # ADICIONADO key="mapa_cidades"
                st.plotly_chart(fig_cidade, use_container_width=True, key="mapa_cidades")
        else:
            st.warning("⚠️ A coluna 'Cidade' não foi encontrada nos dados.")

    with tab_equipe:
        df_equipes_mapa = df.groupby(["Nome Equipe", "Supervisor"]).agg({
            "lat": "mean",
            "lon": "mean",
            "Pontos": "sum"
        }).reset_index()
        
        fig_equipe = Graficos.mapa_pontos(df_equipes_mapa, "Nome Equipe")
        if fig_equipe:
            # ADICIONADO key="mapa_equipes"
            st.plotly_chart(fig_equipe, use_container_width=True, key="mapa_equipes")
else:
    st.info("ℹ️ Para exibir os mapas, adicione as colunas 'lat', 'lon' e 'Cidade' na sua planilha.")

st.divider()
st.subheader("📊 Top 10 Equipes por Pontos")

if not ranking.empty:
    # ADICIONADO key="grafico_barras_top10"
    st.plotly_chart(
        Graficos.grafico_barras(ranking.head(10), "Nome Equipe", "Pontos"),
        use_container_width=True,
        key="grafico_barras_top10"
    )

if pd.notna(ultima_atualizacao):
    st.caption(
        f"🕒 ***Última Atualização dos Dados:*** {pd.to_datetime(ultima_atualizacao).strftime('%d/%m/%Y')}"
    )