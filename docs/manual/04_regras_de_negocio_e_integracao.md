# Capítulo 4 — Regras de Negócio, Fluxo de Autorização e Formatos de Integração

Este capítulo explica **exatamente como o sistema decide** se um estudante pode ou não receber a refeição, como funcionam cotas, grade horária, categorias, estornos, sincronização com Google Sheets e quais formatos de planilhas e JSONs são aceitos.

[⬅️ Capítulo 3 — Painel Administrativo](./03_painel_administrativo.md) | [📑 Índice](../MANUAL_DO_USUARIO.md) | [Capítulo 5 — Terminal do Operador ➡️](./05_terminal_do_operador_registrar.md)

---

## 4.1 Pipeline Completo de Autorização (`registrar_consumo`)

Sempre que um QR Code é lido no Totem, um código USB é bipado ou o operador confirma um registro no Terminal, o núcleo executa a seguinte sequência estrita de verificações:

1. **Identificação do Estudante:** Busca o prontuário exato (removendo espaços e padronizando maiúsculas). Se o usuário digitou nome ou matrícula abreviada sem `IQ30...`, a interface resolve o prontuário via regras específicas antes de acionar o núcleo.
   * *Se não existir no banco:* retorna **`Estudante não encontrado.`**
2. **Verificação de Status Ativo:** Confirma se `estudante.ativo == True`.
   * *Se estiver inativo:* **bloqueia mesmo com Bypass ou Horário Livre** — retorna **`Estudante inativo.`**
3. **Duplicidade na Mesma Sessão:** Verifica se já há consumo ativo desse estudante na `sessao_id` atual.
   * *Se já houver:* **bloqueia mesmo com Bypass** — retorna **`Consumo já registrado.`**
4. **Cota Diária por Refeição e Período (Inviolável):**
   * Para **`almoço`** ou **`jantar`**: bloqueia se já existir qualquer consumo ativo do mesmo estudante **naquela mesma data e tipo de refeição** (mesmo em outra sessão do dia). Retorna **`Consumo de <refeição> já registrado nesta data (Cota diária atingida).`**
   * Para **`lanche`**: bloqueia se já existir consumo ativo de lanche na mesma data e no mesmo **`período`** da sessão (se o período estiver preenchido; ex.: `Matutino`, `Vespertino`). Retorna **`Lanche já consumido nesta data [no período X] (Cota atingida).`**
   * **Atenção:** A cota diária **NÃO pode ser burlada com `⚡ Bypass` ou sufixo `.`** — caso um lançamento anterior tenha sido errado, primeiro é necessário **anular/cancelar** o consumo anterior para liberar a cota novamente.
5. **Validação da Grade Horária (`grade_horarios.json`):**
   * Só é ignorada se o operador ativar **`⚡ Bypass` (`pular_grupos=True`)** (ou marcar *"Liberar acesso avulso (ignorar grupos e horários da grade)"* em `DialogoNovoConsumo`).
   * Se **não houver nenhum slot configurado** para o par `dia_da_semana + refeição` na grade, a trava horária é considerada livre e o sistema passa direto para o passo 6.
   * **Tolerância padrão:** **`±5 minutos`** antes do horário de início e após o horário de término de cada slot.
   * **Combinação de Turma e Categoria no Slot:**
     * Quando o slot especifica apenas `turmas` (e `categorias` = `*` ou vazio): exige que uma turma do aluno esteja na lista.
     * Quando especifica apenas `categorias` (e `turmas` = `*` ou vazio): exige que uma categoria do aluno (permanente **ou** pontual da reserva ativa do dia) esteja na lista.
     * Quando **ambos** (`turmas` e `categorias`) possuem valores específicos (sem `*`/`Todas`), aplica-se a regra **OU**: entra quem atender à turma **OU** à categoria.
     * Quando ambos são `*`/`Todas`/vazios: qualquer turma/categoria é aceita naquele horário.
   * **Modo `🕒 Horário Livre` (`ignorar_horario_grade=True`):** Ignora os limites de hora (`inicio`/`fim`), **mas continua exigindo** que a turma ou categoria do estudante esteja prevista em pelo menos um slot da refeição daquele dia. Em sessões abertas no Totem com **data retroativa**, o `Horário Livre` é ativado automaticamente.
