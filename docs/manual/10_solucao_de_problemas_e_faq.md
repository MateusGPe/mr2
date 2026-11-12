# 10. Solução de Problemas e Perguntas Frequentes (FAQ)

Consulte este guia rápido caso encontre mensagens de bloqueio, falhas de câmera ou erros de sincronização durante o uso diário.

---

## 10.1. Integração Google Cloud e Planilhas

### "Arquivo de credenciais não encontrado em `config/credentials.json`"
* **Causa**: O aplicativo tentou sincronizar ou autenticar no Google Drive/Sheets sem o arquivo JSON do projeto Google Cloud na pasta `config/`.
* **Como resolver**:
  1. Abra **Configurações & Início Rápido (`--setup`)** ➔ aba **Google Cloud & Planilha**.
  2. Clique em **Importar `credentials.json`** e selecione o arquivo baixado no Google Cloud Console (cliente Desktop OAuth ou Service Account).
  3. Clique em **Testar Conexão / Autenticar**.

### Erro de autenticação expirada ou `invalid_grant` (`token.json`)
* **Causa**: O token de acesso salvo em `config/token.json` foi revogado, expirou em projeto em modo de teste do Google, ou pertence a outra conta.
* **Como resolver**:
  1. No **Setup** ➔ aba **Google Cloud & Planilha**, use a ação para limpar/revogar o token atual (ou remova o arquivo `config/token.json` manualmente com o sistema fechado).
  2. Clique em **Autenticar** novamente para abrir o navegador e autorizar a conta institucional correta.

### A sincronização falha em horários sem internet no refeitório
* **Comportamento normal**: O **Totem de Autoatendimento** continua operando normalmente offline usando o SQLite local (`config/registro.db`).
* Os registros pendentes de envio ficam sinalizados na aba **Consumos** e são enfileirados para o próximo envio automático ou quando você acionar **Enviar Consumos (Google Sheets)** pelo Menu de Controles (`F2`, `Ctrl+M` ou botão direito) após a conexão voltar.

---

## 10.2. Regras de Sessão, Reservas e Grade Horária

### Não consigo abrir uma sessão de **Almoço** ou **Jantar**
* **Causa**: Para **Almoço** e **Jantar**, o sistema verifica se existe ao menos **1 reserva ativa** (não cancelada) no banco de dados para aquela data e turno (`almoco=True` ou `jantar=True`).
* **Como resolver**:
  1. Abra o **Painel Administrativo** ➔ aba **Importação** e carregue a planilha de reservas daquele dia (ou baixe do Google Sheets).
  2. Confira na aba **Reservas** se a data exibida corresponde ao dia da sessão que deseja abrir.

### O aluno tem reserva, mas o Totem bloqueia dizendo que está fora do horário
* **Causa**: O relógio atual do computador está fora de qualquer intervalo liberado na **Grade Horária** (`config/grade_horarios.json`) para a turma ou categoria do aluno naquele dia da semana e refeição.
* **Como resolver**:
  * **Se a turma inteira foi liberada excepcionalmente hoje**: no Totem, abra o Menu de Controles (`F2`, `Ctrl+M` ou botão direito) ➔ **Filtrar Turmas da Sessão...** e libere aquela turma, ou ative **Modo Horário Livre** para ignorar a trava da grade mantendo as turmas do dia.
  * **Se a janela permanente mudou**: abra o **Setup** ➔ aba **Grade de Horários** e ajuste os horários daquele dia da semana.
  * **Para o aluno conferir sua janela sozinho**: basta clicar no subtítulo da refeição ativa na tela inicial do Totem para abrir **Horários de Acesso por Turma**.

### "Aluno não aparece para registro" mesmo existindo no cadastro
* **Verificações rápidas**:
  1. No **Painel Administrativo** ➔ aba **Alunos**, confira se o cadastro não está marcado como **Inativo**.
  2. Para sessões de **Almoço** / **Jantar**, confira na aba **Reservas** se há reserva válida naquela data e se não foi cancelada.
  3. Confira se as turmas marcadas na sessão atual (**Filtrar Turmas da Sessão...**) incluem a turma (ou categoria) do estudante.

