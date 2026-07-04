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
        "azul": {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde": {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "laranja": {"fundo": "#FFF7ED", "texto": "#C2410C", "borda": "#F97316", "titulo": "#9A3412"},
        "cinza": {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
    }
    PAGINA = {"titulo": "📈 Central de Comando - Operação", "icon": "🚀"}


# ====================================================
# BLOCO 2: COMPONENTES VISUAIS (FRONT-END)
# ====================================================
class ComponenteVisual:
    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul", delta: Optional[str] = None) -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        delta_html = ""
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

        return f"""
        <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px; border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
            <p style="margin: 0; font-size: 14px; color: {cores['titulo']};"><b>{titulo}</b></p>
            <h2 style="margin: 5px 0 0 0; color: {cores['texto']}; font-weight: 900;">{valor}{delta_html}</h2>
        </div>
        """

    @staticmethod
    def exibir_ticker(dados: list) -> str:
        if not dados: return ""
        html_itens = ""
        for item in dados:
            if item.get("variacao") == "positiva": cor, simbolo = "#22c55e", "▲"
            elif item.get("variacao") == "negativa": cor, simbolo = "#ef4444", "▼"
            elif item.get("variacao") == "share": cor, simbolo = "#38bdf8", "◴"
            else: cor, simbolo = "#94a3b8", "■"
            html_itens += f'<span style="margin: 0 40px; font-family: \'Roboto\', sans-serif; font-size: 15px; white-space: nowrap;"><span style="color: #94a3b8; font-weight: 500;">{item.get("label", "")}:</span><span style="font-weight: 700; color: #FFFFFF; margin-left: 8px;">{item.get("valor", "")}</span><span style="color: {cor}; font-weight: 700; margin-left: 6px; font-size: 13px;">{simbolo} {item.get("delta", "")}</span></span><span style="color: #334155; margin: 0 15px;">|</span>'

        return f"""<style>.ticker-wrapper {{ width: 100%; overflow: hidden; background: linear-gradient(90deg, #0f172a 0%, #1e293b 50%, #0f172a 100%); padding: 12px 0; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); margin-bottom: 25px; position: relative; }} .ticker-wrapper::before, .ticker-wrapper::after {{ content: ''; position: absolute; top: 0; bottom: 0; width: 60px; z-index: 2; }} .ticker-wrapper::before {{ left: 0; background: linear-gradient(90deg, #0f172a, transparent); }} .ticker-wrapper::after {{ right: 0; background: linear-gradient(90deg, transparent, #0f172a); }} .ticker-content {{ display: flex; width: max-content; animation: scroll 35s linear infinite; }} .ticker-wrapper:hover .ticker-content {{ animation-play-state: paused; }} @keyframes scroll {{ 0% {{ transform: translate3d(0, 0, 0); }} 100% {{ transform: translate3d(-50%, 0, 0); }} }} </style> <div class="ticker-wrapper"><div class="ticker-content">{html_itens}{html_itens}</div></div>"""

    # NOVO: Gamificação - Pódio Top 3
    @staticmethod
    def gerar_podio(ranking_df: pd.DataFrame):
        if len(ranking_df) < 3: return
        top3 = ranking_df.head(3).reset_index()
        
        c2, c1, c3 = st.columns([1, 1.2, 1]) # O meio é ligeiramente maior
        
        # Função interna para gerar o HTML da medalha
        def medalha_html(nome, pontos, pos, cor_fundo, cor_borda, icone):
            return f"""<div style="background-color: {cor_fundo}; border: 2px solid {cor_borda}; border-radius: 10px; padding: 15px; text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                <h1 style="margin:0; font-size: 30px;">{icone}</h1>
                <h4 style="margin: 5px 0; color: #334155;">{nome}</h4>
                <h3 style="margin: 0; color: {cor_borda};">{pontos:,.1f} pts</h3>
            </div>"""

        with c1: st.markdown(medalha_html(top3.iloc[0]['Nome Equipe'], top3.iloc[0]['Pontos'], 1, "#FEF9C3", "#EAB308", "🥇 1º Lugar"), unsafe_allow_html=True)
        with c2: st.markdown(medalha_html(top3.iloc[1]['Nome Equipe'], top3.iloc[1]['Pontos'], 2, "#F1F5F9", "#94A3B8", "🥈 2º Lugar"), unsafe_allow_html=True)
        with c3: st.markdown(medalha_html(top3.iloc[2]['Nome Equipe'], top3.iloc[2]['Pontos'], 3, "#FFEDD5", "#F97316", "🥉 3º Lugar"), unsafe_allow_html=True)

    # NOVO: Assistente Virtual (IA)
    @staticmethod
    def gerar_insight_ia(media: float, dias_brutos: int, var_pontos: tuple):
        mensagem = ""
        if media >= 400:
            mensagem = f"🚀 **Visão da IA:** Operação em Alta Performance! A média de {media:.1f} pontos por equipe ultrapassa o teto máximo. Mantenha o ritmo para fechar o mês com recorde."
            st.success(mensagem)
        elif media >= 300:
            mensagem = f"✅ **Visão da IA:** Operação Estável. Média de {media:.1f} pontos garante o atingimento da meta base. Foco em puxar os retardatários para garantir a projeção."
            st.info(mensagem)
        else:
            mensagem = f"⚠️ **Visão da IA:** Alerta de Performance! A média de {media:.1f} pontos está abaixo da linha de corte (300). Restam poucos dias para reverter a tendência."
            st.warning(mensagem)


# ====================================================
# BLOCO 3: FUNÇÕES UTILITÁRIAS E ESTILOS
# ====================================================
class Utilitarios:
    @staticmethod
    def encontrar_coluna_data(df: pd.DataFrame) -> Optional[str]:
        # NOVO: Helper para achar a coluna de data para o gráfico de evolução
        possiveis = ["Data Agendamento", "Data Conclusão", "Data", "Date", "Data_Execucao"]
        for col in possiveis:
            if col in df.columns: return col
        return None

    @staticmethod
    def calcular_variacao(valor_filtrado, valor_geral) -> tuple:
        if valor_geral == 0 or pd.isna(valor_geral): return "neutra", "S/D"
        if abs(valor_filtrado - valor_geral) < 0.0001: return "neutra", "Visão Geral"
        percentual = ((valor_filtrado - valor_geral) / valor_geral) * 100
        if percentual > 0: return "positiva", f"+{percentual:.1f}%"
        elif percentual < 0: return "negativa", f"{percentual:.1f}%"
        return "neutra", "0%"

    @staticmethod
    def calcular_share(valor_filtrado, valor_geral) -> tuple:
        if valor_geral == 0 or pd.isna(valor_geral): return "neutra", "0%"
        if abs(valor_filtrado - valor_geral) < 0.0001: return "neutra", "Visão Geral"
        return "share", f"{(valor_filtrado / valor_geral) * 100:.1f}% do Total"

    @staticmethod
    def formatar_numero(valor: float) -> str:
        return f"{valor:,.0f}".replace(",", ".")

    @staticmethod
    def colorir_metas(valor):
        if 275 <= valor < 300: return "background-color: #FEF08A; color: #9A3412; font-weight: bold"
        if 300 <= valor < 400: return "background-color: #BBF7D0; color: #166534; font-weight: bold"
        if valor >= 400: return "background-color: #1E3A8A; color: #FFFFFF; font-weight: bold"
        return "background-color: #F8FAFC"

    @staticmethod
    def colorir_projecao(valor):
        return "background-color: #334155; color: white; font-weight: bold"

    @staticmethod
    def negrito(valor):
        return "font-weight: bold"

    @staticmethod
    def calcular_dias_uteis(df: pd.DataFrame) -> tuple:
        col_data = Utilitarios.encontrar_coluna_data(df)

        # 1. Descobre a data baseada no RELATÓRIO (não no calendário do PC)
        if col_data and pd.notna(df[col_data].max()):
            data_maxima = pd.to_datetime(df[col_data].max()).date()
        else:
            data_maxima = datetime.date.today()

        ano_ref, mes_ref = data_maxima.year, data_maxima.month

        # 2. Descobre o primeiro e último dia do mês do relatório
        primeiro_dia = datetime.date(ano_ref, mes_ref, 1)
        _, ultimo_dia_num = calendar.monthrange(ano_ref, mes_ref)
        ultimo_dia = datetime.date(ano_ref, mes_ref, ultimo_dia_num)

        # 3. Converte para o padrão do Numpy
        primeiro_dia_np = np.datetime64(primeiro_dia)
        data_maxima_np = np.datetime64(data_maxima)
        ultimo_dia_np = np.datetime64(ultimo_dia)

        # 4. Cálculos de Dias Úteis (Regra: Seg a Sáb = "1111110")
        # Total de dias úteis no mês inteiro:
        total_dias_mes = np.busday_count(primeiro_dia_np, ultimo_dia_np + np.timedelta64(1, "D"), weekmask="1111110")
        
        # Dias que já se passaram até a data do relatório:
        dias_passados = np.busday_count(primeiro_dia_np, data_maxima_np + np.timedelta64(1, "D"), weekmask="1111110")
        
        # Dias que ainda faltam para o mês acabar:
        dias_brutos = max(0, total_dias_mes - dias_passados)
        dias_seguros = max(1, dias_brutos) # Evita divisão por zero nas metas diárias

        return dias_brutos, dias_seguros, data_maxima, dias_passados

    @staticmethod
    def exportar_excel(dataframe: pd.DataFrame) -> bytes:
        # Mantido seu código perfeito de exportação
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Ranking")
            ws = writer.sheets["Ranking"]
            cor_cabecalho = PatternFill(start_color="FF012869", end_color="FF012869", fill_type="solid")
            f_cabecalho = Font("Calibri", size=10.5, bold=True, color="FFFFFFFF")
            borda = Border(left=Side(style="thin", color="FFD9D9D9"), right=Side(style="thin", color="FFD9D9D9"), top=Side(style="thin", color="FFD9D9D9"), bottom=Side(style="thin", color="FFD9D9D9"))
            for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                for celula in row:
                    celula.border = borda
                    if celula.row == 1:
                        celula.fill, celula.font, celula.alignment = cor_cabecalho, f_cabecalho, Alignment(horizontal="center", vertical="center")
            for col in ws.columns:
                ws.column_dimensions[get_column_letter(col[0].column)].width = max(max(len(str(cell.value or "")) for cell in col) + 4, 12)
        return output.getvalue()


# ====================================================
# BLOCO 4: PROCESSAMENTO DE NEGÓCIO E MATEMÁTICA
# ====================================================
class ProcessamentoDados:
    @staticmethod
    def calcular_rankings(df: pd.DataFrame, dias_brutos: int, dias_seguros: int, dias_passados: int) -> tuple:
        base_ranking = df.groupby(["CódAuxEquipe", "Nome Equipe", "Supervisor"])["Pontos"].sum().reset_index().sort_values("Pontos", ascending=False)
        
        # Se a planilha tem os dias do técnico, usa. Se não, usa os dias passados do mês!
        if "Dias Trab Tecnico" in df.columns:
            dias_trabalhados = base_ranking["Nome Equipe"].map(df.groupby("Nome Equipe")["Dias Trab Tecnico"].max()).fillna(dias_passados).astype(int)
        else:
            dias_trabalhados = pd.Series(dias_passados, index=base_ranking.index)
            
        # Evita divisão por zero (se for dia 1 ou feriado)
        dias_trabalhados = dias_trabalhados.replace(0, 1)

        media_pontos = base_ranking["Pontos"] / dias_trabalhados
        
        # A Mágica: Pontos Atuais + (Média x Dias que Faltam pro mês acabar)
        projecao = base_ranking["Pontos"] + (media_pontos * dias_brutos)
        
        ranking = base_ranking.copy()
        ranking.insert(0, "Posição", range(1, len(ranking) + 1))
        for m in [300, 350, 375, 400]: ranking[f"Meta | {m}"] = ranking["Pontos"] - m
        ranking["Projeção"] = projecao

        ranking_dia = base_ranking.copy()
        ranking_dia.insert(0, "Posição", range(1, len(ranking_dia) + 1))
        for m in [300, 350, 375, 400]: ranking_dia[f"Meta Dia | {m}"] = (ranking_dia["Pontos"] - m) / dias_seguros
        ranking_dia["Projeção"] = projecao

        return ranking, ranking_dia

    # NOVO: Calcula distribuição para o Gráfico de Rosca
    @staticmethod
    def calcular_saude_operacao(ranking: pd.DataFrame) -> pd.DataFrame:
        condicoes = [
            (ranking['Pontos'] >= 400),
            (ranking['Pontos'] >= 300) & (ranking['Pontos'] < 400),
            (ranking['Pontos'] < 300)
        ]
        escolhas = ['Alta (400+)', 'Na Meta (300-399)', 'Abaixo (< 300)']
        ranking['Status'] = np.select(condicoes, escolhas, default='Sem Dados')
        return ranking['Status'].value_counts().reset_index()

    # NOVO: Ranking de Supervisores (Média por Equipe)
    @staticmethod
    def ranking_supervisores(ranking: pd.DataFrame) -> pd.DataFrame:
        df_sup = ranking.groupby("Supervisor").agg(
            Qtd_Equipes=('Nome Equipe', 'count'),
            Total_Pontos=('Pontos', 'sum')
        ).reset_index()
        df_sup['Media_por_Equipe'] = df_sup['Total_Pontos'] / df_sup['Qtd_Equipes']
        return df_sup.sort_values('Media_por_Equipe', ascending=True) # Ascending para o px.bar(orientation='h') ficar bonito


# ====================================================
# BLOCO 5: COMPONENTES DE GRÁFICOS
# ====================================================
class Graficos:
    @staticmethod
    def _layout_padrao(fig: Figure, title_x: str = "", title_y: str = "") -> Figure:
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Roboto"), margin=dict(l=0, r=0, t=30, b=0), xaxis=dict(showgrid=False, title=title_x), yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.1)", title=title_y))
        return fig

    @staticmethod
    def grafico_barras(df: pd.DataFrame, x: str, y: str) -> Figure:
        # Mudamos text_auto para True
        fig = px.bar(df, x=x, y=y, text_auto=True, color=y, color_continuous_scale="Oryel")
        # Forçamos a formatação aqui
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", textfont_size=12)
        return Graficos._layout_padrao(fig)

    @staticmethod
    def grafico_barras_horizontal(df: pd.DataFrame, x: str, y: str) -> Figure:
        # Mudamos text_auto para True
        fig = px.bar(df, x=x, y=y, orientation='h', text_auto=True, color=x, color_continuous_scale="Tealgrn")
        # Forçamos a formatação aqui
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", textfont_size=12)
        return Graficos._layout_padrao(fig)

    # NOVO: Gráfico de Rosca (Saúde)
    @staticmethod
    def grafico_rosca(df: pd.DataFrame, names: str, values: str) -> Figure:
        fig = px.pie(df, names=names, values=values, hole=0.6, color=names, color_discrete_map={'Alta (400+)':'#1E3A8A', 'Na Meta (300-399)':'#22C55E', 'Abaixo (< 300)':'#EF4444'})
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=0, b=0), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
        return fig

    # NOVO: Evolução Temporal (Linhas)
    @staticmethod
    def grafico_linhas(df: pd.DataFrame, x: str, y: str, color: str) -> Figure:
        fig = px.line(df, x=x, y=y, color=color, markers=True)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.1)"), margin=dict(l=0, r=0, t=30, b=0))
        return fig

    @staticmethod
    def mapa_pontos(df: pd.DataFrame, titulo_hover: str) -> Optional[Figure]:
        if "lat" not in df.columns or "lon" not in df.columns: return None
        fig = px.scatter_mapbox(df, lat="lat", lon="lon", size="Pontos", color="Pontos", color_continuous_scale="Oryel", hover_name=titulo_hover, hover_data={"lat": False, "lon": False, "Pontos": ":.2f"}, zoom=9, height=500)
        fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0}, paper_bgcolor="rgba(0,0,0,0)")
        return fig

    # NOVO: Mapa de Calor (Heatmap)
    @staticmethod
    def mapa_calor(df: pd.DataFrame) -> Optional[Figure]:
        if "lat" not in df.columns or "lon" not in df.columns: return None
        fig = px.density_mapbox(df, lat='lat', lon='lon', z='Pontos', radius=25, center=dict(lat=-23.55, lon=-46.63), zoom=9, height=500, mapbox_style="open-street-map", color_continuous_scale="Inferno")
        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, paper_bgcolor="rgba(0,0,0,0)")
        return fig