6. **Regra de Elegibilidade (Reserva, Grupo ou Exceção `#`):**
   * **Em `almoço` ou `jantar`:**
     1. Se o aluno possui **reserva ativa não utilizada** naquela data e para aquele turno (`almoco=True` ou `jantar=True`), é **autorizado** com o prato da reserva (`Tradicional`, `Vegetariano`, etc.).
     2. Se não houver reserva livre, verifica se está com **`⚡ Bypass` (`pular_grupos=True`)** ➡️ autoriza com prato **`Sem Reserva (Forçado)`**.
     3. Se já havia uma reserva para aquele turno, mas já vinculada a outro consumo ativo na mesma refeição ➡️ bloqueia com **`Reserva já utilizada nesta data.`**
     4. Se não tem reserva, verifica se alguma turma/categoria efetiva do estudante está marcada como **Exceção (`#` / `excecao_grupos`)** na sessão ➡️ se sim, autoriza com prato **`Sem Reserva (Grupo)`**. Caso contrário ➡️ **`Acesso Negado`**.
   * **Em `lanche`:**
     * Não exige reserva prévia: basta que o estudante pertença a uma turma/categoria selecionada na sessão **OU** a um grupo em **Exceção (`#`)** **OU** esteja em **`⚡ Bypass`**. O prato gravado é o item configurado em `item_servido` (ou `Lanche`).

---

## 4.2 Resumo Comparativo: Normal vs. Horário Livre vs. Bypass

| Modo de Operação | Checa Aluno Ativo & Cota Diária? | Checa Relógio (Faixa `HH:MM` ±5 min)? | Exige Turma/Cat na Grade do Dia? | Exige Reserva (Almoço/Jantar) ou Grupo (Lanche)? |
| :--- | :---: | :---: | :---: | :---: |
| **Normal** | Sim | Sim | Sim (se houver slots no dia) | Sim (ou grupo em Exceção `#`) |
| **🕒 Horário Livre** | Sim | **Não** | **Sim** (se houver slots no dia) | Sim (ou grupo em Exceção `#`) |
| **Exceção `#` (por grupo)** | Sim | Conforme Normal/Horário Livre | Conforme Normal/Horário Livre | **Não** para os grupos marcados com `#` |
| **⚡ Bypass / sufixo `.`** | Sim | **Não** | **Não** | **Não** (força entrada avulsa respeitando cota) |

---

## 4.3 Normalização, Correspondência Inteligente (*Fuzzy*) e Categorias

* **Limpeza e padronização de prontuário:**
  * No Totem e na janela fallback de QR, entradas numéricas ou alfanuméricas sem prefixo completo são padronizadas automaticamente para o formato **`IQ30XXXXX`** (aceitando dígitos `0–9` e `X`, preenchendo os últimos 5 caracteres com zero à esquerda se necessário).
  * Na importação de planilhas (`ajustar_chaves_e_valores`), prefixos `IQ` seguidos de quaisquer 2 dígitos são normalizados para `IQ30`.
* **Composição de Categorias:** As categorias consideradas no atendimento, nas estatísticas e nas exportações resultam da **união** das **categorias permanentes do aluno** com as **categorias pontuais da sua reserva ativa do dia**.
  * Rótulos vazios ou legados (`""`, `"-"`, `"N/A"`, `"REGULAR"`, `"none"`, `"null"`, `"nenhuma"`) são descartados automaticamente.