### Ao escolher outra data no diálogo de Sessão, a seleção de turmas muda
* **Comportamento esperado**: Quando você altera a **Data** dentro do diálogo **Abrir / Gerenciar Sessão**, o sistema recalcula automaticamente qual é o dia da semana correspondente e aplica a seleção padrão da **Grade do Dia** daquele dia da semana.

---

## 10.3. Hardware: Webcam, Leitor USB e Áudio

### A webcam não abre ou abre a câmera errada (ex.: câmera embutida em vez da USB)
* **Como resolver**:
  1. Abra **Configurações & Início Rápido (`--setup`)** ➔ aba **Totem & Segurança**.
  2. Altere o **Índice da Câmera** (tente `0`, `1` ou `2` se houver múltiplas câmeras conectadas).
  3. No Windows, confirme em *Configurações ➔ Privacidade ➔ Câmera* que aplicativos da área de trabalho têm permissão de acesso e que nenhum outro programa está segurando a webcam.

### Leitor de código de barras / QR USB digita caracteres estranhos ou não registra
* **Verificações**:
  1. Verifique se o layout de teclado do Windows está compatível com o leitor (ABNT/ABNT2) e se o leitor USB (modo teclado HID) está configurado para finalizar cada leitura com **Enter**.
  2. No **Terminal do Operador**, confira se o foco está na caixa de busca; no **Totem**, o redirecionamento global encaminha dígitos alfanuméricos automaticamente para o leitor manual quando a tela de leitura está visível sem diálogos abertos.

### Não sai som de bipe no Totem
* **Como resolver**:
  1. Verifique se o áudio do terminal Windows não está no mudo.
  2. No **Setup** ➔ aba **Totem & Segurança**, confirme que os alertas sonoros estão habilitados (`settings.json` ➔ `audio.habilitado`) e confira as frequências configuradas (padrão: `1000 Hz` sucesso / `400 Hz` erro).

---

## 10.4. Segurança, PIN e Backups

### Esqueci o PIN de segurança do Totem e do Setup
* **Importante**: Por segurança, o sistema armazena apenas o hash criptográfico (PBKDF2-HMAC-SHA256) e um salt aleatório em `config/settings.json` — **não existe recuperação visual do PIN antigo**.
* **Como redefinir com acesso físico ao computador**:
  1. Feche todas as janelas do sistema.
  2. Abra `config/settings.json` em um editor de texto e defina `"pin_hash": ""` e `"pin_salt": ""` (mantendo o restante do JSON válido).
  3. Reabra o módulo **Setup (`--setup`)** ➔ aba **Totem & Segurança** e cadastre um novo PIN numérico imediatamente.

### Como desfazer um erro grande de importação ou recuperar o banco após falha de energia
1. Feche os terminais e abra **Configurações & Início Rápido (`--setup`)** ➔ aba **Backups & Restauração**.
2. Selecione o arquivo **`.zip`** mais recente anterior ao ocorrido na lista de backups e clique em **Restaurar Backup Selecionado** (o sistema cria automaticamente uma cópia compactada de segurança antes de sobrescrever a pasta `config/`).

### Onde encontrar detalhes técnicos para reportar um bug à TI?
* Abra o diretório `logs/` na raiz do sistema (ou use o atalho na aba **Geral & Utilitários** do Setup). Cada aplicação grava logs rotativos de até **5 MB** (mantendo **5** arquivos anteriores) com horário exato, mensagens e pilhas de erro completas.

---

* **Anterior:** [9. Atalhos de Teclado e Referência Rápida](09_atalhos_de_teclado_e_referencia_rapida.md)
* **Voltar ao Índice:** [Manual do Usuário (Início)](../MANUAL_DO_USUARIO.md)
