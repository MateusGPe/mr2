# --- Arquivo: registro/nucleo/service_logic.py ---

"""
Módulo de serviço funcional que encapsula toda a lógica de negócio
da aplicação de registro de refeições.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import xlsxwriter

from registro.nucleo import google_api_service, importers_service, models
from registro.nucleo.exceptions import (
    ErroAPIGoogle,
    ErroImportacaoDados,
    ErroNucleoRegistro,
    ErroSessao,
)
from registro.nucleo.repository import (
    RepositorioConsumo,
    RepositorioEstudante,
    RepositorioGrupo,
    RepositorioReserva,
    RepositorioSessao,
)
from registro.nucleo.utils import DADOS_SESSAO, obter_caminho_documentos, para_codigo, salvar_csv


def iniciar_nova_sessao(
    repo_sessao: RepositorioSessao,
    repo_grupo: RepositorioGrupo,
    dados_sessao: DADOS_SESSAO,
) -> int:
    """Inicia uma nova sessão de refeição e a associa aos grupos selecionados."""
    refeicao = dados_sessao["refeicao"].lower()

    payload_sessao = {
        "refeicao": refeicao,
        "periodo": dados_sessao["periodo"],
        "data": dados_sessao["data"],
        "hora": dados_sessao["hora"],
        "item_servido": dados_sessao.get("item_servido"),
    }

    # Cria a sessão no banco de dados
    nova_sessao_db = repo_sessao.criar(payload_sessao)

    # Associa os grupos à sessão, se houver
    if dados_sessao["grupos"]:
        grupos_db = repo_grupo.por_nomes(set(dados_sessao["grupos"]))
        nova_sessao_db.grupos.extend(grupos_db)

    repo_sessao.obter_sessao().commit()
    return nova_sessao_db.id


def listar_todas_sessoes(repo_sessao: RepositorioSessao) -> List[Dict]:
    """Retorna uma lista simplificada de todas as sessões existentes."""
    sessoes = repo_sessao.ler_todos()
    return [
        {
            "id": s.id,
            "refeicao": s.refeicao,
            "periodo": s.periodo,
            "data": s.data,
            "hora": s.hora,
            "item_servido": s.item_servido,
            "grupos": [g.nome for g in s.grupos],
        }
        for s in sessoes
    ]


def obter_detalhes_sessao(
    repo_sessao: RepositorioSessao, id_sessao: int
) -> models.Sessao:
    """Retorna o objeto de uma sessão específica a partir do seu ID."""
    sessao = repo_sessao.ler_um(id_sessao)
    if not sessao:
        raise ErroSessao(f"Sessão com ID {id_sessao} não encontrada.")
    return sessao


def obter_estudantes_para_sessao(
    repo_sessao: RepositorioSessao,
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
    consumido: Optional[bool] = None,
) -> List[Dict]:
    """Busca estudantes elegíveis para a sessão, com base nas regras de negócio."""
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    ids_grupos_sessao = {g.id for g in sessao.grupos}

    # 1. Obter todos os consumos já registrados para esta sessão
    consumos_sessao = repo_consumo.ler_filtrado(sessao_id=id_sessao)
    mapa_consumos_por_estudante = {c.estudante_id: c for c in consumos_sessao}

    # 2. Otimizar busca de estudantes com base no filtro 'consumido'
    if consumido is True:
        ids_estudantes_para_buscar = set(mapa_consumos_por_estudante.keys())
        estudantes = repo_estudante.por_ids(ids_estudantes_para_buscar)
    else:  # Se consumido for False ou None, busca todos os ativos
        estudantes = repo_estudante.ler_filtrado(ativo=True)

    # 3. Otimizar busca de reservas, pegando todas para a data da sessão de uma só vez
    mapa_reservas_dia = {
        r.estudante_id: r
        for r in repo_reserva.ler_filtrado(data=sessao.data, cancelada=False)
    }
    
    # 4. Construir a lista final de estudantes elegíveis, aplicando as regras
    detalhes_estudantes = []
    for est in estudantes:
        autorizado = False
        motivo = "Acesso Negado"
        prato = "Sem Reserva"

        if sessao.refeicao == "almoço":
            reserva = mapa_reservas_dia.get(est.id)
            if reserva:
                autorizado = True
                motivo = "Reserva"
                prato = reserva.prato
            else: # Verifica exceção por grupo
                ids_grupos_estudante = {g.id for g in est.grupos}
                if ids_grupos_sessao.intersection(ids_grupos_estudante):
                    autorizado = True
                    motivo = "Exceção (Grupo)"
        else:  # Lanche
            ids_grupos_estudante = {g.id for g in est.grupos}
            if ids_grupos_sessao.intersection(ids_grupos_estudante):
                autorizado = True
                motivo = "Autorizado (Grupo)"
                prato = sessao.item_servido or "Lanche"

        if not autorizado:
            continue

        info_consumo = mapa_consumos_por_estudante.get(est.id)

        # Aplicar filtro final de consumo
        if consumido is True and not info_consumo:
            continue
        if consumido is False and info_consumo:
            continue

        detalhes_estudantes.append(
            {
                "pront": est.prontuario,
                "nome": est.nome,
                "turma": est.grupos[0].nome if est.grupos else "N/A",
                "prato": prato,
                "consumido": bool(info_consumo),
                "id_consumo": info_consumo.id if info_consumo else None,
                "hora_registro": info_consumo.hora_consumo if info_consumo else "",
                "status": motivo,
                **para_codigo(est.prontuario),
            }
        )

    return sorted(detalhes_estudantes, key=lambda x: x["nome"])


def deletar_sessao(repo_sessao: RepositorioSessao, id_sessao: int):
    """Deleta uma sessão e seus consumos associados (via cascade do DB)."""
    if not repo_sessao.deletar(id_sessao):
        raise ErroSessao(f"Sessão com ID {id_sessao} não encontrada para exclusão.")
    repo_sessao.obter_sessao().commit()


def atualizar_sessao(repo_sessao: RepositorioSessao, id_sessao: int, dados: Dict[str, Any]):
    """Atualiza os dados de uma sessão existente."""
    # 'grupos' são tratados em um método separado para clareza
    dados.pop('grupos', None)

    sessao_atualizada = repo_sessao.atualizar(id_sessao, dados)
    if not sessao_atualizada:
        raise ErroSessao(f"Sessão com ID {id_sessao} não encontrada para atualização.")

    repo_sessao.obter_sessao().commit()
    return sessao_atualizada


def registrar_consumo(
    repo_sessao: RepositorioSessao,
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
    prontuario: str,
) -> Dict[str, Any]:
    """Aplica a lógica de autorização e, se bem-sucedido, registra o consumo."""
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    estudantes = repo_estudante.ler_filtrado(prontuario=prontuario)
    if not estudantes:
        return {"autorizado": False, "motivo": "Estudante não encontrado."}
    estudante = estudantes[0]

    # Verificar se já consumiu na mesma sessão
    consumo_existente = repo_consumo.ler_filtrado(
        estudante_id=estudante.id, sessao_id=id_sessao
    )
    if consumo_existente:
        return {"autorizado": False, "motivo": "Consumo já registrado."}

    # Lógica de autorização
    id_reserva = None
    autorizado = False
    motivo = "Acesso Negado"

    if sessao.refeicao == "almoço":
        reservas = repo_reserva.ler_filtrado(
            estudante_id=estudante.id, data=sessao.data, cancelada=False
        )
        if reservas:
            autorizado = True
            id_reserva = reservas[0].id
            motivo = "Autorizado com reserva."
        else:
            ids_grupos_sessao = {g.id for g in sessao.grupos}
            ids_grupos_estudante = {g.id for g in estudante.grupos}
            if ids_grupos_sessao.intersection(ids_grupos_estudante):
                autorizado = True
                motivo = "Autorizado por exceção (grupo)."
    else:  # Lanche
        ids_grupos_sessao = {g.id for g in sessao.grupos}
        ids_grupos_estudante = {g.id for g in estudante.grupos}
        if ids_grupos_sessao.intersection(ids_grupos_estudante):
            autorizado = True
            motivo = "Autorizado para lanche (grupo)."

    if autorizado:
        payload = {
            "estudante_id": estudante.id,
            "sessao_id": sessao.id,
            "hora_consumo": datetime.now().strftime("%H:%M:%S"),
            "reserva_id": id_reserva,
        }
        repo_consumo.criar(payload)
        repo_consumo.obter_sessao().commit()

    return {"autorizado": autorizado, "motivo": motivo, "aluno": estudante.nome}


def desfazer_consumo(repo_consumo: RepositorioConsumo, id_consumo: int):
    """Remove um registro de consumo do banco de dados."""
    if repo_consumo.deletar(id_consumo):
        repo_consumo.obter_sessao().commit()


def atualizar_cancelamento_reserva(repo_reserva: RepositorioReserva, id_reserva: int, cancelar: bool = True):
    """Marca ou desmarca uma reserva como cancelada."""
    atualizado = repo_reserva.atualizar(id_reserva, {"cancelada": cancelar})
    if not atualizado:
        raise ErroNucleoRegistro(f"Reserva com ID {id_reserva} não encontrada.")
    repo_reserva.obter_sessao().commit()


def atualizar_grupos_sessao(
    repo_sessao: RepositorioSessao,
    repo_grupo: RepositorioGrupo,
    id_sessao: int,
    nomes_grupos: List[str],
):
    """Atualiza a lista de grupos autorizados para uma sessão."""
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    grupos_db = repo_grupo.por_nomes(set(nomes_grupos))
    sessao.grupos = grupos_db
    repo_sessao.obter_sessao().commit()


def exportar_sessao_para_xlsx(
    repo_sessao: RepositorioSessao, repo_consumo: RepositorioConsumo, id_sessao: int
) -> str:
    """Exporta os dados de consumo da sessão para um arquivo XLSX."""
    sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
    consumos = repo_consumo.ler_filtrado(sessao_id=id_sessao)

    nome_arquivo = ".".join(
        (
            sessao.refeicao.capitalize(),
            sessao.data.replace("/", "-"),
            sessao.hora.replace(":", "."),
            "xlsx",
        )
    )
    caminho_arquivo = obter_caminho_documentos() / nome_arquivo

    with xlsxwriter.Workbook(str(caminho_arquivo)) as workbook:
        worksheet = workbook.add_worksheet(nome_arquivo)
        cabecalho = ["Matrícula", "Data", "Nome", "Turma", "Refeição", "Hora"]
        worksheet.write_row(0, 0, cabecalho)
        for i, consumo in enumerate(consumos):
            prato = "Sem Reserva (Exceção)"
            if consumo.reserva_id and consumo.reserva:
                prato = consumo.reserva.prato
            elif sessao.refeicao == "lanche":
                prato = sessao.item_servido or "Lanche"

            turma = (
                consumo.estudante.grupos[0].nome if consumo.estudante.grupos else "N/A"
            )

            dados_linha = [
                consumo.estudante.prontuario,
                sessao.data,
                consumo.estudante.nome,
                turma,
                prato,
                consumo.hora_consumo,
            ]
            worksheet.write_row(i + 1, 0, dados_linha)
    return str(caminho_arquivo)


def sincronizar_do_google_sheets(
    repo_estudante: RepositorioEstudante,
    repo_reserva: RepositorioReserva,
    repo_grupo: RepositorioGrupo,
):
    """Sincroniza estudantes e reservas a partir de uma planilha do Google Sheets."""
    try:
        caminho_config = Path("./config")
        caminho_config.mkdir(exist_ok=True)
        planilha = google_api_service.obter_planilha()

        # Importa discentes (estudantes)
        discentes = google_api_service.buscar_valores_aba(planilha, "Discentes")
        if discentes:
            caminho_csv = caminho_config / "students.csv"
            if salvar_csv(discentes, caminho_csv):
                importers_service.importar_estudantes_csv(repo_estudante, repo_grupo, caminho_csv)

        # Importa reservas
        reservas = google_api_service.buscar_valores_aba(planilha, "DB")
        if reservas:
            caminho_csv = caminho_config / "reserves.csv"
            if salvar_csv(reservas, caminho_csv):
                importers_service.importar_reservas_csv(
                    repo_estudante, repo_reserva, caminho_csv
                )

    except (ErroAPIGoogle, ErroImportacaoDados) as e:
        repo_estudante.obter_sessao().rollback()
        raise e
    except Exception as e:
        repo_estudante.obter_sessao().rollback()
        raise ErroNucleoRegistro(f"Erro inesperado na sincronização: {e}") from e


def sincronizar_para_google_sheets(
    repo_sessao: RepositorioSessao,
    repo_consumo: RepositorioConsumo,
    id_sessao: int,
):
    """Envia os registros de consumo da sessão para a planilha do Google Sheets."""
    try:
        sessao = obter_detalhes_sessao(repo_sessao, id_sessao)
        consumos = repo_consumo.ler_filtrado(sessao_id=id_sessao)

        linhas_para_adicionar = []
        for consumo in consumos:
            prato = "Sem Reserva (Exceção)"
            if consumo.reserva_id and consumo.reserva:
                prato = consumo.reserva.prato
            elif sessao.refeicao == "lanche":
                prato = sessao.item_servido or "Lanche"

            turma = (
                consumo.estudante.grupos[0].nome if consumo.estudante.grupos else "N/A"
            )

            linhas_para_adicionar.append(
                [
                    consumo.estudante.prontuario,
                    sessao.data,
                    consumo.estudante.nome,
                    turma,
                    prato,
                    consumo.hora_consumo,
                ]
            )

        if linhas_para_adicionar:
            planilha = google_api_service.obter_planilha()
            google_api_service.anexar_linhas_unicas(
                planilha, linhas_para_adicionar, sessao.refeicao.capitalize()
            )
    except (ErroAPIGoogle, ErroSessao) as e:
        raise e
    except Exception as e:
        raise ErroNucleoRegistro(f"Erro inesperado no upload para a planilha: {e}") from e