* **Limiares de Busca por Nome / Prontuário (*Fuzzy Matching*):**
  * **Terminal do Operador:** Busca com `debounce` de **100 ms** a partir de **2 caracteres**. Aceita matrícula (score ≥ 85) ou nome (score ≥ 70).
  * **Totem de Autoatendimento (USB / digitação):** Se a matrícula formatada não existir, busca por nome entre alunos elegíveis com score **≥ 90**, aprovando automaticamente apenas se for candidato único, ou se tiver score **≥ 98**, ou vantagem **≥ 10 pontos** sobre o 2º colocado (caso contrário retorna *"Múltiplos resultados encontrados. Digite o prontuário."*).
  * **Importador em Lote (`AnalisadorSimplificado`):** `SCORE_MATCH_CERTO = 95`, `SCORE_MATCH_PRONTUARIO = 85`, `SCORE_MATCH_NOME = 75` (corte mínimo de sugestões `60`, exibindo até 4 candidatos).

---

## 4.4 Exclusão Lógica (*Soft Delete*), Mesclagem de Reservas e Segurança

### Auditoria de Cancelamentos (*Soft Delete*)
Ao excluir/anular um consumo (seja pela tabela do Terminal do Operador ou pelo CRUD do Totem), o registro **não é apagado fisicamente** do SQLite. Em vez disso:
* `ativo` muda para `False`;
* são gravados **`deletado_em`** (data/hora exata), **`deletado_por`** (nome do operador informado) e **`motivo_cancelamento`** (justificativa);
* a cota diária do aluno e eventual vínculo de consumo da reserva são liberados;
* ao sincronizar com a nuvem ou exportar a sessão em `.xlsx`, todos os estornos vão automaticamente para a aba **`Consumo_Cancelados`** (Google Sheets) ou **`Cancelados`** (Excel).

### Mesclagem Automática de Reservas na Importação
Ao importar reservas em lote (via assistente do Painel ou aba `DB` do Google Sheets), se houver múltiplas linhas para o mesmo **`(estudante, data)`**:
* Os turnos são **mesclados via OU lógico (`OR`)** — por exemplo, se o aluno já tinha reserva de `Almoço` e entra nova linha de `Jantar` na mesma data, a reserva resultante passa a cobrir **`Almoço e Jantar`**.
* Se o campo `prato` anterior era vazio ou `"Não especificado"`, o novo prato é assumido.
* Novas categorias pontuais da linha são adicionadas sem apagar as já associadas àquela reserva.

### Segurança nas Exportações (Anti-*Formula Injection*)
Em todas as exportações geradas pelo sistema:
* **CSV:** Qualquer célula iniciada por `=`, `+`, `-` (exceto `-` isolado), `@`, tabulação (`\t`) ou retorno de carro (`\r`) recebe prefixo de escape `'`.
* **XLSX:** Os workbooks são gravados com `strings_to_formulas=False` e `strings_to_urls=False` além da sanitização de células.

### Logs e Histórico de Sincronização (`SyncLog`)
* O banco SQLite mantém a tabela **`SyncLog`** registrando `timestamp`, `direction` (`download`/`upload`), `status` (`success`/`failure`/`unknown`), `message` e `records_affected`.
* Os logs em texto são gravados em `logs/<app>.log` (UTF-8) com rotação automática a cada **5 MB** mantendo **5 arquivos de backup**.

---

## 4.5 Estrutura das 8 Abas do Google Sheets e Impacto no Sistema

O botão **Criar Estrutura de Abas** no Setup (`--setup`) cria ou valida automaticamente todas as **8 abas oficiais** na planilha configurada, congelando e formatando a linha 1 (cabeçalho) sem sobrescrever dados já existentes:

