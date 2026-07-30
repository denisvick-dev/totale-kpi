import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import io
from pathlib import Path

# ============ CONFIGURAÇÕES ============

# Cores da marca
COR_AZUL = "#012869"
COR_LARANJA = "#F37C04"
COR_CINZA = "#555555"
COR_CINZA_CLARO = "#F5F7FA"
COR_CINZA_MEDIO = "#E1E5EB"
COR_BRANCA = "#FFFFFF"
COR_TEXTO = "#2C3E50"

# Dimensões do template
TEMPLATE_WIDTH = 1327
TEMPLATE_HEIGHT = 284

# Diretório raiz do projeto (detecta automaticamente)
ARQUIVO_ATUAL = Path(__file__).resolve()
if ARQUIVO_ATUAL.parent.name == "pages":
    BASE_DIR = ARQUIVO_ATUAL.parent.parent
else:
    BASE_DIR = ARQUIVO_ATUAL.parent

# Diretórios do projeto
FONTS_DIR = BASE_DIR / "fonts"
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
IMAGES_DIR = ASSETS_DIR / "images"

# Caminhos dos arquivos
FONTE_REGULAR = FONTS_DIR / "Oscine-Regular.ttf"
FONTE_BOLD = FONTS_DIR / "Oscine-Bold.ttf"
ICONE_INSTAGRAM = ICONS_DIR / "instagram.png"
ICONE_LINKEDIN = ICONS_DIR / "linkedin.png"
TEMPLATE_BASE = IMAGES_DIR / "template-base.png"


# ============ STREAMLIT CONFIG ============

