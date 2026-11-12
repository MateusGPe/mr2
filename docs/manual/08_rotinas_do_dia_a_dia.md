# 8. Rotinas do Dia a Dia

Este capítulo consolida os fluxos práticos recomendados para a equipe do refeitório e a coordenação técnica executarem o sistema com tranquilidade em cada turno.

---

## 8.1. Checklist Pré-Abertura do Refeitório

Execute esta preparação antes de liberar a fila para os alunos:

1. **Sincronizar a base e as reservas do dia** (no [Painel Administrativo](03_painel_administrativo.md)):
   * Abra a aba **Importação**.
   * Se a planilha de estudantes teve matrículas novas ou trocas de turma no SUAP, importe o **CSV de Estudantes** ou clique em **Baixar do Google**.
   * Na seção de **Reservas**, carregue o CSV do dia ou baixe as reservas atualizadas da planilha Google para que **Almoço** e **Jantar** estejam no banco local.
2. **Conferir casos especiais**:
   * Na aba **Reservas**, valide que ninguém ficou sem reserva por falha de digitação; caso falte alguém autorizado, use **Nova Reserva**.
   * Na aba **Turmas**, confirme se novos alunos ingressantes estão vinculados às turmas corretas (para não serem bloqueados pela Grade de Horários no Totem).
3. **Abrir a sessão no equipamento de registro**:
   * No [Terminal do Operador](05_terminal_do_operador_registrar.md) ou pelo Menu de Controles do [Totem de Autoatendimento](06_totem_de_autoatendimento.md) (`F2` / `Ctrl+M` / botão direito ➔ *Trocar / Abrir Sessão...*), abra ou retome a sessão da refeição correspondente (**Almoço**, **Jantar** ou **Lanche**).
   * Para **Lanche**, preencha ou selecione o **Item servido** (ex.: `Achocolatado e Biscoito Maisena`).
   * Selecione o **Período** (ex.: `Integral`, `Matutino`) e marque todas as turmas/grupos autorizados (ou o grupo geral correspondente).

> [!IMPORTANT]
> Para sessões de **Almoço** ou **Jantar**, o sistema exige que exista pelo menos uma reserva ativa para a data e turno escolhidos no banco de dados antes de liberar a criação da sessão.

---

## 8.2. Operação Durante o Pico da Fila

### Cenário A: Operação com Totem de Autoatendimento + Fiscalização

1. Deixe o Totem em tela cheia (`F11`) com a câmera ativa ou leitor USB posicionado em um apoio firme.
2. Os alunos aproximam o crachá (ou digitam o prontuário no leitor/campo manual — o Totem redireciona automaticamente teclas alfanuméricas para a caixa de entrada caso o foco saia dela):
   * **Tela Verde + Bipe agudo**: passagem liberada.
   * **Tela Laranja/Vermelha + Bipe grave**: o aluno para ao lado sem travar a fila e a equipe verifica o motivo mostrado na mensagem (sem reserva, fora do horário da turma na grade, ou passagem duplicada).
3. Se uma turma foi liberada antecipadamente pela coordenação escolar (ex.: professor faltou e a turma saiu 15 minutos antes):
   * No Totem, pressione **`F2`** ou **`Ctrl+M`** (ou clique com o **botão direito** na área do vídeo ➔ *Filtrar Turmas da Sessão...*) e dê **Exceção** (ou liberação *SEM Reserva `#`*) apenas para aquela turma específica, **sem desligar a proteção para o resto da escola** — ou ative o **Modo Horário Livre** caso haja mudança geral de rotina no dia.

### Cenário B: Operação Assistida pelo Operador

1. Mantenha o cursor no campo **Busca / Prontuário**.
2. Passe o leitor de código de barras ou digite o **código numérico do prontuário** (não precisa digitar `IQ` ou `SP` no início) e tecle `Enter`:
   * Use `↓` e `↑` para alternar entre candidatos da lista, `Enter` para registrar o selecionado, `Shift+Enter` para forçar bypass de restrições (com critério do operador) ou `Esc` para limpar a busca.
   * Se a busca por nome retornar vários homônimos (ex.: vários `Lucas`), filtre adicionando a turma após vírgula ou ponto (ex.: `lucas, 1A`) ou clique duas vezes na linha certa antes de registrar.