| Nome da Aba | Cabeçalho Padrão (Linha 1) | Direção na Sincronização | Observações |
| :--- | :--- | :--- | :--- |
| **`Discentes`** | `Matrícula`, `Nome`, `Turma`, `Categoria` | Download ➡️ SQLite | Cadastra/atualiza alunos e vincula `Turma` + `Categoria` (separadas por vírgula). Salva cópia em `config/students.csv`. |
| **`DB`** | `DATA`, `MATRÍCULA`, `NOME`, `TURMA`, `REFEIÇÃO`, `DIA DA SEMANA`, `CATEGORIA`, `ALMOÇO`, `JANTAR` | Download ➡️ SQLite | Importa reservas mesclando turnos e categorias pontuais. Salva cópia em `config/reserves.csv`. |
| **`Almoço`** | `Matrícula`, `Data`, `Nome`, `Turma`, `Refeição`, `Hora`, `Categoria` | SQLite ➡️ Upload | Envia apenas linhas inéditas usando chave única `[Matrícula, Data, Hora, Categoria]`. |
| **`Jantar`** | `Matrícula`, `Data`, `Nome`, `Turma`, `Refeição`, `Hora`, `Categoria` | SQLite ➡️ Upload | Mesma estrutura e deduplicação da aba `Almoço`. |
| **`Lanche`** | `Matrícula`, `Data`, `Nome`, `Turma`, `Refeição`, `Hora`, `Categoria` | SQLite ➡️ Upload | A coluna `Refeição` recebe o item servido na sessão (ex.: `Iogurte com Cereais`). |
| **`Consumo_Cancelados`** | `Data`, `Hora Original`, `Hora Cancelamento`, `Matrícula`, `Nome`, `Turma`, `Categoria`, `Refeição`, `Cancelado Por`, `Motivo` | SQLite ➡️ Upload | Trilha de auditoria de todos os consumos anulados via *soft delete*. |
| **`Configuração`** | `Dia`, `Refeição`, `Horário Início`, `Horário Fim`, `Turmas Liberadas`, `Categorias Permitidas` | Download ➡️ `grade_horarios.json` | Quando preenchida com pelo menos um slot válido, atualiza a grade horária local no download. |
| **`Lanches`** | `Lanche` | **Bidirecional** (Download ⇄ Upload) | Une itens locais (`config/lanches.json`) e remotos sem duplicatas; ao adicionar um lanche novo na sessão, ele é enviado para esta aba. |

---

### 4.5.1 Aba `Discentes` — Cadastro de Estudantes, Turmas e Categorias

A aba `Discentes` é a base do cadastro de estudantes. Qualquer inclusão ou alteração aqui alimenta o banco local (`config/registro.db`) durante a rotina de **Download**.

```sheets
title: Planilha Refeitório (Google Sheets)
active_tab: Discentes
active_cell: D5
fx: LIB0, PAP
caption: Figura: Estrutura oficial da aba Discentes com exemplos de turmas e categorias separadas por vírgula.
| Matrícula | Nome | Turma | Categoria |
| IQ3010001 | Gustavo Pereira Santos | 2º A - MEC | [green]PAP |
| IQ3010002 | Rafaela Lima Alves | 3º B - MEC | [yellow]- |
| IQ3010003 | Manuela Machado Oliveira | 1º A - MAC | [yellow]- |
| IQ3010005 | Vitor Teixeira Marques | 2º A - MAC | [active][green]LIB0, PAP |
| IQ3010006 | Manuela Fernandes Silva | 1º B - MEC | [green]ESP1, PAP |
```