st.set_page_config(
    page_title="Gerador de Assinatura | Totale Tecnologia",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Corporativo Personalizado
st.markdown(f"""
    <style>
    /* Importar fonte profissional */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Reset e base */
    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    
    /* Esconder apenas o menu (mantém header para navegação) */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    
    /* Container principal */
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }}
    
    /* Header corporativo */
    .corporate-header {{
        background: linear-gradient(135deg, {COR_AZUL} 0%, #023a9c 100%);
        padding: 2rem 3rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(1, 40, 105, 0.15);
        color: white;
    }}
    
    .corporate-header h1 {{
        color: white !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
        letter-spacing: -0.5px;
    }}
    
    .corporate-header p {{
        color: rgba(255, 255, 255, 0.85) !important;
        font-size: 1rem !important;
        margin: 0.5rem 0 0 0 !important;
        font-weight: 400;
    }}
    
    .header-badge {{
        display: inline-block;
        background: {COR_LARANJA};
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 8px;
    }}
    
    /* Seções (na área principal) */
    .section-title {{
        color: {COR_AZUL};
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    
    .section-subtitle {{
        color: {COR_CINZA};
        font-size: 0.875rem;
        margin-bottom: 1.5rem;
    }}
    
    /* Inputs (apenas na área principal, NÃO na sidebar) */
    section.main .stTextInput > label {{
        color: {COR_TEXTO} !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
    }}
    
    section.main .stTextInput > div > div > input {{
        border-radius: 8px !important;
        border: 1.5px solid {COR_CINZA_MEDIO} !important;
        padding: 0.6rem 1rem !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
    }}
    
    section.main .stTextInput > div > div > input:focus {{
        border-color: {COR_LARANJA} !important;
        box-shadow: 0 0 0 3px rgba(243, 124, 4, 0.1) !important;
    }}
    
    /* Selectbox área principal */
    section.main .stSelectbox > label {{
        color: {COR_TEXTO} !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
    }}
    
    /* Botões */
    .stButton > button, .stDownloadButton > button {{
        background: linear-gradient(135deg, {COR_LARANJA} 0%, #e56d00 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.75rem 2rem !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        letter-spacing: 0.3px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(243, 124, 4, 0.25) !important;
    }}
    
    .stButton > button:hover, .stDownloadButton > button:hover {{
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 16px rgba(243, 124, 4, 0.35) !important;
    }}
    
    /* Alertas */
    .stAlert {{
        border-radius: 8px !important;
        border: none !important;
        padding: 1rem 1.25rem !important;
    }}
    
    /* Status Indicator */
    .status-item {{
        display: flex;
        align-items: center;
        padding: 0.5rem 0.75rem;
        margin: 0.25rem 0;
        background: white;
        border-radius: 6px;
        border-left: 3px solid;
        font-size: 0.875rem;
        color: {COR_TEXTO};
    }}
    
    .status-ok {{
        border-left-color: #10B981;
    }}
    
    .status-error {{
        border-left-color: #EF4444;
    }}
    
    /* Métricas de arquivo */
    .file-metrics {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin: 1rem 0;
    }}
    
    .metric-box {{
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid {COR_CINZA_MEDIO};
        text-align: center;
    }}
    
    .metric-label {{
        font-size: 0.75rem;
        color: {COR_CINZA};
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
        margin-bottom: 0.25rem;
    }}
    
    .metric-value {{
        font-size: 1.25rem;
        color: {COR_AZUL};
        font-weight: 700;
    }}
    
    /* Divider personalizado */
    .custom-divider {{
        height: 1px;
        background: linear-gradient(90deg, transparent, {COR_CINZA_MEDIO}, transparent);
        margin: 2rem 0;
        border: none;
    }}
    
    /* Footer */
    .corporate-footer {{
        margin-top: 3rem;
        padding: 1.5rem;
        background: {COR_CINZA_CLARO};
        border-radius: 8px;
        text-align: center;
        border-top: 3px solid {COR_LARANJA};
    }}
    
    .corporate-footer p {{
        margin: 0;
        color: {COR_CINZA};
        font-size: 0.875rem;
    }}
    
    .corporate-footer strong {{
        color: {COR_AZUL};
    }}
    
    /* ============ SIDEBAR - PRESERVAR NAVEGAÇÃO ============ */
    /* Garantir que os links de navegação sejam VISÍVEIS na sidebar */
    [data-testid="stSidebarNav"] {{
        background: transparent !important;
    }}
    
    [data-testid="stSidebarNav"] a {{
        color: white !important;
    }}
    
    [data-testid="stSidebarNav"] a span {{
        color: white !important;
        font-weight: 500 !important;
    }}
    
    [data-testid="stSidebarNav"] a:hover {{
        background: rgba(255, 255, 255, 0.15) !important;
    }}
    
    /* Títulos do meu conteúdo dentro da sidebar */
    [data-testid="stSidebar"] .element-container h2,
    [data-testid="stSidebar"] .element-container h3 {{
        color: white !important;
    }}
    
    /* Texto normal na sidebar em branco */
    [data-testid="stSidebar"] .element-container p,
    [data-testid="stSidebar"] .element-container label {{
        color: white !important;
    }}
    
    /* Expander na sidebar */
    [data-testid="stSidebar"] .streamlit-expanderHeader {{
        background: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border-radius: 6px !important;
    }}
    
    /* Sliders na sidebar - texto branco */
    [data-testid="stSidebar"] .stSlider label {{
        color: white !important;
    }}
    </style>
""", unsafe_allow_html=True)
# ============ HEADER CORPORATIVO ============

st.markdown(f"""
    <div class="corporate-header">
        <div class="header-badge">Ferramenta Interna</div>
        <h1>Gerador de Assinatura de E-mail</h1>
        <p>Crie sua assinatura profissional padronizada Totale Tecnologia</p>
    </div>
""", unsafe_allow_html=True)

# ============ FUNÇÕES AUXILIARES ============

def hex_to_rgb(hex_color):
    """Converte cor hexadecimal para RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def carregar_fonte(tamanho, negrito=False):
    """Carrega a fonte Oscine com fallback para fontes do sistema"""
    caminho_fonte = FONTE_BOLD if negrito else FONTE_REGULAR
    
    if caminho_fonte.exists():
        try:
            return ImageFont.truetype(str(caminho_fonte), tamanho)
        except (OSError, IOError) as e:
            st.warning(f"⚠️ Erro ao carregar fonte {caminho_fonte.name}: {e}")
    
    fontes_sistema = [
        "arialbd.ttf" if negrito else "arial.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if negrito else "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrito else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    
    for fonte in fontes_sistema:
        try:
            return ImageFont.truetype(fonte, tamanho)
        except (OSError, IOError):
            continue
    
    return ImageFont.load_default()


def verificar_recursos():
    """Verifica se todos os recursos necessários estão presentes"""
    status = {
        "Fonte Regular": FONTE_REGULAR.exists(),
        "Fonte Bold": FONTE_BOLD.exists(),
        "Ícone Instagram": ICONE_INSTAGRAM.exists(),
        "Ícone LinkedIn": ICONE_LINKEDIN.exists(),
        "Template Base": TEMPLATE_BASE.exists(),
    }
    return status


def gerar_assinatura(nome, cargo, telefone1, telefone2, config):
    """Sobrescreve texto na imagem template"""
    
    img = Image.open(TEMPLATE_BASE).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    laranja_rgb = hex_to_rgb(COR_LARANJA)
    azul_rgb = hex_to_rgb(COR_AZUL)
    
    fonte_nome = carregar_fonte(config["tamanho_nome"], negrito=True)
    fonte_cargo = carregar_fonte(config["tamanho_cargo"], negrito=False)
    fonte_telefone = carregar_fonte(config["tamanho_telefone"], negrito=True)
    
    if nome:
        draw.text(
            (config["x_nome"], config["y_nome"]),
            nome,
            fill=laranja_rgb,
            font=fonte_nome
        )
    
    if cargo:
        draw.text(
            (config["x_cargo"], config["y_cargo"]),
            cargo,
            fill=azul_rgb,
            font=fonte_cargo
        )
    
    telefones = telefone1 if telefone1 else ""
    if telefone2:
        telefones += f"  •  {telefone2}" if telefones else telefone2
    
    if telefones:
        draw.text(
            (config["x_telefone"], config["y_telefone"]),
            telefones,
            fill=azul_rgb,
            font=fonte_telefone
        )
    
    return img


# ============ SIDEBAR CORPORATIVA ============

with st.sidebar:
    st.markdown("## Painel de Controle")
    
    # Status dos recursos com visual melhorado
    st.markdown("### 📦 Status do Sistema")
    status = verificar_recursos()
    
    for recurso, ok in status.items():
        classe = "status-ok" if ok else "status-error"
        icone = "✓" if ok else "✗"
        st.markdown(
            f'<div class="status-item {classe}"><strong>{icone}</strong>&nbsp;&nbsp;{recurso}</div>',
            unsafe_allow_html=True
        )
    
    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)
    
    # Info do template
    st.markdown(f"""
        <div style="background: white; padding: 1rem; border-radius: 8px; border-left: 3px solid {COR_AZUL};">
            <div style="font-size: 0.75rem; color: {COR_CINZA}; text-transform: uppercase; font-weight: 600;">Template</div>
            <div style="font-size: 1rem; color: {COR_AZUL}; font-weight: 700; margin-top: 4px;">{TEMPLATE_WIDTH} × {TEMPLATE_HEIGHT} px</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)
    
    # Ajustes de posição
    st.markdown("### 🎯 Ajustes de Posicionamento")
    st.caption("Configure a posição dos elementos")
    
    with st.expander("👤 Nome", expanded=False):
        x_nome = st.slider("Posição Horizontal (X)", 0, TEMPLATE_WIDTH, 125, key="xn")
        y_nome = st.slider("Posição Vertical (Y)", 0, TEMPLATE_HEIGHT, 164, key="yn")
        tamanho_nome = st.slider("Tamanho da Fonte", 10, 80, 42, key="tn")
    
    with st.expander("💼 Cargo", expanded=False):
        x_cargo = st.slider("Posição Horizontal (X)", 0, TEMPLATE_WIDTH, 125, key="xc")
        y_cargo = st.slider("Posição Vertical (Y)", 0, TEMPLATE_HEIGHT, 211, key="yc")
        tamanho_cargo = st.slider("Tamanho da Fonte", 8, 60, 32, key="tc")
    
    with st.expander("📱 Telefones", expanded=False):
        x_telefone = st.slider("Posição Horizontal (X)", 0, TEMPLATE_WIDTH, 598, key="xt")
        y_telefone = st.slider("Posição Vertical (Y)", 0, TEMPLATE_HEIGHT, 209, key="yt")
        tamanho_telefone = st.slider("Tamanho da Fonte", 8, 60, 35, key="tt")
    
    st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)
    
    # Debug
    with st.expander("🔧 Configurações Avançadas"):
        st.caption("**Caminhos do Sistema**")
        st.code(f"Base: {BASE_DIR.name}", language="text")
        st.code(f"Fontes: fonts/", language="text")
        st.code(f"Assets: assets/", language="text")


