# 📖 Manual Completo do Usuário — Sistema de Refeitório (v1.3.0)

Bem-vindo ao manual oficial do **Sistema de Refeitório (`registro`)**. Esta documentação cobre integralmente cada módulo, janela, botão, caixa de diálogo, regra de negócio, formato de arquivo e rotina operacional para uso diário em refeitórios escolares e instituições de ensino.

![Menu Inicial do Sistema de Refeitório](./imagens/01_launcher_principal.png)

---

## 🧭 Sumário dos Capítulos

Explore o conteúdo completo de forma sequencial ou salte diretamente para o módulo que deseja consultar:

| Capítulo | Assunto | O que você encontra |
| :--- | :--- | :--- |
| [**1. Visão Geral e Arquitetura**](manual/01_visao_geral_e_arquitetura.md) | Introdução, módulos e instalação | Visão dos 5 módulos no Menu Inicial, flags de linha de comando (`--reg`, `--painel`, `--auto`, `--cards`, `--setup`), preparação inicial e estrutura de pastas. |
| [**2. Configuração Inicial e Setup**](manual/02_configuracao_inicial_e_setup.md) | `--setup` (6 abas + PIN) | Checklist de integridade, Google Cloud (`credentials.json`, OAuth / Service Account, ID da planilha), Totem & PIN PBKDF2, Grade Horária semanal, Backups `.zip` e atalhos no Windows. |
| [**3. Painel Administrativo**](manual/03_painel_administrativo.md) | `--painel` (5 abas + diálogos) | Gestão completa de Alunos (ativos/inativos, duplicidade), Turmas/Categorias (`VincularAlunoDialog`), Reservas, Importação inteligente (CSV/XLSX/Google) e Dashboard + exportações `.xlsx`. |
| [**4. Regras de Negócio e Integração**](manual/04_regras_de_negocio_e_integracao.md) | Motor de regras, CSV/XLSX e Sheets | Normalização de prontuários (`IQXX` ➔ `IQ30`), leitura booleana/turno em planilhas, regras de bloqueio de Almoço/Jantar vs Lanche, Grade Horária, sanitização OWASP em relatórios e tabela `sync_logs`. |
| [**5. Terminal do Operador**](manual/05_terminal_do_operador_registrar.md) | `--reg` (`AppRegistro`) | Abertura/retomada de sessões, pré-seleção de data pela Grade, filtro de turmas (`#` sem reserva e Horário Livre), busca com curingas, registro com confirmação, cancelamento auditado e janela secundária Self-Service. |
| [**6. Totem de Autoatendimento**](manual/06_totem_de_autoatendimento.md) | `--auto` (`AppSelfService`) | Leitura por webcam/scanner USB, tela pública *Horários das Turmas* (`LIBERADO AGORA` / `EM BREVE` / `ENCERRADO`), Menu de Contexto (`F2` / `Ctrl+M` / botão direito), teclado PIN, aba Consumos + lançamento manual offline e Dashboard interno + sync Google Sheets. |
| [**7. Gerador de Crachás**](manual/07_gerador_de_crachas.md) | `--cards` (`registro.cards`) | Carregamento por SQLite ou CSV/XLSX, filtros por busca e turmas, grade A4 (`2–4 × 4–10`), marcas de corte, limite de 40 caracteres no cabeçalho PDF, exportação em PDF vetorial ou HTML e payload puro do QR Code. |
| [**8. Rotinas do Dia a Dia**](manual/08_rotinas_do_dia_a_dia.md) | Guia prático de operação | Checklists de pré-abertura, condução do horário de pico, tratamento de exceções na fila (aluno sem crachá, troca de prato, turma antecipada), fechamento de turno e manutenção semanal. |
| [**9. Atalhos de Teclado e Referência Rápida**](manual/09_atalhos_de_teclado_e_referencia_rapida.md) | Referência rápida | Tabela consolidada de atalhos e gestos reais por janela, curingas (`todos`, `---`, `***`, `..`, `.`, `#`), comandos CLI, badges de interface e mapa completo de arquivos gerados. |
| [**10. Solução de Problemas e FAQ**](manual/10_solucao_de_problemas_e_faq.md) | Diagnóstico e suporte | Respostas diretas para falhas OAuth/Google Cloud, bloqueios de sessão/horário, câmera ou leitor USB, redefinição de PIN esquecido, restauração de backup `.zip` e logs rotativos em `logs/`. |

---

## ⚡ Primeiros Passos (Guia em 4 Etapas)

Se esta é a primeira vez que o sistema está sendo implantado no campus:

1. **Inicie o Menu Principal** a partir da pasta raiz do projeto:
   ```bash
   uv run python -m registro
   ```
2. Abra **⚙️ Configurações & Início Rápido (`--setup`)** para configurar credenciais do Google Cloud (se for usar planilhas online), definir o **PIN do Operador**, ajustar a **Grade de Horários Semanal** e verificar o checklist verde.
3. Abra o **📊 Painel Administrativo (`--painel`)** na aba **Importação** para carregar a planilha de estudantes e criar suas turmas/categorias e reservas do dia.
4. No horário do atendimento, escolha conforme a infraestrutura do refeitório:
   * **Terminal do Operador (`--reg`)** para balcão assistido com confirmação ágil pelo servidor.
   * **Totem de Autoatendimento (`--auto`)** para guichê autônomo com webcam/QR Code, fila offline e controle de grade horária.

---

## 📚 Glossário Rápido do Sistema

* **Prontuário / Matrícula**: Código identificador único do estudante (ex.: `SP301001`, `IQ301234`). O sistema ignora prefixos padrão na busca numérica e normaliza códigos legados como `IQXX...` para `IQ30...`.
* **Grupo (`turma` vs `categoria`)**: Além das turmas acadêmicas (ex.: `1º Ano A - Informática`), estudantes podem possuir categorias (ex.: `Evento Robótica`, `Optativa Artes`, `PAP`, `ESP1`) que funcionam como **grupos equivalentes às turmas** na Grade Horária e nos filtros de sessão — separadas apenas para não misturar turmas regulares com eventos, optativas ou agrupamentos arbitrários.
* **Sessão de Refeição**: Representa um turno específico de atendimento (`almoço`, `jantar` ou `lanche`) em uma data e período, vinculando grupos participantes e contabilizando os consumos realizados.
* **Reserva (`Almoço` / `Jantar`)**: Direito prévio agendado para o estudante em determinada data, com preferência de prato (`Tradicional`, `Vegetariano`, `Vegano`, etc.). Necessária para abrir sessões de Almoço e Jantar.
* **Lanche (Item Servido)**: Modalidade simplificada de sessão voltada ao intervalo/lanche; lista todos os alunos elegíveis dos grupos da sessão sem exigir reserva prévia individual.
* **Exceção `#` (Sem Reserva)**: Liberação intencional de consumo avulso registrada no Terminal do Operador ou liberada por grupo no filtro de turmas, marcada nos relatórios com `#`.
* **Modo Horário Livre**: Chave temporária da sessão que ignora as janelas de hora da Grade Horária sem desligar a filtragem das turmas autorizadas no dia.
* **Grade Horária (`grade_horarios.json`)**: Escala semanal que define intervalos (`inicio`–`fim`) e quais turmas/categorias têm acesso permitido em cada janela.
* **Fila Offline (`SyncLog` / Pendente Sync)**: Consumos gravados instantaneamente no banco local `config/registro.db` caso a internet caia, aguardando envio posterior ao Google Sheets.

---

*Versão da documentação: **1.3.0** • Todas as capturas de tela em [`docs/imagens/`](./imagens/) refletem a interface gráfica real do sistema.*