| Coluna na Planilha | Dado Esperado | Impacto Direto no Aplicativo / Totem | O Que Ocorre em Caso de Erro / Alteração |
| :--- | :--- | :--- | :--- |
| **A: `Matrícula`** | `IQ3010001` (aceita `Matrícula IQ` ou `Prontuário` via mapeamento) | • É a **chave única** do estudante no SQLite.<br>• O **Gerador de Crachás (`--cards`)** codifica exatamente este texto no **QR Code**.<br>• No leitor do Totem (webcam ou scanner USB), a busca é feita prioritariamente por este código. | **Se alterar:** O aluno é tratado como um **novo registro**; crachás antigos deixam de corresponder ao novo prontuário.<br>*Normalização automática:* Remove espaços e converte prefixos `IQXX` para `IQ30`. |
| **B: `Nome`** | Nome completo (ex.: *Gustavo Pereira Santos*) | • Exibido na tela do Totem e nos diálogos de confirmação.<br>• Usado no **Terminal do Operador (`--reg`)** e no Totem para busca instantânea por aproximação (*Fuzzy Matching*). | **Se alterar:** Atualiza o nome no banco local na próxima sincronização. |
| **C: `Turma`** | Nome da turma (ex.: *2º A - MEC*) | • Determina em qual **janela da Grade Horária** o estudante pode acessar o refeitório.<br>• Usado nos filtros rápidos ao abrir sessões e nos gráficos do Dashboard. | **Atenção:** A importação **adiciona** a nova turma aos vínculos do aluno sem remover turmas antigas. Para trocar de turma removendo a anterior, desvincule a turma antiga no **Painel Administrativo (`--painel`)**. |
| **D: `Categoria`** | Tags separadas por vírgula (ex.: `PAP`, `LIB0, PAP`, `ESP1`) | • Concede acesso em horários prioritários da Grade (ex.: faixa exclusiva para `PAP`).<br>• Exibe a tag destacada no cartão de atendimento e permite filtros em lote na sessão. | **Vazio, `-`, `N/A` ou `REGULAR`:** Ignorados automaticamente.<br>**Múltiplas categorias (`LIB0, PAP`):** O app decompõe em grupos distintos e aplica as regras de ambos. |

---

### 4.5.2 Aba `DB` — Reservas Diárias de Almoço e Jantar

A aba `DB` controla quem possui reserva ativa de **Almoço** ou **Jantar** em cada data e qual opção de prato foi escolhida.

```sheets
title: Planilha Refeitório (Google Sheets)
active_tab: DB
active_cell: E2
fx: Tradicional
caption: Figura: Estrutura oficial da aba DB (CABECALHO_RESERVAS) com indicação de prato, turnos e categoria pontual.
| DATA | MATRÍCULA | NOME | TURMA | REFEIÇÃO | DIA DA SEMANA | CATEGORIA | ALMOÇO | JANTAR |
| 15/05/2026 | IQ3010001 | Gustavo Pereira Santos | 2º A - MEC | [active][green]Tradicional | Sexta-feira | PAP | [green]Sim | [yellow]Não |
| 15/05/2026 | IQ3010005 | Vitor Teixeira Marques | 2º A - MAC | [green]Vegetariano | Sexta-feira | LIB0, PAP | [green]Sim | [green]Sim |
| 15/05/2026 | IQ3010006 | Manuela Fernandes Silva | 1º B - MEC | [green]Vegano | Sexta-feira | ESP1 | [yellow] | [green]Sim |
```

> [!NOTE]
> Além do cabeçalho padrão acima (`DATA`, `MATRÍCULA`, `NOME`, `TURMA`, `REFEIÇÃO`, `DIA DA SEMANA`, `CATEGORIA`, `ALMOÇO`, `JANTAR`), o importador também aceita cabeçalhos alternativos mapeados em `config/mapeamento_colunas.json` (como `Prontuário`, `Prato`, `Turno` / `Tipo Refeição`, `Categorias`). O estudante precisa já existir na aba `Discentes` (ou no banco local) para que sua reserva seja vinculada; linhas com matrícula desconhecida ou sem data são ignoradas.