# ============ VERIFICAÇÕES ============

if not TEMPLATE_BASE.exists():
    st.error("❌ **Template não encontrado**")
    st.warning(f"Adicione o arquivo template em: `{TEMPLATE_BASE}`")
    
    if IMAGES_DIR.exists():
        arquivos = list(IMAGES_DIR.iterdir())
        if arquivos:
            st.info("📁 Arquivos encontrados na pasta:")
            for arq in arquivos:
                st.write(f"- `{arq.name}`")
    st.stop()

if not FONTE_REGULAR.exists() or not FONTE_BOLD.exists():
    st.warning("⚠️ Fontes Oscine não encontradas. Usando fonte alternativa do sistema.")


# ============ CONTEÚDO PRINCIPAL ============

col1, col2 = st.columns([1, 2], gap="large")

# ===== COLUNA ESQUERDA: FORMULÁRIO =====
with col1:
    st.markdown('<div class="section-title">📝 Dados Pessoais</div>', unsafe_allow_html=True)
    st.markdown('<p class="section-subtitle">Preencha as informações que aparecerão na assinatura</p>', unsafe_allow_html=True)
    
    with st.container():
        nome = st.text_input(
            "Nome Completo",
            value="Denis Vick",
            placeholder="Digite seu nome completo"
        )
        
        cargo = st.text_input(
            "Cargo / Função",
            value="Analista de COP | Leste & ABCDM",
            placeholder="Ex: Analista, Gerente, Coordenador"
        )
        
        st.markdown("**Contatos Telefônicos**")
        
        telefone1 = st.text_input(
            "Telefone Principal",
            value="(11) 99304-5101",
            placeholder="(00) 00000-0000"
        )
        
        telefone2 = st.text_input(
            "Telefone Secundário",
            value="",
            placeholder="Opcional",
            help="Deixe em branco se não quiser incluir"
        )

