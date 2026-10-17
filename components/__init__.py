"""
components/__init__.py
======================
Pacote de componentes reutilizáveis do portal TOTALE.
"""

from components.base_operacional import (
    carregar_base_quebra,
    carregar_base_volumetria,
    carregar_lista_ativos,
    gerar_bases,
    ler_arquivo_bytes,
    ler_arquivo_caminho,
    localizar_base,
    normalizar_lista_ativos,
    preparar_base_quebra,
    preparar_base_volumetria,
    status_base,
)
from components.calendario import (
    InfoCalendario,
    carregar_feriados,
    contar_dias_uteis,
    dias_uteis_mes,
    eh_dia_util,
    fator_projecao,
    projetar_por_ritmo,
)
from components.criterios import (
    # Constantes de valores vazios
    VAZIOS_GERAIS,
    VAZIOS_CONTRATO,
    # Constantes de critérios
    TERMO_MIGRACAO_OS,
    TERMO_PME_HABILIDADE,
    VALOR_FLAG_GPON_SIM,
    TERMO_GPON_HABILIDADE,
    TERMOS_ND,
    TERMOS_PME,
    # Normalização
    normalizar_str,
    norm_col_nome,
    # Detecção de colunas
    detectar_cols_tipo,
    detectar_col_tipo_os_1,
    detectar_col_flag_gpon,
    detectar_col_capacidade,
    detectar_col_habilidade,
    detectar_col_status_atividade,
    detectar_col_contrato,
    # Criação de colunas
    criar_coluna_tipos_agrupados,
    criar_flag_gpon,
    # Classificação principal
    classificar_tipo_servico,
    # Métricas e painéis
    extrair_metricas_criterios,
    render_painel_criterios,
    # Componentes UI
    render_debug_criterios,
    render_card_destaque_migracao,
    render_lista_colunas,
)

from components.robo_local import (
    TotaleRoboEngine,
    executar_ciclo_headless,
    renderizar_robo_local,
    renderizar_sidebar_robo,
)

__all__ = [
    # Base operacional (robô)
    "carregar_base_quebra",
    "carregar_base_volumetria",
    "carregar_lista_ativos",
    "gerar_bases",
    "ler_arquivo_bytes",
    "ler_arquivo_caminho",
    "localizar_base",
    "normalizar_lista_ativos",
    "preparar_base_quebra",
    "preparar_base_volumetria",
    "status_base",
    # Robô local
    "TotaleRoboEngine",
    "executar_ciclo_headless",
    "renderizar_robo_local",
    "renderizar_sidebar_robo",
    # Calendário
    "InfoCalendario",
    "carregar_feriados",
    "contar_dias_uteis",
    "dias_uteis_mes",
    "eh_dia_util",
    "fator_projecao",
    "projetar_por_ritmo",
    # Constantes
    "VAZIOS_GERAIS", "VAZIOS_CONTRATO",
    "TERMO_MIGRACAO_OS", "VALOR_FLAG_GPON_SIM", "TERMO_GPON_HABILIDADE",
    "TERMO_PME_HABILIDADE", "TERMOS_ND", "TERMOS_PME",
    # Normalização
    "normalizar_str", "norm_col_nome",
    # Detecção
    "detectar_cols_tipo", "detectar_col_tipo_os_1",
    "detectar_col_flag_gpon", "detectar_col_capacidade",
    "detectar_col_habilidade", "detectar_col_status_atividade",
    "detectar_col_contrato",
    # Criação
    "criar_coluna_tipos_agrupados", "criar_flag_gpon",
    # Classificação
    "classificar_tipo_servico",
    # Métricas e UI
    "extrair_metricas_criterios", "render_painel_criterios",
    "render_debug_criterios", "render_card_destaque_migracao",
    "render_lista_colunas",
]
