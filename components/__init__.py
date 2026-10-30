"""
components/__init__.py
======================
Pacote de componentes reutilizáveis do portal TOTALE.
"""

from components.base_operacional import (
    carregar_hierarquia,
    carregar_lista_ativos,
    gerar_bases_upload,
    hierarquia_de,
    ler_arquivo_bytes,
    normalizar_erro_worksheet,
    normalizar_lista_ativos,
    preparar_base_rota_inicial,
    resolver_sheet_id,
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
    TERMO_GPON_HABILIDADE,
    # Constantes de critérios
    TERMO_MIGRACAO_OS,
    TERMO_PME_HABILIDADE,
    TERMOS_ND,
    TERMOS_PME,
    VALOR_FLAG_GPON_SIM,
    VAZIOS_CONTRATO,
    # Constantes de valores vazios
    VAZIOS_GERAIS,
    # Classificação principal
    classificar_tipo_servico,
    # Criação de colunas
    criar_coluna_tipos_agrupados,
    criar_flag_gpon,
    detectar_col_capacidade,
    detectar_col_contrato,
    detectar_col_flag_gpon,
    detectar_col_habilidade,
    detectar_col_status_atividade,
    detectar_col_tipo_os_1,
    # Detecção de colunas
    detectar_cols_tipo,
    # Métricas e painéis
    norm_col_nome,
    # Normalização
    normalizar_str,
    # Componentes UI
)
from components.upload_base import (
    limpar_bases_operacionais,
    metadados_upload,
    processar_e_publicar,
    render_status_upload,
    render_upload_base_operacional,
)

__all__ = [
    # Aderência à projeção (Produtividade)
    "calcular_aderencia",
    "classificar_aderencia",
    # Base operacional (leitura e tratamento)
    "carregar_hierarquia",
    "carregar_lista_ativos",
    "gerar_bases_upload",
    "hierarquia_de",
    "ler_arquivo_bytes",
    "normalizar_erro_worksheet",
    "normalizar_lista_ativos",
    "preparar_base_rota_inicial",
    "resolver_sheet_id",
    # Upload manual compartilhado
    "limpar_bases_operacionais",
    "metadados_upload",
    "processar_e_publicar",
    "render_status_upload",
    "render_upload_base_operacional",
    # Calendário
    "InfoCalendario",
    "carregar_feriados",
    "contar_dias_uteis",
    "dias_uteis_mes",
    "eh_dia_util",
    "fator_projecao",
    "projetar_por_ritmo",
    # Constantes
    "VAZIOS_GERAIS",
    "VAZIOS_CONTRATO",
    "TERMO_MIGRACAO_OS",
    "VALOR_FLAG_GPON_SIM",
    "TERMO_GPON_HABILIDADE",
    "TERMO_PME_HABILIDADE",
    "TERMOS_ND",
    "TERMOS_PME",
    # Normalização
    "normalizar_str",
    "norm_col_nome",
    # Detecção
    "detectar_cols_tipo",
    "detectar_col_tipo_os_1",
    "detectar_col_flag_gpon",
    "detectar_col_capacidade",
    "detectar_col_habilidade",
    "detectar_col_status_atividade",
    "detectar_col_contrato",
    # Criação
    "criar_coluna_tipos_agrupados",
    "criar_flag_gpon",
    # Classificação
    "classificar_tipo_servico",
    # Métricas e UI
]