# ====================================================
# BLOCO 6: INICIALIZAÇÃO E DADOS BRUTOS
# ====================================================
st.set_page_config(page_title=Configuracoes.PAGINA["titulo"], page_icon=Configuracoes.PAGINA["icon"], layout="wide")
st.title(Configuracoes.PAGINA["titulo"])

if "dados_prod" not in st.session_state:
    st.warning("⚠️ Carregue os dados na página principal primeiro.")
    st.stop()

prod = st.session_state["dados_prod"]["Prod"].copy()
gpon = st.session_state["dados_prod"]["Gpon"].copy()
prod["Pontos"] = pd.to_numeric(prod["Pontos"], errors="coerce").fillna(0)
gpon["Pontos"] = pd.to_numeric(gpon["Pontos"], errors="coerce").fillna(0)

df = pd.concat([prod, gpon], ignore_index=True)

# DICIONÁRIO DE COORDENADAS
# COORDENADAS_CIDADES = {
#     "SAO PAULO": {"lat": -23.5505, "lon": -46.6333}, "GUARULHOS": {"lat": -23.4555, "lon": -46.5333},
#     "SANTO ANDRE": {"lat": -23.6611, "lon": -46.5333}, "SAO BERNARDO DO CAMPO": {"lat": -23.7000, "lon": -46.5600},
#     "SAO CAETANO DO SUL": {"lat": -23.6250, "lon": -46.5500}, "DIADEMA": {"lat": -23.6800, "lon": -46.6300},
#     "MAUA": {"lat": -23.6700, "lon": -46.4700}, "ABCDM": {"lat": -23.6600, "lon": -46.5500},
# }
# def atribuir_coords(cidade):
#     if pd.isna(cidade): return None, None
#     cid = str(cidade).strip().upper() # Upper para garantir segurança
#     if cid in COORDENADAS_CIDADES: return COORDENADAS_CIDADES[cid]["lat"], COORDENADAS_CIDADES[cid]["lon"]
#     return None, None

