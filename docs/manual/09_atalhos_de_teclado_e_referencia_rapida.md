# 9. Atalhos de Teclado e Referência Rápida

Esta seção reúne em formato de consulta direta apenas os atalhos, gestos, curingas, comandos CLI e arquivos realmente implementados e verificados no sistema.

---

## 9.1. Atalhos e Ações do Terminal do Operador (`--reg`)

| Atalho / Gesto | Onde funciona | Ação |
| :--- | :--- | :--- |
| `Enter` | Campo de busca | Registra o estudante selecionado (ou primeiro elegível compatível). |
| `Shift+Enter` | Campo de busca | Registra ignorando bloqueios/travas (`forcar_bypass=True`), quando autorizado pelo operador. |
| `↓` / `↑` | Campo de busca | Move a seleção para baixo ou para cima na tabela de elegíveis sem tirar o cursor da busca. |
| `Esc` | Campo de busca | Limpa o texto digitado na busca imediatamente. |
| `Duplo Clique` | Tabela de elegíveis | Seleciona e registra o estudante clicado. |
| `Delete` / `BackSpace` | Tabela de registrados (painel direito) | Aciona o fluxo de desfazer/cancelar o consumo selecionado (com diálogo auditado). |
| `Clique no cabeçalho` | Qualquer tabela (`TreeviewSimples`) | Ordena a tabela crescente/decrescente com seta indicadora (`▲` / `▼`). |

---

## 9.2. Atalhos e Gestos do Totem de Autoatendimento (`--auto`)

| Atalho / Gesto | Contexto / PIN | Ação |
| :--- | :--- | :--- |
| `F2` ou `Ctrl+M` | Qualquer tela do Totem | Abre o **Menu de Contexto / Controles do Operador** (ações internas exigem PIN quando configurado). |
| **Botão direito** | Qualquer área da janela ou vídeo da câmera | Abre o **Menu de Contexto / Controles do Operador** na posição do cursor. |
| **Botão direito** | Tabela de **Consumos** | Abre o menu de contexto do registro selecionado (detalhes/edição/cancelamento). |
| **Clique** no subtítulo da refeição ativa | Tela principal de leitura (`Modo Totem`) | Abre a janela pública **Horários de Acesso por Turma** com fechamento automático em 15 segundos. |
| `F11` | Janela do Totem | Alterna o modo **Tela Cheia** (pode exigir PIN para ativar/alternar conforme política de segurança). |
| `Esc` | Janela principal / Diálogos | Sai do modo **Tela Cheia** (pode exigir PIN se `require_pin_to_exit` estiver ativo) ou fecha o diálogo **Horários das Turmas** / **PIN**. |
| `Digitação alfanumérica` | Tela principal de leitura (mesmo fora do foco) | Redireciona automaticamente as teclas para a caixa de entrada manual, evitando perda de leitura de scanners USB. |
| `Enter` | Caixa manual do Totem / Diálogo de **PIN** | Submete a matrícula digitada ou confirma o **PIN** informado (`Return` / `KP_Enter`). |
| `Duplo Clique` | Aba **Consumos** / Lista de candidatos manual | Abre os detalhes/edição do consumo ou confirma o candidato selecionado no lançamento manual. |
| `Delete` / `BackSpace` | Aba **Consumos** / Diálogo de **PIN** | Cancela/exclui o consumo selecionado (aba Consumos) ou apaga o último dígito no teclado de **PIN**. |
| `0`–`9` (teclado físico) | Diálogo de **PIN** | Insere dígitos no campo mascarado sem precisar tocar nos botões da tela. |

---

## 9.3. Interações Rápidas do Painel Administrativo (`--painel`)

| Gesto / Interação | Aba / Diálogo | Ação |
| :--- | :--- | :--- |
| `Duplo Clique` | Aba **Alunos**, aba **Reservas** ou diálogo **Vincular Aluno** | Abre diretamente o formulário de edição do item (ou conclui vinculação na turma). |
| Seleção em menus suspensos (`Combo`) | Todas as abas com filtros | Atualiza a filtragem instantaneamente sem precisar clicar em "Aplicar". |
| `Clique no cabeçalho` | Todas as tabelas (`TreeviewSimples`) | Ordena dinamicamente pela coluna clicada (`▲` / `▼`). |

---

## 9.4. Curingas e Marcadores Especiais de Busca

Utilizáveis na barra de pesquisa do **Terminal do Operador**, nas abas de busca do **Painel Administrativo** e nos filtros com busca integrada:

| Sintaxe | Onde usar | Comportamento |
| :--- | :--- | :--- |
| `todos`, `---`, `***`, `..` | Campo de busca do Terminal / Painel | Lista **todos os estudantes** disponíveis no contexto atual (ignorando filtro de texto). |
| `<nome>, <turma>` ou `<nome>. <turma>` | Busca de estudantes | Filtra simultaneamente pelo nome **e** pela turma usando separador por vírgula ou ponto (ex.: `ana, 1º ano`). |
| `<termo>.` (com ponto final) | Busca do Terminal | Restringe a correspondência usando tratamento de sufixo `.` para refinar grupo/prontuário exato. |
| `#` (cerquilha) | Terminal do Operador | Registro avulso / **Sem Reserva** para alunos ou visitantes autorizados fora da listagem nominal padrão, contabilizado separadamente como `#` nos relatórios e na sincronização. |
| Apenas dígitos (`301001`) | Leitor / Busca | O sistema normaliza automaticamente prefixos como `IQ`, `SP`, `IQXX` (`IQXX` ➔ `IQ30`) para comparar o código sem exigir digitação manual do prefixo completo. |

