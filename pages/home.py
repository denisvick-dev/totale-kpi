import streamlit as st
import time
import pytz
from zoneinfo import ZoneInfo
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# =====================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================
st.set_page_config(page_title="Portal TOTALE", page_icon="📊", layout="wide")

# =====================================
# CONFIGURAÇÕES INSTITUCIONAIS
# =====================================

VERSAO_SISTEMA = "2.1.0"
AMBIENTE = "Produção"  # Pode mudar para "Homologação" ou "Teste"

# =====================================
# ESTILO GLOBAL - POWER BI STYLE
# =====================================
st.markdown("""
<style>

/* Fundo geral */
.main {
    background-color: #F3F2F1;
}

/* Remove padding exagerado */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}

/* Barra superior */
.top-bar {
    background-color: #012869;
    padding: 18px 30px;
    border-radius: 8px;
    color: white;
    margin-bottom: 25px;
}

/* Cards padrão */
.card {
    background-color: white;
    padding: 25px;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid #E0E0E0;
}

/* Status */
.status-ok {
    background-color: #E6F4EA;
    border-left: 6px solid #2E7D32;
}

.status-warning {
    background-color: #FFF4E5;
    border-left: 6px solid #F37C04;
}

/* Títulos */
h1, h2, h3 {
    font-weight: 600;
}

</style>
""", unsafe_allow_html=True)

# =====================================
# HEADER SUPERIOR
# =====================================
st.markdown("""
<div class="top-bar">
    <h2 style="margin:0;">📊 Portal TOTALE</h2>
    <span>Painéis de Produção, Indicadores e Gestão Estratégica</span>
</div>
""", unsafe_allow_html=True)

# =====================================
# INTRODUÇÃO
# =====================================
st.markdown("""
<div class="card">
<b>Bem-vindo ao ambiente centralizado de dados da TOTALE.</b><br><br>
Este portal fornece uma visão clara e estratégica dos processos produtivos e indicadores
de performance, apoiando decisões com base em dados confiáveis.
</div>
""", unsafe_allow_html=True)

st.write("")

# =====================================
# STATUS DO SISTEMA
# =====================================
dados_carregados = "dados_prod" in st.session_state and st.session_state["dados_prod"] is not None

if not dados_carregados:
    st.markdown("""
    <div class="card status-warning">
        <b>⚠ Sistema aguardando atualização de dados</b><br><br>
        1️⃣ Acesse <b>🔁 Atualização de Dados</b> no menu lateral<br>
        2️⃣ Clique em <b>Atualizar Agora</b><br>
        3️⃣ Aguarde a conclusão
    </div>
    """, unsafe_allow_html=True)
else:
    ultima_atualizacao = st.session_state.get("ultima_atualizacao")
    hora_formatada = ultima_atualizacao.strftime("%d/%m/%Y às %H:%M:%S") if ultima_atualizacao else "Recente"

    st.markdown(f"""
    <div class="card status-ok">
        ✅ <b>Sistema atualizado e pronto para uso</b><br>
        Última sincronização: {hora_formatada}
    </div>
    """, unsafe_allow_html=True)

st.write("")

# =====================================
# CARDS DE NAVEGAÇÃO
# =====================================
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="card">
        <h4>⚙️ Produção</h4>
        Monitore eficiência operacional, volume produzido e desempenho por setor.
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="card">
        <h4>📈 Indicadores Estratégicos</h4>
        Acompanhe metas, resultados financeiros e KPIs críticos do negócio.
    </div>
    """, unsafe_allow_html=True)

st.write("")
st.divider()

# =====================================
# CARROSSEL
# =====================================
st.subheader("📢 Comunicados Internos")

imgs_carrossel = [
    "assets/images/informe_vagas.jpeg",
    "assets/images/consultivo_copa.jpg",
    "assets/images/indicacao_totale.png"
]

if "slide_index" not in st.session_state:
    st.session_state.slide_index = 0

if len(imgs_carrossel) > 0:

    col1, col2, col3 = st.columns([1,2,1])

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        slide_atual = imgs_carrossel[st.session_state.slide_index]
        st.image(slide_atual, use_container_width=True)

        st.markdown(
            f"<div style='text-align:center; font-size:14px; color:#666;'>Slide {st.session_state.slide_index + 1} de {len(imgs_carrossel)}</div>",
            unsafe_allow_html=True
        )

        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("⬅ Anterior", use_container_width=True):
                st.session_state.slide_index = (st.session_state.slide_index - 1) % len(imgs_carrossel)

        with col_btn2:
            if st.button("Próximo ➡", use_container_width=True):
                st.session_state.slide_index = (st.session_state.slide_index + 1) % len(imgs_carrossel)

        st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("Nenhum comunicado disponível no momento.")
    
# =====================================
# AUTO REFRESH INTELIGENTE
# =====================================
st_autorefresh(interval=1000, key="footer_refresh")

# =====================================
# HORÁRIO OFICIAL DE BRASÍLIA
# =====================================
tz_brasilia = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(tz_brasilia)
data_atual = agora.strftime("%d/%m/%Y")
hora_atual = agora.strftime("%H:%M:%S")

# =====================================
# RODAPÉ CENTRALIZADO PREMIUM
# =====================================
footer_html = f"""
<style>
.footer {{
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #012869;
    color: white;
    padding: 12px 20px;
    font-size: 14px;
    text-align: center;
    z-index: 999;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.2);
    font-weight: 500;
}}

.footer span {{
    margin: 0 8px;
}}

.block-container {{
    padding-bottom: 4.5rem;
}}
</style>

<div class="footer">
    🏢 <b>Portal TOTALE</b>
    <span>|</span>
    🌐 {AMBIENTE}
    <span>|</span>
    🕒 {data_atual} • {hora_atual} BRT
    <span>|</span>
    🔖 v{VERSAO_SISTEMA}
</div>
"""

st.markdown(footer_html, unsafe_allow_html=True)