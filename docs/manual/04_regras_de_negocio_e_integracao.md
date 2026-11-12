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

## 4.5 Estrutura das 8 Abas do Google Sheets

O botão **Criar Estrutura de Abas** no Setup cria/valida exatamente estas abas e cabeçalhos:

| Nome da Aba | Cabeçalho Padrão (Linha 1) | Direção na Sincronização | Observações |
| :--- | :--- | :--- | :--- |
| **`Discentes`** | `Matrícula IQ`, `Nome`, `Turma`, `Categoria` | Download ➡️ SQLite | Cadastra/atualiza alunos e vincula `Turma` + `Categoria` (separadas por vírgula). Salva cópia em `config/students.csv`. |
| **`DB`** | `Prontuário`, `Data`, `Prato`, `Almoço`, `Jantar`, `Turno`, `Categorias` | Download ➡️ SQLite | Importa reservas mesclando turnos e categorias pontuais. Salva cópia em `config/reserves.csv`. |
| **`Almoço`** | `Matrícula`, `Data`, `Nome`, `Turma`, `Refeição`, `Hora`, `Categoria` | SQLite ➡️ Upload | Envia apenas linhas inéditas usando chave única `[Matrícula, Data, Hora, Categoria]`. |
| **`Jantar`** | `Matrícula`, `Data`, `Nome`, `Turma`, `Refeição`, `Hora`, `Categoria` | SQLite ➡️ Upload | Mesma estrutura e deduplicação da aba `Almoço`. |
| **`Lanche`** | `Matrícula`, `Data`, `Nome`, `Turma`, `Refeição`, `Hora`, `Categoria` | SQLite ➡️ Upload | A coluna `Refeição` recebe o item servido na sessão (ex.: `Iogurte com Cereais`). |
| **`Consumo_Cancelados`** | `Data`, `Hora Consumo`, `Hora Cancelamento`, `Matrícula`, `Nome`, `Turma`, `Categoria`, `Refeição`, `Operador`, `Motivo` | SQLite ➡️ Upload | Trilha de auditoria de todos os consumos anulados via *soft delete*. |
| **`Configuração`** | `Dia`, `Refeição`, `Início`, `Fim`, `Turmas`, `Categorias` | Download ➡️ `grade_horarios.json` | Quando preenchida com slots válidos, atualiza a grade local no download. Aceita `Seg`/`Segunda-feira`, `Ter`..`Dom` e `*`/`Todas`. |
| **`Lanches`** | `Item / Cardápio` | **Bidirecional** (Download ⇄ Upload) | Une itens locais (`lanches.json`) e remotos sem duplicatas; ao adicionar um lanche novo na sessão, ele é enviado em segundo plano para esta aba. |

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