| Colunas | Campo | Comportamento no Aplicativo | Regra de Mesclagem (*Merge*) |
| :--- | :--- | :--- | :--- |
| **A & B (`DATA`, `MATRÍCULA`)** | Chave da Reserva | Define a **chave composta `(estudante, data)`**. Se a data não coincidir com a data da sessão aberta, o aluno ficará sem reserva naquele dia. | Múltiplas linhas para o mesmo aluno e mesma data são consolidadas em **uma única reserva**. |
| **C, D, F (`NOME`, `TURMA`, `DIA DA SEMANA`)** | Campos Informativos | Facilitam a leitura humana na planilha. Não sobrescrevem o cadastro do aluno na aba `Discentes` durante a leitura de `DB`. | — |
| **E (`REFEIÇÃO`)** | Prato | Informa à equipe o prato reservado (**Tradicional**, **Vegetariano**, **Vegano**, etc.), exibido na tela de confirmação do Totem e do Terminal. | Se uma linha anterior estava vazia ou como `"Não especificado"`, a nova linha define o prato. |
| **G (`CATEGORIA`)** | Categorias Pontuais | Categorias válidas **apenas para a data da reserva**. Somam-se às categorias permanentes da aba `Discentes` sem alterar o cadastro fixo do aluno. | Todas as categorias pontuais das linhas daquele dia são unidas sem duplicação. |
| **H & I (`ALMOÇO`, `JANTAR`)** | Turnos Autorizados | Aceita valores booleanos (`Sim`/`Não`, `1`/`0`, `X`, `OK`, `true`/`false`). Caso a planilha utilize coluna `Turno` (`Almoço`, `Jantar`, `Ambos`), ela também é interpretada. | Aplica **OU lógico (`OR`)**: se uma linha libera `Almoço=Sim` e outra na mesma data libera `Jantar=Sim`, a reserva passa a cobrir **ambos os turnos**. |

---

### 4.5.3 Abas de Exportação: `Almoço`, `Jantar` e `Lanche`

Essas três abas são preenchidas **pelo aplicativo (Upload)** ao sincronizar os consumos confirmados em cada sessão.

```sheets
title: Planilha Refeitório (Google Sheets)
active_tab: Almoço
active_cell: E4
fx: Sem Reserva (Exceção)
caption: Figura: Linhas enviadas pelo aplicativo para a aba Almoço, incluindo consumos com reserva e exceções liberadas.
| Matrícula | Data | Nome | Turma | Refeição | Hora | Categoria |
| IQ3010001 | 15/05/2026 | Gustavo Pereira Santos | 2º A - MEC | [green]Tradicional | 11:34:12 | PAP |
| IQ3010005 | 15/05/2026 | Vitor Teixeira Marques | 2º A - MAC | [green]Vegetariano | 11:38:05 | LIB0, PAP |
| IQ3010002 | 15/05/2026 | Rafaela Lima Alves | 3º B - MEC | [active][yellow]Sem Reserva (Exceção) | 11:42:20 | - |
```

* **Regra de preenchimento da coluna E (`Refeição`):**
  * Em **`Almoço`** e **`Jantar`**: registra o prato da reserva utilizada (ex.: `Tradicional`, `Vegetariano`) ou **`Sem Reserva (Exceção)`** quando o acesso foi liberado via grupo em Exceção (`#`) ou `⚡ Bypass`.
  * Em **`Lanche`**: registra o item configurado na sessão (`item_servido`, ex.: `Iogurte com Cereais`, ou `Lanche`).

> [!IMPORTANT]
> **Deduplicação no Upload:** Antes de anexar novas linhas, o sistema gera uma chave de identidade composta pelas 2 primeiras e 2 últimas colunas — ou seja, **`[Matrícula, Data, Hora, Categoria]`**. Evite editar manualmente esses quatro campos em linhas já enviadas para não gerar reinserções em sincronizações futuras.

---

### 4.5.4 Aba `Consumo_Cancelados` — Trilha de Auditoria e Estornos

Sempre que um consumo é cancelado no Terminal do Operador ou no Totem, o registro recebe *soft delete* no SQLite e é enviado para `Consumo_Cancelados` no próximo Upload.

```sheets
title: Planilha Refeitório (Google Sheets)
active_tab: Consumo_Cancelados
active_cell: J2
fx: Leitura duplicada acidental
caption: Figura: Auditoria de cancelamento gerada automaticamente na aba Consumo_Cancelados.
| Data | Hora Original | Hora Cancelamento | Matrícula | Nome | Turma | Categoria | Refeição | Cancelado Por | Motivo |
| 15/05/2026 | 11:40:15 | 11:42:01 | IQ3010008 | Gabriela Ferreira Moreira | 1º A - MEC | LIB0 | Almoço | [green]Mateus | [active][yellow]Leitura duplicada acidental |
```