# if "Cidade" in df.columns:
#     df[['lat', 'lon']] = df['Cidade'].apply(lambda x: pd.Series(atribuir_coords(x)))

TOTAL_GERAL_PONTOS = df["Pontos"].sum()
TOTAL_GERAL_OS = len(df)
TOTAL_GERAL_EQUIPES = df["Nome Equipe"].nunique() if "Nome Equipe" in df.columns else 0
MEDIA_GERAL_PONTOS = TOTAL_GERAL_PONTOS / TOTAL_GERAL_EQUIPES if TOTAL_GERAL_EQUIPES > 0 else 0


# ====================================================
# BLOCO 7: FILTROS (SIDEBAR)
# ====================================================
st.sidebar.header("🎯 Filtros Avançados")
if "Projeto" in df.columns:
    proj_sel = st.sidebar.selectbox("Projeto:", ["Todos"] + sorted(df["Projeto"].dropna().astype(str).unique()))
    if proj_sel != "Todos": df = df[df["Projeto"] == proj_sel]

if "Supervisor" in df.columns:
    sup_sel = st.sidebar.selectbox("Supervisor:", ["Todos"] + sorted(df["Supervisor"].dropna().astype(str).unique()))
    if sup_sel != "Todos": df = df[df["Supervisor"] == sup_sel]