# ===== COLUNA DIREITA: PRÉ-VISUALIZAÇÃO =====
with col2:
    st.markdown('<div class="section-title">👁️ Pré-visualização</div>', unsafe_allow_html=True)
    st.markdown('<p class="section-subtitle">Veja como sua assinatura ficará no e-mail</p>', unsafe_allow_html=True)
    
    try:
        config = {
            "x_nome": x_nome,
            "y_nome": y_nome,
            "tamanho_nome": tamanho_nome,
            "x_cargo": x_cargo,
            "y_cargo": y_cargo,
            "tamanho_cargo": tamanho_cargo,
            "x_telefone": x_telefone,
            "y_telefone": y_telefone,
            "tamanho_telefone": tamanho_telefone,
        }
        
        img_final = gerar_assinatura(nome, cargo, telefone1, telefone2, config)
        
        # Container de preview
        st.image(img_final, use_container_width=True)
        st.caption(f"📐 Resolução original: {img_final.width} × {img_final.height} pixels")
        
        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)
        
        # ============ SEÇÃO DE DOWNLOAD ============
        st.markdown('<div class="section-title">📥 Exportar Assinatura</div>', unsafe_allow_html=True)
        st.markdown('<p class="section-subtitle">Configure o tamanho e formato para download</p>', unsafe_allow_html=True)
        
        col_tam1, col_tam2 = st.columns(2)
        
        with col_tam1:
            tamanho_opcao = st.selectbox(
                "📏 Tamanho da Imagem",
                options=[
                    "E-mail Padrão (600px)",
                    "E-mail Compacto (500px)",
                    "E-mail Ampliado (700px)",
                    "Resolução Original (1327px)"
                ],
                index=0,
                help="600px é o tamanho recomendado para a maioria dos clientes de e-mail"
            )
        
        with col_tam2:
            formato_opcao = st.selectbox(
                "🎨 Formato do Arquivo",
                options=[
                    "PNG (alta qualidade)",
                    "JPG (arquivo menor)"
                ],
                index=0,
                help="PNG mantém melhor qualidade. JPG gera arquivo menor."
            )
        
        larguras = {
            "E-mail Padrão (600px)": 600,
            "E-mail Compacto (500px)": 500,
            "E-mail Ampliado (700px)": 700,
            "Resolução Original (1327px)": TEMPLATE_WIDTH
        }
        
        largura_final = larguras[tamanho_opcao]
        
        if largura_final != img_final.width:
            proporcao = largura_final / img_final.width
            altura_final = int(img_final.height * proporcao)
            img_download = img_final.resize(
                (largura_final, altura_final),
                Image.Resampling.LANCZOS
            )
        else:
            img_download = img_final
        
        buffer = io.BytesIO()
        
        if formato_opcao.startswith("PNG"):
            img_download.save(buffer, format="PNG", optimize=True)
            mime_type = "image/png"
            extensao = "png"
        else:
            img_jpg = img_download.convert("RGB")
            img_jpg.save(buffer, format="JPEG", quality=90, optimize=True)
            mime_type = "image/jpeg"
            extensao = "jpg"
        
        buffer.seek(0)
        tamanho_kb = len(buffer.getvalue()) / 1024
        
        # Métricas em cards
        st.markdown(f"""
            <div class="file-metrics">
                <div class="metric-box">
                    <div class="metric-label">Dimensões</div>
                    <div class="metric-value">{img_download.width}×{img_download.height}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Tamanho</div>
                    <div class="metric-value">{tamanho_kb:.1f} KB</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Formato</div>
                    <div class="metric-value">{extensao.upper()}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Botão de download
        st.download_button(
            label=f"⬇️  Baixar Assinatura em {extensao.upper()}",
            data=buffer,
            file_name=f"assinatura_totale_{nome.replace(' ', '_').lower() if nome else 'padrao'}.{extensao}",
            mime=mime_type,
            use_container_width=True,
            type="primary"
        )
        
        # Status do arquivo
        if tamanho_kb > 100:
            st.warning(f"⚠️ **Arquivo grande** ({tamanho_kb:.1f} KB). Recomendamos abaixo de 100 KB para melhor performance em e-mails.")
        else:
            st.success(f"✅ **Tamanho otimizado** para uso em assinatura de e-mail")
        
        # Instruções em tabs
        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📚 Guia de Instalação</div>', unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["📧 Gmail", "📧 Outlook Desktop", "📧 Outlook Web"])
        
        with tab1:
            st.markdown("""
            **Passo a passo para Gmail:**
            
            1. Abra o Gmail e clique no ícone de engrenagem ⚙️ no canto superior direito
            2. Selecione **"Ver todas as configurações"**
            3. Na aba **"Geral"**, role até a seção **"Assinatura"**
            4. Clique em **"Criar nova"** e defina um nome
            5. No editor, clique no ícone de imagem 🖼️
            6. Faça upload da imagem PNG/JPG baixada
            7. Configure a assinatura para "novas mensagens" e "respostas"
            8. Role até o final da página e clique em **"Salvar alterações"**
            """)
        
        with tab2:
            st.markdown("""
            **Passo a passo para Outlook Desktop:**
            
            1. Abra o Outlook e vá em **Arquivo → Opções**
            2. Selecione **E-mail** no menu lateral
            3. Clique no botão **"Assinaturas..."**
            4. Clique em **"Novo"** e dê um nome à assinatura
            5. No editor de assinatura, clique no ícone de imagem 🖼️
            6. Selecione o arquivo baixado
            7. Defina como padrão para **novas mensagens** e **respostas**
            8. Clique em **OK** para salvar
            """)
        
        with tab3:
            st.markdown("""
            **Passo a passo para Outlook Web (Office 365):**
            
            1. Clique no ícone de **Configurações ⚙️** no canto superior direito
            2. Selecione **"Ver todas as configurações do Outlook"**
            3. Navegue até **E-mail → Compor e responder**
            4. Na seção **"Assinatura de email"**, clique em **"Nova assinatura"**
            5. Insira a imagem através do ícone de imagem no editor
            6. Marque as opções para incluir automaticamente
            7. Clique em **"Salvar"**
            """)
    
    except FileNotFoundError as e:
        st.error(f"❌ Arquivo não encontrado: {e}")
    except Exception as e:
        st.error(f"❌ Erro ao processar: {e}")

# ============ FOOTER CORPORATIVO ============

st.markdown(f"""
    <div class="corporate-footer">
        <p><strong>Totale Tecnologia</strong> © 2026 · Conexão em Movimento</p>
        <p style="font-size: 0.75rem; margin-top: 0.5rem;">Ferramenta de uso interno · Versão 1.0</p>
    </div>
""", unsafe_allow_html=True)