* **Efeito no App:** Ao confirmar o cancelamento, a cota diária do estudante e o vínculo com sua reserva são liberados imediatamente no banco local, permitindo novo registro se necessário. A deduplicação dessa aba usa `[Data, Hora Original, Cancelado Por, Motivo]`.

---

### 4.5.5 Aba `Configuração` — Grade Horária Semanal

Permite manter a grade semanal de atendimento centralizada na nuvem. Ao executar o **Download**, caso a aba contenha ao menos um slot válido, ela atualiza o arquivo local `config/grade_horarios.json`.

```sheets
title: Planilha Refeitório (Google Sheets)
active_tab: Configuração
active_cell: F2
fx: PAP, ESP1
caption: Figura: Parametrização da Grade Horária na aba Configuração com faixa prioritária seguida das turmas regulares.
| Dia | Refeição | Horário Início | Horário Fim | Turmas Liberadas | Categorias Permitidas |
| Segunda | almoco | [green]11:15 | [green]11:35 | * | [active][green]PAP, ESP1 |
| Segunda | almoco | [green]11:35 | [green]12:15 | [blue]1º A - MEC, 1º A - MAC | * |
| Segunda | almoco | [green]12:15 | [green]12:55 | [blue]2º A - MEC, 2º A - MAC | * |
```

* **Flexibilidade de preenchimento:** Aceita abreviações ou nomes completos para o dia (`Seg`, `Segunda`, `Segunda-feira`, etc.), variações da refeição (`almoco`/`Almoço`, `jantar`/`Jantar`, `lanche`/`Lanche`) e curingas `*` ou `Todas` para liberar todas as turmas/categorias naquele slot.
* **Tolerância e `Horário Livre`:** O Totem aplica tolerância automática de **±5 minutos** nas extremidades (`Horário Início` e `Horário Fim`). Se o operador ativar **🕒 Horário Livre** na sessão, os limites de relógio são ignorados, mas as turmas/categorias configuradas para o dia continuam sendo exigidas (exceto sob `⚡ Bypass`).

---

### 4.5.6 Aba `Lanches` — Cardápio Sincronizado (Bidirecional)

Mantém a lista de opções de lanches (`config/lanches.json`) sincronizada entre o computador local e a planilha.

```sheets
title: Planilha Refeitório (Google Sheets)
active_tab: Lanches
active_cell: A3
fx: Bolo de Cenoura com Suco
caption: Figura: Aba Lanches com lista de itens sincronizada bidirecionalmente com config/lanches.json.
| Lanche |
| Achocolatado com Biscoito |
| [active][green]Bolo de Cenoura com Suco |
| Iogurte com Cereais |
| Pão de Queijo com Suco |
```

* **Sincronização Bidirecional:** No Download, o sistema faz a união sem duplicatas entre os itens locais (`config/lanches.json`) e os remotos da aba `Lanches`, atualizando ambos os lados. Além disso, sempre que um novo item de lanche é digitado ao abrir uma sessão de lanche, o aplicativo o envia automaticamente em segundo plano para esta aba.

---

### 4.5.7 Síntese do Ciclo de Dados (`Google Sheets ⇄ SQLite Local`)

* **⬇️ Entrada de Dados (Download):** Lê **`Discentes`** (atualiza estudantes/grupos e gera `config/students.csv`), **`DB`** (importa e mescla reservas em `config/reserves.csv` + SQLite), **`Configuração`** (atualiza `config/grade_horarios.json` se houver slots válidos) e **`Lanches`** (unifica `config/lanches.json`). Tudo fica salvo localmente para operação autônoma mesmo sem internet.
* **⬆️ Saída de Dados (Upload):** Envia os consumos ativos das sessões para **`Almoço`**, **`Jantar`** e **`Lanche`**, envia estornos auditados para **`Consumo_Cancelados`** e publica novos itens locais na aba **`Lanches`**, sempre verificando deduplicação antes de gravar.