if "Nome Equipe" in df.columns:
    equipe_sel = st.sidebar.selectbox("Equipe:", ["Todos"] + sorted(df["Nome Equipe"].dropna().astype(str).unique()))
    if equipe_sel != "Todos": df = df[df["Nome Equipe"] == equipe_sel]

if st.sidebar.button("🔄 Limpar Filtros"): st.rerun()


# ====================================================
# BLOCO 8: CÁLCULOS E CARDS
# ====================================================
dias_brutos, dias_seguros, ultima_atualizacao, dias_passados = Utilitarios.calcular_dias_uteis(df)

total_equipes_filtro = df["Nome Equipe"].nunique() if "Nome Equipe" in df.columns else 0
total_os_filtro = len(df)
total_pontos_filtro = df["Pontos"].sum() if "Pontos" in df.columns else 0
media_pontos_filtro = total_pontos_filtro / total_equipes_filtro if total_equipes_filtro > 0 else 0

var_pontos = Utilitarios.calcular_share(total_pontos_filtro, TOTAL_GERAL_PONTOS)
var_os = Utilitarios.calcular_share(total_os_filtro, TOTAL_GERAL_OS)
var_equipes = Utilitarios.calcular_share(total_equipes_filtro, TOTAL_GERAL_EQUIPES)
var_media = Utilitarios.calcular_variacao(media_pontos_filtro, MEDIA_GERAL_PONTOS)

