# ----------------------------------------------------------------------------
# Arquivo: registro/nucleo/service_logic.py (Fachada de Serviços do Núcleo)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""
Fachada de serviços funcionais do núcleo de registro de refeições.
Re-exporta funções dos módulos especializados em `registro.nucleo.services`
para garantir 100% de compatibilidade retroativa com a API existente.
"""

from registro.nucleo import google_api_service, importers_service, models
from registro.nucleo.services.consumo_service import (
    atualizar_consumo,
    desfazer_consumo,
    desfazer_consumo_por_prontuario,
    registrar_consumo,
    registrar_consumo_com_reserva,
)
from registro.nucleo.services.estudante_service import (
    REGEX_LIMPEZA_PRONTUARIO,
    atualizar_estudante,
    criar_estudante,
    listar_estudantes,
    listar_estudantes_fuzzy,
    listar_todos_os_estudantes,
)
from registro.nucleo.services.export_service import (
    _escrever_consumos_em_planilha,
    exportar_estudantes_para_csv,
    exportar_reservas_para_csv,
    exportar_sessao_para_xlsx,
    exportar_todos_os_consumos_para_xlsx,
)
from registro.nucleo.services.reserva_service import (
    atualizar_cancelamento_reserva,
    atualizar_reserva,
    criar_reserva,
    deletar_reserva,
    listar_datas_reservas,
    listar_reservas,
    salvar_importacao_dados,
)
from registro.nucleo.services.sessao_service import (
    atualizar_grupos_sessao,
    atualizar_sessao,
    carregar_estado_sessao,
    deletar_sessao,
    iniciar_nova_sessao,
    limpar_estado_sessao,
    listar_todas_sessoes,
    listar_todos_os_grupos,
    obter_detalhes_sessao,
    obter_estudantes_para_sessao,
    salvar_estado_sessao,
)
from registro.nucleo.services.stats_service import (
    obter_estatisticas_dashboard,
    obter_estatisticas_sessao,
)
from registro.nucleo.services.sync_service import (
    _montar_linhas_para_sessao,
    sincronizar_do_google_sheets,
    sincronizar_para_google_sheets,
    sincronizar_todas_sessoes_para_google_sheets,
)

__all__ = [
    "REGEX_LIMPEZA_PRONTUARIO",
    "_escrever_consumos_em_planilha",
    "_montar_linhas_para_sessao",
    "atualizar_cancelamento_reserva",
    "atualizar_consumo",
    "atualizar_estudante",
    "atualizar_grupos_sessao",
    "atualizar_reserva",
    "atualizar_sessao",
    "carregar_estado_sessao",
    "criar_estudante",
    "criar_reserva",
    "deletar_reserva",
    "deletar_sessao",
    "desfazer_consumo",
    "desfazer_consumo_por_prontuario",
    "exportar_estudantes_para_csv",
    "exportar_reservas_para_csv",
    "exportar_sessao_para_xlsx",
    "exportar_todos_os_consumos_para_xlsx",
    "iniciar_nova_sessao",
    "limpar_estado_sessao",
    "listar_datas_reservas",
    "listar_estudantes",
    "listar_estudantes_fuzzy",
    "listar_reservas",
    "listar_todas_sessoes",
    "listar_todos_os_estudantes",
    "listar_todos_os_grupos",
    "obter_detalhes_sessao",
    "obter_estatisticas_dashboard",
    "obter_estatisticas_sessao",
    "obter_estudantes_para_sessao",
    "registrar_consumo",
    "registrar_consumo_com_reserva",
    "salvar_estado_sessao",
    "salvar_importacao_dados",
    "sincronizar_do_google_sheets",
    "sincronizar_para_google_sheets",
    "sincronizar_todas_sessoes_para_google_sheets",
]
