import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from typing import Optional, Tuple
from io import BytesIO

# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS
# ====================================================
class Configuracoes:
    TEMAS_CARD = {
        "azul": {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde": {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "laranja": {"fundo": "#FFF7ED", "texto": "#C2410C", "borda": "#F97316", "titulo": "#9A3412"},
        "roxo": {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#581C87"},
        "vermelho": {"fundo": "#FEF2F2", "texto": "#B91C1C", "borda": "#EF4444", "titulo": "#991B1B"},
        "cinza": {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
    }
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    SLA_QUEBRA_MAXIMA = 0.20  # 20% (FECHAMENTO)


# ====================================================
# BLOCO 2: UTILITÁRIOS E COMPONENTES VISUAIS
# ====================================================
class Utilitarios:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras_chave: list) -> Optional[str]:
        if df is None or df.empty:
            return None
        cols_upper = {c.upper(): c for c in df.columns}
        for p in palavras_chave:
            if p.upper() in cols_upper:
                return cols_upper[p.upper()]
        return None

    @staticmethod
    def classificar_os_series(status_series: pd.Series) -> pd.Series:
        """Classifica rigorosamente com base no novo conceito de Status (vetorizado)."""
        s = status_series.fillna("").astype(str).str.strip().str.upper()

        executada = (s == "EXECUTADA")
        nao_exec = s.isin(["NÃO EXECUTADA", "NAO EXECUTADA"])

        return pd.Series(
            np.select([executada, nao_exec], ["Executada", "Não Executada"], default="Pendente"),
            index=status_series.index
        )


class ComponenteVisual:
    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul", subtitulo: str = "") -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 15px; border-radius: 8px; border-left: 5px solid {cores['borda']}; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin: 0; font-size: 13px; color: {cores['titulo']}; font-weight: bold; text-transform: uppercase;">{titulo}</p>
            <h2 style="margin: 5px 0 0 0; color: {cores['texto']}; font-weight: 900; font-size: 28px;">{valor}</h2>
            <p style="margin: 5px 0 0 0; font-size: 12px; color: #64748B; font-weight: 500;">{subtitulo}</p>
        </div>
        """


# ====================================================
# BLOCO 3: PROCESSAMENTO DE DADOS
# ====================================================
class Dados:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
        try:
            name = filename.lower()
            bio = BytesIO(file_bytes)
            if name.endswith(".csv"):
                return pd.read_csv(bio, sep=None, engine="python", encoding="utf-8")
            if name.endswith((".xlsx", ".xls")):
                return pd.read_excel(bio, engine="openpyxl")
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_gsheets() -> pd.DataFrame:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df_gs = conn.read(spreadsheet=Configuracoes.URL_ATIVOS)
            if df_gs is None or df_gs.empty:
                return pd.DataFrame()

            df_gs.columns = df_gs.columns.astype(str).str.strip().str.upper()

            col_log = Utilitarios.buscar_coluna(df_gs, ['LOGIN', 'ID', 'MATRÍCULA', 'MATRICULA'])
            col_tec = Utilitarios.buscar_coluna(df_gs, ['TÉCNICO', 'NOME'])
            col_mon = Utilitarios.buscar_coluna(df_gs, ['MONITOR', 'GESTOR'])

            rename = {}
            if col_log: rename[col_log] = "LOGIN"
            if col_tec: rename[col_tec] = "TÉCNICO"
            if col_mon: rename[col_mon] = "MONITOR"
            df_gs = df_gs.rename(columns=rename)

            keep = [c for c in ["LOGIN", "TÉCNICO", "MONITOR"] if c in df_gs.columns]
            df_gs = df_gs[keep].copy()

            if "LOGIN" in df_gs.columns:
                df_gs["LOGIN"] = (
                    df_gs["LOGIN"].astype(str).str.replace(".0", "", regex=False).str.strip().str.upper()
                )
                df_gs = df_gs.drop_duplicates(subset=["LOGIN"], keep="last")

            return df_gs
        except Exception:
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(show_spinner=False)
    def preparar_base(df: pd.DataFrame, df_gsheets: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.astype(str).str.strip().str.upper()

        # TOTAL DE TAREFAS
        if "TOTAL DE TAREFAS" not in df.columns:
            df["TOTAL DE TAREFAS"] = 1
        df["TOTAL DE TAREFAS"] = pd.to_numeric(df["TOTAL DE TAREFAS"], errors="coerce").fillna(0)

        # Drop contrato vazio
        if "CONTRATO" in df.columns:
            df = df.dropna(subset=["CONTRATO"])

        # Flags de Serviço
        tipo_os = df.get("TIPO DE O.S 1", df.get("TIPO O.S 1", pd.Series("", index=df.index))).astype(str).str.upper()
        hab_trab = df.get("HABILIDADE DE TRABALHO", pd.Series("", index=df.index)).astype(str).str.upper()

        df["Check_GPON"] = hab_trab.str.contains(r"PON\(1/100\)", regex=True, na=False)
        df["Check_ND"] = tipo_os.str.contains("ADESAO", na=False)
        df["Check_Migracao"] = (tipo_os.str.contains("MUDANCA DE PACOTE", na=False)) & (df["Check_GPON"] == True)
        df["Check_PME"] = hab_trab.str.contains("PME", na=False)

        # Cruzamento com GSheets (Login)
        col_login = Utilitarios.buscar_coluna(df, ["LOGIN", "LOGIN DO TÉCNICO", "USUÁRIO", "USUARIO", "MATRÍCULA", "MATRICULA"])
        if col_login and df_gsheets is not None and (not df_gsheets.empty) and ("LOGIN" in df_gsheets.columns):
            df[col_login] = df[col_login].astype(str).str.replace(".0", "", regex=False).str.strip().str.upper()
            df_gsheets2 = df_gsheets[["LOGIN", "TÉCNICO", "MONITOR"]].drop_duplicates("LOGIN", keep="last")

            for c in ["TÉCNICO", "MONITOR"]:
                if c in df.columns:
                    df = df.drop(columns=[c])

            df = df.merge(df_gsheets2, left_on=col_login, right_on="LOGIN", how="left")

        df["TÉCNICO"] = df.get("TÉCNICO", pd.Series("NÃO MAPEADO", index=df.index)).fillna("NÃO MAPEADO")
        df["MONITOR"] = df.get("MONITOR", pd.Series("SEM MONITOR", index=df.index)).fillna("SEM MONITOR")

        return df


# ====================================================
# BLOCO 3.1: MÉTRICAS (ATUAL, FECHAMENTO, CENÁRIOS, SLA)
# ====================================================
def calcular_quebra_atual(df_alvo: pd.DataFrame) -> Tuple[float, float]:
    """
    Quebra Atual (OFICIAL): Não Executada / (Executada + Não Executada)
    Retorna: (volume_considerado, taxa_atual)
    """
    if df_alvo is None or df_alvo.empty:
        return 0.0, 0.0
    exec_ = float(df_alvo.loc[df_alvo["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
    naoexec = float(df_alvo.loc[df_alvo["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())
    considerado = exec_ + naoexec
    taxa = (naoexec / considerado) if considerado > 0 else 0.0
    return considerado, taxa


def projetar_fechamento(df_alvo: pd.DataFrame, p_pendente: float) -> dict:
    """
    Fechamento (proj) para SLA:
      (Não Exec + Pendente*p) / (Exec + Não Exec + Pendente) = (Não Exec + Pendente*p) / Alocado
    """
    if df_alvo is None or df_alvo.empty:
        return {
            "alocado": 0.0, "exec": 0.0, "naoexec": 0.0, "pend": 0.0,
            "quebra_atual": 0.0, "fechamento_proj": 0.0, "naoexec_proj": 0.0
        }

    alocado = float(df_alvo["TOTAL DE TAREFAS"].sum())
    exec_ = float(df_alvo.loc[df_alvo["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
    naoexec = float(df_alvo.loc[df_alvo["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())
    pend = max(0.0, alocado - exec_ - naoexec)

    considerado, quebra_atual = calcular_quebra_atual(df_alvo)
    naoexec_proj = naoexec + pend * float(p_pendente)
    fechamento_proj = (naoexec_proj / alocado) if alocado > 0 else 0.0

    return {
        "alocado": alocado,
        "exec": exec_,
        "naoexec": naoexec,
        "pend": pend,
        "quebra_atual": quebra_atual,
        "fechamento_proj": fechamento_proj,
        "naoexec_proj": naoexec_proj,
    }


def projetar_cenarios(df_alvo: pd.DataFrame, p_ot: float, p_base: float, p_pess: float) -> dict:
    return {
        "Otimista": projetar_fechamento(df_alvo, p_ot),
        "Base": projetar_fechamento(df_alvo, p_base),
        "Pessimista": projetar_fechamento(df_alvo, p_pess),
    }


def folga_sla_fechamento(df_alvo: pd.DataFrame, sla: float) -> dict:
    """
    Quantas OS do Pendente ainda podem virar 'Não Executada' sem estourar o SLA no FECHAMENTO.
    Regra: (NãoExec + x) / Alocado <= SLA  => x <= SLA*Alocado - NãoExec
    """
    if df_alvo is None or df_alvo.empty:
        return {
            "alocado": 0.0, "exec": 0.0, "naoexec": 0.0, "pend": 0.0,
            "limite_ne_total": 0.0, "folga_ne_pendente": 0.0,
            "folga_pct_pendente": 0.0, "precisa_executar_pendente": 0.0,
            "estourado": False
        }

    alocado = float(df_alvo["TOTAL DE TAREFAS"].sum())
    exec_ = float(df_alvo.loc[df_alvo["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
    naoexec = float(df_alvo.loc[df_alvo["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())
    pend = max(0.0, alocado - exec_ - naoexec)

    limite_ne_total = sla * alocado
    folga_total = limite_ne_total - naoexec

    estourado = (folga_total < 0)

    folga_ne_pendente = max(0.0, min(pend, folga_total))
    folga_pct_pendente = (folga_ne_pendente / pend) if pend > 0 else 0.0
    precisa_executar_pendente = max(0.0, pend - folga_ne_pendente)

    return {
        "alocado": alocado,
        "exec": exec_,
        "naoexec": naoexec,
        "pend": pend,
        "limite_ne_total": limite_ne_total,
        "folga_ne_pendente": folga_ne_pendente,
        "folga_pct_pendente": folga_pct_pendente,
        "precisa_executar_pendente": precisa_executar_pendente,
        "estourado": estourado,
    }


def tabela_cenarios_por_grupo(
    df: pd.DataFrame, grupo: str,
    p_ot: float, p_base: float, p_pess: float,
    min_alocado: float = 5
) -> pd.DataFrame:
    """
    Ranking por grupo:
      - Quebra Atual = NE/(E+NE)
      - Fechamento (Ot/Base/Pess) = (NE + Pend*p)/Alocado
    """
    if df is None or df.empty or grupo not in df.columns or "Status Contrato" not in df.columns:
        return pd.DataFrame()

    pv = pd.pivot_table(
        df,
        index=grupo,
        columns="Status Contrato",
        values="TOTAL DE TAREFAS",
        aggfunc="sum",
        fill_value=0
    )

    for c in ["Executada", "Não Executada", "Pendente"]:
        if c not in pv.columns:
            pv[c] = 0.0

    out = pv.reset_index().copy()
    out["Executada"] = out["Executada"].astype(float)
    out["Não Executada"] = out["Não Executada"].astype(float)
    out["Pendente"] = out["Pendente"].astype(float)

    out["Considerado"] = out["Executada"] + out["Não Executada"]
    out["Alocado"] = out["Considerado"] + out["Pendente"]

    out["Quebra Atual"] = np.where(out["Considerado"] > 0, out["Não Executada"] / out["Considerado"], 0.0)

    def proj(p):
        return np.where(out["Alocado"] > 0, (out["Não Executada"] + out["Pendente"] * p) / out["Alocado"], 0.0)

    out["Fechamento Otimista"] = proj(p_ot)
    out["Fechamento Base"] = proj(p_base)
    out["Fechamento Pessimista"] = proj(p_pess)

    out = out[out["Alocado"] >= float(min_alocado)].copy()
    out = out.sort_values("Fechamento Base", ascending=False)
    return out


# ====================================================
# BLOCO 4: FRONT-END E DASHBOARD
# ====================================================
st.set_page_config(page_title="Gestão de Quebra", page_icon="📊", layout="wide")
st.title("🗣️ Painel Executivo: Quebra de Agenda")

if "df_memoria" not in st.session_state:
    st.session_state["df_memoria"] = None

# --- UPLOAD ---
if st.session_state["df_memoria"] is None:
    arquivo = st.file_uploader("📥 Envie a base de dados (Excel ou CSV)", type=["xlsx", "xls", "csv"])
    if arquivo:
        with st.spinner("Analisando dados e cruzando hierarquia..."):
            df_base = Dados.ler_arquivo_bytes(arquivo.getvalue(), arquivo.name)
            df_gs = Dados.buscar_gsheets()
            st.session_state["df_memoria"] = Dados.preparar_base(df_base, df_gs)
        st.rerun()

# --- DASHBOARD ---
else:
    df_full = st.session_state["df_memoria"]

    col_aviso, col_btn = st.columns([4, 1])
    with col_aviso:
        st.success("✅ Base processada com sucesso!")
    with col_btn:
        if st.button("🔄 Enviar outra base", use_container_width=True):
            st.session_state["df_memoria"] = None
            st.rerun()

    col_status = Utilitarios.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS", "STATUS"])
    col_motivo = Utilitarios.buscar_coluna(df_full, ["MOTIVO", "SUBSTATUS", "MOTIVO BAIXA", "OBSERVAÇÃO", "OBSERVACAO"])

    if not col_status:
        st.error("⚠️ Coluna de 'Status' não encontrada na planilha.")
        st.stop()

    # Status Contrato (vetorizado)
    df_full = df_full.copy()
    df_full["Status Contrato"] = Utilitarios.classificar_os_series(df_full[col_status])

    # --- SIDEBAR DE FILTROS + CENÁRIOS ---
    with st.sidebar:
        st.header("🎯 Filtros")
        df_filtrado = df_full

        qtd_orfaos = int((df_filtrado["TÉCNICO"] == "NÃO MAPEADO").sum()) if "TÉCNICO" in df_filtrado.columns else 0
        if qtd_orfaos > 0:
            st.error(f"⚠️ {qtd_orfaos} logins não existem no Google Sheets.")

        # Filtros Monitor/Técnico
        for col, titulo in [("MONITOR", "👔 Monitor"), ("TÉCNICO", "👤 Técnico")]:
            if col in df_filtrado.columns:
                bloqueados = {"nan", "SEM MONITOR", "NÃO MAPEADO"}
                opcoes = ["Todos"] + sorted([str(x) for x in df_filtrado[col].unique() if str(x) not in bloqueados])
                selecao = st.selectbox(titulo, opcoes)
                if selecao != "Todos":
                    df_filtrado = df_filtrado[df_filtrado[col] == selecao]

        st.divider()
        st.subheader("🔮 Projeção de Fechamento (Pendente → Não Executada)")
        p_ot = st.slider("Otimista (%)", 0, 100, 10, 5) / 100
        p_base = st.slider("Base (%)", 0, 100, 30, 5) / 100   # ajustável
        p_pess = st.slider("Pessimista (%)", 0, 100, 60, 5) / 100

        st.divider()
        st.subheader("🏁 Ranking")
        min_alocado_rank = st.number_input("Mín. OS alocadas (filtro)", min_value=1, value=5, step=1)
        top_n = st.number_input("Top N", min_value=5, value=10, step=1)

    df = df_filtrado.copy()

    # ====================================================
    # KPIs (Atual vs Fechamento Base com SLA)
    # ====================================================
    cen_geral = projetar_cenarios(df, p_ot, p_base, p_pess)
    atual = cen_geral["Base"]["quebra_atual"]              # NE/(E+NE)
    fech_base = cen_geral["Base"]["fechamento_proj"]       # projeção (base) no FECHAMENTO (SLA)
    pend = cen_geral["Base"]["pend"]

    t_exec = cen_geral["Base"]["exec"]
    t_nao_exec = cen_geral["Base"]["naoexec"]
    t_total_rota = cen_geral["Base"]["alocado"]

    st.divider()
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(ComponenteVisual.criar_card("Total Tarefas", f"{t_total_rota:,.0f}", "azul", "Alocado"), unsafe_allow_html=True)
    with c2:
        st.markdown(ComponenteVisual.criar_card("Executadas", f"{t_exec:,.0f}", "verde", "Baixadas"), unsafe_allow_html=True)
    with c3:
        st.markdown(ComponenteVisual.criar_card("Não Executadas", f"{t_nao_exec:,.0f}", "laranja", "Baixadas"), unsafe_allow_html=True)
    with c4:
        st.markdown(ComponenteVisual.criar_card("Pendentes", f"{pend:,.0f}", "cinza", "Em aberto"), unsafe_allow_html=True)
    with c5:
        st.markdown(ComponenteVisual.criar_card("Quebra Atual", f"{atual:,.2%}", "cinza", "NE/(E+NE)"), unsafe_allow_html=True)
    with c6:
        cor_sla = "vermelho" if fech_base > Configuracoes.SLA_QUEBRA_MAXIMA else "roxo"
        st.markdown(
            ComponenteVisual.criar_card(
                "Fechamento (Base)",
                f"{fech_base:,.2%}",
                cor_sla,
                f"SLA {Configuracoes.SLA_QUEBRA_MAXIMA:.0%} (Fechamento)"
            ),
            unsafe_allow_html=True
        )

    # ====================================================
    # Cenários (Otimista / Base / Pessimista)
    # ====================================================
    st.write("---")
    st.markdown("### 🔮 Cenários de Fechamento (para SLA)")

    c_ot, c_ba, c_pe, c_g = st.columns([1, 1, 1, 2])

    def card_cenario(nome: str, tema_padrao: str):
        taxa = cen_geral[nome]["fechamento_proj"]
        neproj = cen_geral[nome]["naoexec_proj"]
        tema = "vermelho" if taxa > Configuracoes.SLA_QUEBRA_MAXIMA else tema_padrao
        return ComponenteVisual.criar_card(nome, f"{taxa:.2%}", tema, f"Não Exec (proj): {neproj:,.0f}")

    with c_ot:
        st.markdown(card_cenario("Otimista", "cinza"), unsafe_allow_html=True)
    with c_ba:
        st.markdown(card_cenario("Base", "roxo"), unsafe_allow_html=True)
    with c_pe:
        st.markdown(card_cenario("Pessimista", "cinza"), unsafe_allow_html=True)

    with c_g:
        df_plot = pd.DataFrame({
            "Cenário": ["Otimista", "Base", "Pessimista"],
            "Fechamento": [
                cen_geral["Otimista"]["fechamento_proj"],
                cen_geral["Base"]["fechamento_proj"],
                cen_geral["Pessimista"]["fechamento_proj"],
            ],
        })
        fig = px.bar(
            df_plot,
            x="Cenário",
            y="Fechamento",
            text=df_plot["Fechamento"].map(lambda x: f"{x:.2%}"),
            color="Fechamento",
            color_continuous_scale="Reds"
        )
        fig.add_hline(y=Configuracoes.SLA_QUEBRA_MAXIMA, line_width=2, line_dash="dash", line_color="black")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(
            yaxis_tickformat=".0%",
            margin=dict(t=10, b=0, l=0, r=0),
            coloraxis_showscale=False,
            yaxis_title="Fechamento (proj)"
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ====================================================
    # Quanto falta para estourar SLA
    # ====================================================
    st.write("---")
    st.markdown("### 🧨 Quanto falta para estourar o SLA (Fechamento)")

    m = folga_sla_fechamento(df, Configuracoes.SLA_QUEBRA_MAXIMA)
    cc1, cc2, cc3 = st.columns([1.2, 1.2, 2])

    with cc1:
        if m["estourado"]:
            tema = "vermelho"
        else:
            tema = "verde" if m["folga_ne_pendente"] > 0 else "laranja"

        st.markdown(
            ComponenteVisual.criar_card(
                "Folga SLA (em OS)",
                f"{np.floor(m['folga_ne_pendente']):,.0f}",
                tema,
                f"Do pendente pode quebrar: {m['folga_pct_pendente']:.1%}"
            ),
            unsafe_allow_html=True
        )

    with cc2:
        st.markdown(
            ComponenteVisual.criar_card(
                "Precisa Executar (mín.)",
                f"{np.ceil(m['precisa_executar_pendente']):,.0f}",
                "azul",
                "Qtd do pendente que não pode virar quebra"
            ),
            unsafe_allow_html=True
        )

    with cc3:
        st.caption("Margem dentro do Pendente antes de estourar o SLA")
        st.progress(min(1.0, max(0.0, float(m["folga_pct_pendente"]))))

        if m["estourado"]:
            excesso = (m["naoexec"] - m["limite_ne_total"])
            st.error(f"SLA já estourado. Excesso atual: {excesso:,.1f} OS acima do limite.")
        elif m["pend"] == 0:
            st.info("Sem pendentes. Fechamento já está definido.")
        else:
            st.info(
                f"Limite de Não Executadas (fechamento): {m['limite_ne_total']:,.1f} | "
                f"Não Executadas atual: {m['naoexec']:,.1f}"
            )

    # ====================================================
    # Projeção por Tipo de Serviço (Base + faixa Ot↔Pess)
    # ====================================================
    st.write("---")
    st.markdown("### 📊 Fechamento Projetado por Tipo de Serviço (Base + faixa Ot↔Pess)")

    servicos = {
        "ND (Adesão)": df[df.get("Check_ND", False) == True],
        "Migração": df[df.get("Check_Migracao", False) == True],
        "Tecnologia GPON": df[df.get("Check_GPON", False) == True],
        "Cliente PME": df[df.get("Check_PME", False) == True],
    }

    def _to_float(value, default=0.0):
        try:
            if hasattr(value, "item"):
                value = value.item()
            return float(value)
        except Exception:
            return default

    rows = []
    for nome, dfx in servicos.items():
        if dfx.empty:
            continue
        c = projetar_cenarios(dfx, p_ot, p_base, p_pess)
        vol_cons, tx_atual = calcular_quebra_atual(dfx)
        rows.append({
            "Serviço": nome,
            "Otimista": _to_float(c["Otimista"]["fechamento_proj"]),
            "Base": _to_float(c["Base"]["fechamento_proj"]),
            "Pessimista": _to_float(c["Pessimista"]["fechamento_proj"]),
            "Atual": _to_float(tx_atual),
            "Vol (cons.)": _to_float(vol_cons),
        })

    df_svc = pd.DataFrame(rows)
    if df_svc.empty:
        st.info("Sem volume suficiente para projeção por serviço.")
    else:
        # cards (base)
        a1, a2, a3, a4 = st.columns(4)
        cols = [a1, a2, a3, a4]

        for i, rec in enumerate(df_svc.to_dict("records")):
            if i >= 4:
                break
            tema = "vermelho" if rec["Base"] > Configuracoes.SLA_QUEBRA_MAXIMA else "cinza"
            with cols[i]:
                st.markdown(
                    ComponenteVisual.criar_card(
                        rec["Serviço"],
                        f"{rec['Base']:.2%}",
                        tema,
                        f"Atual: {rec['Atual']:.2%} | Vol: {rec['Vol (cons.)']:,.0f}"
                    ),
                    unsafe_allow_html=True
                )

        # gráfico com faixa
        df_svc = df_svc.sort_values("Base", ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=df_svc["Serviço"],
            x=df_svc["Base"],
            orientation="h",
            text=df_svc["Base"].map(lambda x: f"{x:.2%}"),
            textposition="outside",
            marker_color="#DC2626",
            error_x=dict(
                type="data",
                symmetric=False,
                array=(df_svc["Pessimista"] - df_svc["Base"]),
                arrayminus=(df_svc["Base"] - df_svc["Otimista"])
            ),
            hovertemplate=(
                "<b>%{y}</b><br>" +
                "Atual (NE/(E+NE)): %{customdata[0]:.2%}<br>" +
                "Fech. Otimista: %{customdata[1]:.2%}<br>" +
                "Fech. Base: %{x:.2%}<br>" +
                "Fech. Pessimista: %{customdata[2]:.2%}<br>" +
                "<extra></extra>"
            ),
            customdata=np.column_stack([df_svc["Atual"], df_svc["Otimista"], df_svc["Pessimista"]])
        ))
        try:
            linha_sla = float(Configuracoes.SLA_QUEBRA_MAXIMA)
        except Exception:
            linha_sla = None
        if linha_sla is not None:
            fig.add_vline(x=linha_sla, line_width=2, line_dash="dash", line_color="black")
        fig.update_layout(
            xaxis_tickformat=".0%",
            xaxis_title="Fechamento (Base) — com faixa Ot↔Pess",
            yaxis_title="",
            margin=dict(t=10, b=0, l=0, r=0),
            height=300
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ====================================================
    # Distribuição / Top Motivos / “Top Monitores” (atual)
    # ====================================================
    st.write("---")
    g1, g2, g3 = st.columns([1, 1.2, 1.2])

    with g1:
        st.markdown("#### 📉 Distribuição")
        df_pie = df.groupby("Status Contrato", as_index=False)["TOTAL DE TAREFAS"].sum()
        if not df_pie.empty:
            fig = px.pie(
                df_pie, names="Status Contrato", values="TOTAL DE TAREFAS", hole=0.5,
                color="Status Contrato",
                color_discrete_map={"Executada": "#16A34A", "Não Executada": "#DC2626", "Pendente": "#94A3B8"}
            )
            fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.2), margin=dict(t=10, b=10, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with g2:
        st.markdown("#### 🔎 Top Motivos (Não Executada)")
        if col_motivo and col_motivo in df.columns:
            df_motivos = (
                df[df["Status Contrato"] == "Não Executada"]
                .groupby(col_motivo, as_index=False)["TOTAL DE TAREFAS"].sum()
                .sort_values("TOTAL DE TAREFAS", ascending=False)
                .head(5)
            )
            if not df_motivos.empty:
                fig_m = px.bar(
                    df_motivos,
                    x="TOTAL DE TAREFAS", y=col_motivo,
                    orientation="h",
                    color_discrete_sequence=["#DC2626"],
                    text="TOTAL DE TAREFAS"
                )
                fig_m.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")
                st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})

    with g3:
        st.markdown("#### 👔 Top Monitores (Quebra Atual)")
        if "MONITOR" in df.columns:
            p_mon = pd.crosstab(df["MONITOR"], df["Status Contrato"], values=df["TOTAL DE TAREFAS"], aggfunc="sum").fillna(0)
            if "Não Executada" in p_mon.columns:
                if "Executada" not in p_mon.columns:
                    p_mon["Executada"] = 0.0
                p_mon["Considerado"] = p_mon["Executada"] + p_mon["Não Executada"]
                p_mon["% Quebra Atual"] = np.where(p_mon["Considerado"] > 0, p_mon["Não Executada"] / p_mon["Considerado"], 0.0)
                rank_mon = p_mon[p_mon["Considerado"] >= 5].sort_values("% Quebra Atual", ascending=False).head(5).reset_index()
                st.dataframe(
                    rank_mon[["MONITOR", "Não Executada", "% Quebra Atual"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={"% Quebra Atual": st.column_config.ProgressColumn("Taxa", format="%.2f", min_value=0, max_value=1)},
                )

    # ====================================================
    # Ranking por Responsável (SLA no Fechamento)
    # ====================================================
    st.write("---")
    st.markdown("### 🧭 Ranking por Responsável (SLA no Fechamento)")

    tab_mon, tab_tec = st.tabs(["👔 Monitor", "👤 Técnico"])

    def render_ranking(df_rank: pd.DataFrame, label_col: str):
        if df_rank.empty:
            st.info("Sem volume suficiente para ranking com os filtros atuais.")
            return

        df_rank = df_rank.head(int(top_n)).copy()

        st.dataframe(
            df_rank[[label_col, "Alocado", "Pendente", "Quebra Atual", "Fechamento Otimista", "Fechamento Base", "Fechamento Pessimista"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Quebra Atual": st.column_config.ProgressColumn("Quebra Atual", min_value=0, max_value=1, format="%.2f"),
                "Fechamento Otimista": st.column_config.ProgressColumn("Fech. Otimista", min_value=0, max_value=1, format="%.2f"),
                "Fechamento Base": st.column_config.ProgressColumn("Fech. Base", min_value=0, max_value=1, format="%.2f"),
                "Fechamento Pessimista": st.column_config.ProgressColumn("Fech. Pessimista", min_value=0, max_value=1, format="%.2f"),
            }
        )

        # gráfico (Base + faixa Ot↔Pess)
        df_plot = df_rank.sort_values("Fechamento Base", ascending=True)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=df_plot[label_col],
            x=df_plot["Fechamento Base"],
            orientation="h",
            marker_color="#7C3AED",
            text=df_plot["Fechamento Base"].map(lambda x: f"{x:.2%}"),
            textposition="outside",
            error_x=dict(
                type="data",
                symmetric=False,
                array=(df_plot["Fechamento Pessimista"] - df_plot["Fechamento Base"]),
                arrayminus=(df_plot["Fechamento Base"] - df_plot["Fechamento Otimista"])
            ),
        ))
        fig.add_vline(x=Configuracoes.SLA_QUEBRA_MAXIMA, line_width=2, line_dash="dash", line_color="black")
        fig.update_layout(
            margin=dict(t=10, b=0, l=0, r=0),
            xaxis_tickformat=".0%",
            xaxis_title="Fechamento (Base) — com faixa Ot↔Pess",
            yaxis_title="",
            height=450
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with tab_mon:
        if "MONITOR" in df.columns:
            rank = tabela_cenarios_por_grupo(df, "MONITOR", p_ot, p_base, p_pess, min_alocado=float(min_alocado_rank))
            render_ranking(rank, "MONITOR")
        else:
            st.warning("Coluna MONITOR não encontrada.")

    with tab_tec:
        if "TÉCNICO" in df.columns:
            rank = tabela_cenarios_por_grupo(df, "TÉCNICO", p_ot, p_base, p_pess, min_alocado=float(min_alocado_rank))
            render_ranking(rank, "TÉCNICO")
        else:
            st.warning("Coluna TÉCNICO não encontrada.")

    # ====================================================
    # TABELAS
    # ====================================================
    st.write("---")
    tab_acao, tab_base = st.tabs(["🚨 Fila de Tratamento (Backoffice)", "🧾 Base de Dados Completa"])

    with tab_acao:
        df_acao = df[df["Status Contrato"] == "Não Executada"].copy()
        if not df_acao.empty:
            cols_chaves = [c for c in ["CONTRATO", "TÉCNICO", "MONITOR", col_motivo, "TOTAL DE TAREFAS"] if c and c in df_acao.columns]
            st.dataframe(df_acao[cols_chaves] if cols_chaves else df_acao, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Baixar Fila (.CSV)",
                data=df_acao.to_csv(index=False, sep=";", encoding="utf-8-sig"),
                file_name="fila.csv",
                mime="text/csv",
            )
        else:
            st.success("Nenhuma quebra registrada!")

    with tab_base:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Baixar Base (.CSV)",
            data=df.to_csv(index=False, sep=";", encoding="utf-8-sig"),
            file_name="base.csv",
            mime="text/csv",
        )