# Renderiza Ticker e IA
st.markdown(ComponenteVisual.exibir_ticker([
    {"label": "Pontos", "valor": Utilitarios.formatar_numero(total_pontos_filtro), "variacao": var_pontos[0], "delta": var_pontos[1]},
    {"label": "O.S.", "valor": Utilitarios.formatar_numero(total_os_filtro), "variacao": var_os[0], "delta": var_os[1]},
    {"label": "Equipes", "valor": str(total_equipes_filtro), "variacao": var_equipes[0], "delta": var_equipes[1]},
    {"label": "Média/Equipe", "valor": Utilitarios.formatar_numero(media_pontos_filtro), "variacao": var_media[0], "delta": var_media[1]},
]), unsafe_allow_html=True)

ComponenteVisual.gerar_insight_ia(media_pontos_filtro, dias_brutos, var_pontos)

# Renderiza Cards
c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(ComponenteVisual.criar_card("Total Pontos (Geral)", Utilitarios.formatar_numero(TOTAL_GERAL_PONTOS), "cinza"), unsafe_allow_html=True)
with c2: st.markdown(ComponenteVisual.criar_card("Total Pontos (Filtro)", Utilitarios.formatar_numero(total_pontos_filtro), "azul", var_pontos[1]), unsafe_allow_html=True)
with c3: st.markdown(ComponenteVisual.criar_card("Equipes (Filtro)", str(total_equipes_filtro), "verde", var_equipes[1]), unsafe_allow_html=True)
with c4: st.markdown(ComponenteVisual.criar_card("Total O.S. (Filtro)", Utilitarios.formatar_numero(total_os_filtro), "laranja", var_os[1]), unsafe_allow_html=True)