---

## 9.5. Comandos de Linha de Comando (CLI)

Execute a partir da raiz do projeto usando `uv run python -m registro`:

| Comando | Módulo Iniciado | Descrição |
| :--- | :--- | :--- |
| `uv run python -m registro` | **Menu Inicial** | Abre a janela lançadora com os 5 módulos. |
| `uv run python -m registro --reg` (ou `/reg`) | **Terminal do Operador** | Abre direto a tela de atendimento por fila/prontuário. |
| `uv run python -m registro --painel` (ou `/painel`) | **Painel Administrativo** | Abre direto a gestão de alunos, turmas, reservas, importação e dashboard. |
| `uv run python -m registro --auto` (ou `/auto`) | **Totem de Autoatendimento** | Abre direto o totem com câmera/QR, PIN e fila offline. |
| `uv run python -m registro --setup` (ou `/setup`) | **Setup e Configurações** | Abre a central de configurações, Google Cloud, PIN, grade horária e backups. |
| `uv run python -m registro --cards` (ou `/cards`) | **Gerador de Crachás** | Abre a ferramenta de criação de cartões QR em PDF/HTML. |
| `uv run python -m registro --help` | Ajuda CLI | Mostra a lista de opções suportadas no terminal. |
| `uv run python -m registro.cards` | **Gerador de Crachás** | Executa o gerador diretamente pelo submódulo dedicado. |

---

## 9.6. Badges de Status e Indicadores Visuais

| Badge / Cor | Local | Significado |
| :--- | :--- | :--- |
| **LIBERADO AGORA** (Verde) | Horários por Turma (Totem) | A janela horária desta turma/categoria está aberta neste minuto. |
| **EM BREVE** (Laranja) | Horários por Turma (Totem) | A janela ainda vai começar hoje (exibe contagem em minutos até o início). |
| **ENCERRADO** (Cinza) | Horários por Turma (Totem) | O horário dessa turma já terminou no turno de hoje. |
| **PENDENTE SYNC** (Laranja) | Consumos do Totem / Histórico | Registro salvo no SQLite aguardando envio com sucesso ao Google Sheets. |
| **`#` / Sem Reserva** | Terminal / Totem / Consumos | Atendimento realizado como exceção sem reserva prévia associada. |
| **Ativo / Inativo** | Alunos (Painel) | Estudantes inativos permanecem no histórico (para auditoria de consumos antigos), mas não aparecem para novas sessões nem reservas. |

---

## 9.7. Diretórios e Arquivos Gerados pelo Sistema

| Caminho | Conteúdo |
| :--- | :--- |
| `config/registro.db` | Banco de dados SQLite principal (`estudantes`, `grupos`, `sessoes`, `reservas`, `consumos`, `sync_logs`). |
| `config/settings.json` | Preferências de **áudio** (frequências e durações de bipe), **totem** (tela cheia, câmera ao iniciar, exigência de PIN, índice da câmera, tempo de feedback) e hash/salt do **PIN** PBKDF2-HMAC-SHA256. |
| `config/session.json` | Estado persistido da sessão em andamento (`id_sessao`, `excecao_grupos`, `ignorar_horario_grade`). |
| `config/grade_horarios.json` | Escalonamento semanal por dia (`segunda`..`domingo`) e refeição (`almoco`, `jantar`, `lanche`) com faixas `inicio`/`fim`, `turmas` e `categorias`. |
| `config/lanches.json` | Lista predefinida de itens exibidos na caixa combinada quando a sessão for **Lanche**. |
| `config/presets_turmas.json` | Predefinições de grupos de turmas no diálogo de sessão. |
| `config/turmas_integrado.json` | Lista das turmas usadas pelo botão rápido **Integrado** nos filtros. |
| `config/mapeamento_colunas.json` | Dicionário personalizável de sinônimos de cabeçalhos de planilhas importadas. |
| `config/spreadsheet.json` | ID da planilha do Google Sheets salva pelo Setup. |
| `config/credentials.json` | Credenciais OAuth 2.0 ou Service Account baixadas do Google Cloud. |
| `config/token.json` | Token de autorização OAuth gerado automaticamente após o login do navegador. |
| `backups/` | Arquivos **`.zip`** datados criados pelo gerenciador de backups contendo a pasta `config/` (sem arquivos `.tmp`, `.lock`, `-wal` ou `-shm`). |
| `logs/` | Logs rotativos (`5 MB` por arquivo, até `5` backups por módulo) úteis para suporte e diagnóstico. |

---

* **Anterior:** [8. Rotinas do Dia a Dia](08_rotinas_do_dia_a_dia.md)
* **Próximo:** [10. Solução de Problemas e FAQ](10_solucao_de_problemas_e_faq.md)