---

## 8.3. Tratando Exceções Comuns na Hora

| Situação | O que fazer na hora | Onde ajustar |
| :--- | :--- | :--- |
| **Aluno esqueceu o crachá** | No Terminal do Operador, busque pelo **Nome** (ou peça para digitar os números do prontuário) e confirme após conferir documento ou turma. | [Terminal do Operador](05_terminal_do_operador_registrar.md) |
| **Aluno pegou refeição e houve erro / dupla leitura** | Clique no consumo na lista à direita do Terminal (e pressione `Delete`/`BackSpace` ou o botão cancelar) ou na aba **Consumos** do Totem. Informe **Operador** e **Motivo** no diálogo auditado. | [Diálogo de Cancelamento](05_terminal_do_operador_registrar.md#56-desfazer-um-registro-cancelamento-auditado) |
| **Aluno está na lista errada de reserva (ex.: Vegetarianos vs Tradicional)** | Edite a reserva no Painel Administrativo (aba **Reservas**, duplo clique) ou edite o registro na aba **Consumos** do Totem (`Duplo Clique`). | [Painel Admin](03_painel_administrativo.md) / [Totem](06_totem_de_autoatendimento.md) |
| **Turma autorizada na portaria não aparece ou está fora da grade** | Abra **Filtrar Turmas da Sessão...** (no Terminal ou via menu de contexto do Totem) e marque os grupos desejados ou ative **Horário Livre**. | [Totem](06_totem_de_autoatendimento.md) / [Terminal](05_terminal_do_operador_registrar.md) |
| **Aluno ingressante acabou de chegar sem QR Code** | Cadastre o aluno na aba **Alunos** do Painel, gere o crachá unitário filtrando por ele no **Gerador de Crachás**, ou lance usando `#` temporariamente no Terminal se necessário. | [Gerador de Crachás](07_gerador_de_crachas.md) |

---

## 8.4. Fechamento do Turno e Sincronização em Nuvem

Ao encerrar o atendimento da refeição:

1. **No Totem (`AppSelfService`)**:
   * Abra o menu (`F2`, `Ctrl+M` ou botão direito) ➔ **Consumos Registrados** para revisar rapidamente o total de atendimentos e verificar se existe algum lançamento `#` não identificado ou cancelamento pendente de justificativa.
   * No mesmo menu, clique em **Enviar Consumos (Google Sheets)** para forçar o envio imediato dos registros e cancelamentos caso a internet tenha oscilado durante o horário de pico.
   * Confirme na aba **Dashboard & Estatísticas** (e na aba **Consumos**) se o contador de pendentes zerou e se o histórico de sincronizações registra sucesso.
2. **No Terminal do Operador**:
   * Confira o contador de registrados no painel direito.
   * Quando aplicável, gere uma cópia da sessão em planilha pelo botão de exportação (**.xlsx** com abas *Resumo*, *Consumos* e *Reservas*, ou consolidação no Painel Administrativo).

> [!NOTE]
> Em refeições de **Lanche**, o envio para o Google Sheets pelo Totem dispara um envio em segundo plano da aba específica de lanches. Aguarde a barra de progresso no rodapé concluir antes de fechar o programa.

---

## 8.5. Rotina Semanal de Manutenção e Segurança

Uma vez por semana (por exemplo, toda sexta-feira após o último turno):

1. Abra o **Setup e Configurações** ➔ aba **Backups & Restauração**.
2. Crie um **Backup Manual** para gerar um arquivo compactado **`.zip`** datado na pasta `backups/` (contendo toda a pasta `config/`, exceto temporários `.tmp`, `.lock`, `-wal` e `-shm`) e copie o arquivo mais recente para um pendrive ou pasta institucional em nuvem.
3. Verifique se o limite de retenção de backups e o espaço em disco estão adequados e confira na aba **Checklist & Início** se a conexão com o Google Sheets continua válida.
4. Na aba **Dashboard** do Painel Administrativo, exporte o consolidado de consumos da semana caso a gestão escolar arquive relatórios locais em `.xlsx`.

---

* **Anterior:** [7. Gerador de Crachás](07_gerador_de_crachas.md)
* **Próximo:** [9. Atalhos de Teclado e Referência Rápida](09_atalhos_de_teclado_e_referencia_rapida.md)