st.divider()

# ====================================================
# BLOCO 9: ESTRUTURA DE ABAS MESTRES
# ====================================================
ranking = pd.DataFrame()
if "Nome Equipe" in df.columns:
    ranking, ranking_dia = ProcessamentoDados.calcular_rankings(df, dias_brutos, dias_seguros, dias_passados)

aba_ranking, aba_executivo, aba_evolucao = st.tabs([
    "🏆 Ranking & Metas", 
    "👔 Visão Executiva", 
    "📈 Evolução Temporal"
])

# ----------------- ABA 1: RANKING E METAS -----------------
with aba_ranking:
    st.subheader("🥇 Pódio - Top 3 Equipes")
    ComponenteVisual.gerar_podio(ranking)
    
    st.write("---")
    col_titulo, col_toggle = st.columns([3, 1])
    with col_titulo: st.subheader("📊 Tabela Geral de Metas e Projeção")
    with col_toggle: por_dia = st.toggle("Modo: Meta Diária", key="tg_meta_dia")

    df_exibir = ranking_dia if por_dia else ranking
    formatos = {c: "{:,.1f}" for c in df_exibir.columns if "Meta" in c or c in ["Pontos", "Projeção"]}

    st.dataframe(df_exibir.style.format(formatter=formatos).map(Utilitarios.negrito, subset=["Pontos"]).map(Utilitarios.colorir_metas, subset=["Pontos"]).map(Utilitarios.colorir_projecao, subset=["Projeção"]), use_container_width=True, height=400, hide_index=True)

    nome_arq = "ranking_diario.xlsx" if por_dia else "ranking_geral.xlsx"
    st.download_button(f"📥 Baixar Excel", data=Utilitarios.exportar_excel(df_exibir), file_name=nome_arq, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ----------------- ABA 2: VISÃO EXECUTIVA -----------------
with aba_executivo:
    st.subheader("👔 Performance de Gestão")
    c_exec1, c_exec2 = st.columns([1, 2])
    
    with c_exec1:
        st.markdown("**Saúde da Operação (Faixa de Metas)**")
        df_saude = ProcessamentoDados.calcular_saude_operacao(ranking)
        st.plotly_chart(Graficos.grafico_rosca(df_saude, "Status", "count"), use_container_width=True, key="graf_saude")
        
    with c_exec2:
        st.markdown("**Ranking de Supervisores (Média pts por Equipe)**")
        df_sup = ProcessamentoDados.ranking_supervisores(ranking)
        st.plotly_chart(Graficos.grafico_barras_horizontal(df_sup, "Media_por_Equipe", "Supervisor"), use_container_width=True, key="graf_sup")

# ----------------- ABA 3: LOGÍSTICA E MAPAS -----------------
# with aba_mapa:
#     st.subheader("🌍 Análise Geográfica de Densidade e Pontos")
#     st.info("O componente de mapa foi desativado!!")
    # if "lat" in df.columns and "lon" in df.columns:
    #     t_calor, t_cidade, t_equipe = st.tabs(["🔥 Mapa de Calor (Demanda)", "📍 Visão por Cidade", "👥 Visão por Equipe"])

    #     with t_calor:
    #         fig_calor = Graficos.mapa_calor(df)
    #         if fig_calor: st.plotly_chart(fig_calor, use_container_width=True, key="mapa_calor")
            
    #     with t_cidade:
    #         if "Cidade" in df.columns:
    #             df_cidades = df.groupby("Cidade").agg({"lat": "mean", "lon": "mean", "Pontos": "sum"}).reset_index()
    #             fig_cidade = Graficos.mapa_pontos(df_cidades, "Cidade")
    #             if fig_cidade: st.plotly_chart(fig_cidade, use_container_width=True, key="mapa_cid")

    #     with t_equipe:
    #         df_equipes_mapa = df.groupby(["Nome Equipe", "Supervisor"]).agg({"lat": "mean", "lon": "mean", "Pontos": "sum"}).reset_index()
    #         fig_equipe = Graficos.mapa_pontos(df_equipes_mapa, "Nome Equipe")
    #         if fig_equipe: st.plotly_chart(fig_equipe, use_container_width=True, key="mapa_eq")
    # else:
    #     st.info("ℹ️ Adicione as colunas 'lat', 'lon' e 'Cidade' para habilitar os mapas.")

# ----------------- ABA 4: EVOLUÇÃO TEMPORAL -----------------
with aba_evolucao:
    col_data = Utilitarios.encontrar_coluna_data(df)
    st.subheader("📈 Curva de Tendência Diária")
    
    if col_data:
        # Pega as top 5 equipes para não poluir o gráfico
        top_equipes_lista = ranking.head(5)["Nome Equipe"].tolist()
        df_evolucao = df[df["Nome Equipe"].isin(top_equipes_lista)].copy()
        
        # Agrupa por dia e equipe
        df_evolucao[col_data] = pd.to_datetime(df_evolucao[col_data]).dt.date
        df_agrupado = df_evolucao.groupby([col_data, "Nome Equipe"])["Pontos"].sum().reset_index()
        
        # Faz a soma cumulativa para mostrar o crescimento
        df_agrupado["Pontos Acumulados"] = df_agrupado.groupby("Nome Equipe")["Pontos"].cumsum()
        
        fig_linha = Graficos.grafico_linhas(df_agrupado, col_data, "Pontos Acumulados", "Nome Equipe")
        st.plotly_chart(fig_linha, use_container_width=True, key="graf_linha")
        st.caption("Mostrando a evolução de pontos acumulados das Top 5 equipes atuais.")
    else:
        st.info("ℹ️ Para ver a evolução, sua planilha precisa de uma coluna de Data (ex: 'Data Agendamento' ou 'Data Conclusão').")

# Rodapé com atualização
if pd.notna(ultima_atualizacao):
    st.sidebar.divider()
    st.sidebar.caption(f"🕒 **Última Atualização:**\n{pd.to_datetime(ultima_atualizacao).strftime('%d/%m/%Y')}")