---

## 4.6 Exemplos Práticos de Planilhas e Arquivos JSON

### Exemplo 1: CSV de Estudantes com Cabeçalho (`Discentes`)
```csv
Matrícula IQ,Nome,Turma,Categoria
SP301001,Ana Beatriz Silva,1º Ano A - Informática,PAP
SP301002,Carlos Eduardo Santos,1º Ano A - Informática,
SP301004,Gabriel Rodrigues Costa,2º Ano B - Mecatrônica,"PAP,ESP1"
```

### Exemplo 2: CSV de Reservas para Importação (`DB` ou Assistente Passo 1)
Aceita tanto colunas booleanas (`Almoço`, `Jantar` com valores `Sim`/`Não`, `1`/`0`, `X`, `OK`, `true`/`false`) quanto coluna textual (`Turno` / `Tipo Refeição` com valores `Almoço`, `Jantar`, `Ambos`, `Almoço e Jantar`):
```csv
Prontuário,Data,Prato,Almoço,Jantar,Turno,Categorias
SP301001,15/05/2026,Tradicional,Sim,Não,Almoço,PAP
SP301003,15/05/2026,Vegetariano,Sim,Sim,Ambos,ESP1
SP301005,15/05/2026,Vegano,,Sim,Jantar,
```

### Exemplo 3: Lista Simples em TXT (`simples`)
Útil para colar rapidamente uma relação recebida por e-mail (um aluno por linha, misturando ou escolhendo prontuários ou nomes; na Etapa 2 define-se Data, Prato e Turnos padrão):
```text
SP301001
Ana Beatriz Silva
SP301002
Carlos Eduardo Santos
```

### Exemplo 4: `config/grade_horarios.json`
```json
{
  "segunda": {
    "almoco": [
      {
        "inicio": "11:15",
        "fim": "11:35",
        "turmas": ["*"],
        "categorias": ["PAP", "ESP1"]
      },
      {
        "inicio": "11:30",
        "fim": "12:15",
        "turmas": ["1º Ano A - Informática", "2º Ano B - Mecatrônica"],
        "categorias": ["*"]
      }
    ],
    "jantar": [],
    "lanche": []
  }
}
```

### Exemplo 5: `config/settings.json`
```json
{
  "pin_hash": "",
  "pin_salt": "",
  "totem": {
    "fullscreen": false,
    "camera_on_start": true,
    "require_pin_to_exit": true,
    "feedback_delay_ms": 1500,
    "camera_index": 0
  },
  "audio": {
    "habilitado": true,
    "freq_sucesso": 1000,
    "dur_sucesso_ms": 200,
    "freq_erro": 400,
    "dur_erro_ms": 1000
  }
}
```

### Exemplo 6: `config/lanches.json` e `config/session.json` e `config/spreadsheet.json`
```json
// config/lanches.json
[
  "Achocolatado e Biscoito Maisena",
  "Iogurte com Cereais",
  "Suco de Uva e Banana"
]
```
```json
// config/session.json (gerenciado automaticamente pelo Terminal e Totem)
{
  "id_sessao": 1,
  "excecao_grupos": ["3º Ano C - Edificações"],
  "ignorar_horario_grade": false
}
```
```json
// config/spreadsheet.json
{
  "spreadsheet_id": "1A2B3C4D5E6F7G8H9I0J_EXEMPLO_GOOGLE_SHEETS"
}
```

---

[⬅️ Capítulo 3 — Painel Administrativo](./03_painel_administrativo.md) | [📑 Índice](../MANUAL_DO_USUARIO.md) | [Capítulo 5 — Terminal do Operador ➡️](./05_terminal_do_operador_registrar.md)

