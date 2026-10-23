# Registro de Refeições

[![Versão](https://img.shields.io/badge/versão-1.2.2-blue.svg)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)
[![Licença](https://img.shields.io/badge/licença-MIT-green.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Sistema completo para gestão, controle e registro de presença em refeições de estudantes, projetado para instituições de ensino e refeitórios escolares. A aplicação oferece interfaces gráficas modernas construídas com Tkinter e `ttkbootstrap`, suporte a autoatendimento autônomo com leitura de QR Code, sincronização bidirecional com Google Sheets e persistência local via SQLite e SQLAlchemy 2.0.

---

## 🚀 Funcionalidades Principais

* **Lançador Unificado (`registro`):** Ponto de entrada central com menu visual moderno para inicialização de qualquer módulo da aplicação com um único clique, além de despachante inteligente de argumentos via linha de comando (`--painel`, `--reg`, `--auto`, `--setup`).
* **Central de Início Rápido & Configurações (`setup`):** Hub visual com checklist de integridade em tempo real, links diretos e importador de credenciais do Google Cloud Console, teste de conexão da Google Sheets API, definição de PIN touch-friendly para o Totem, gerenciador completo de backups e restaurações compactadas (`.zip`) e criação de atalhos no Windows.
* **Totem de Autoatendimento (`autoatendimento`):** Interface autônoma otimizada para terminais e totens interativos. Oferece validação em tempo real com leitura de QR Code via webcam (OpenCV e PyZbar), leitor USB de código de barras ou digitação manual com busca incremental de matrículas. Conta com menu de contexto protegido por PIN para o operador (`F2` ou clique com botão direito no cabeçalho), dashboard embutido e gestão de consumos.
* **Terminal de Registro do Operador (`registrar`):** Interface desktop para atendentes e operadores. Permite a busca rápida de estudantes por nome ou matrícula, confirmação visual/sonora de atendimento, controle de sessão ativa e filtragem instantânea de turmas autorizadas.
* **Painel Administrativo (`painel`):** Central de controle com abas dedicadas para:
  * **Alunos:** Consulta, cadastro, edição e exclusão de estudantes e vínculo de turmas.
  * **Turmas:** CRUD completo e gerenciamento de turmas/cursos integrados.
  * **Reservas:** Gestão de refeições reservadas por data e estudante.
  * **Importação:** Carga em lote inteligente de listas de alunos e reservas a partir de planilhas CSV ou Excel (`.xlsx`).
  * **Dashboard:** Visualização de indicadores estatísticos e métricas consolidadas de consumo e taxa de comparecimento.
* **Gerenciamento de Sessões de Refeição:** Criação e configuração de sessões com tipo de refeição (almoço, lanche, jantar, etc.), data, horário, período e vinculação com as turmas autorizadas.
* **Sincronização com Google Sheets:** Sincronização automática e sob demanda com planilhas do Google Drive via Google Sheets API (`gspread`), garantindo envio seguro de registros e controle de duplicidade.
* **Exportação de Relatórios:** Exportação dos dados de consumo e frequência de refeições para relatórios formatados em Excel (`.xlsx`) na pasta de Documentos do usuário.
* **Persistência Confiável:** Armazenamento local estruturado em banco de dados SQLite orquestrado pelo ORM SQLAlchemy 2.0 com integridade referencial e suporte a migrações em memória para testes automatizados.

---

## 🛠️ Requisitos e Pré-requisitos

* **Python:** Versão 3.11 ou superior (compatível até 3.13).
* **uv:** Gerenciador de projetos e dependências Python ultrarrápido ([documentação oficial do uv](https://docs.astral.sh/uv/)).
* **Câmera/Webcam (Opcional):** Necessária caso queira utilizar a leitura de QR Code no totem de autoatendimento.

---

## 📦 Instalação

1. Clone o repositório ou faça o download dos arquivos do projeto:
   ```bash
   git clone https://github.com/MateusGPe/mr2.git
   cd mr2
   ```

2. Instale o ambiente virtual e todas as dependências com o `uv`:
   ```bash
   uv sync
   ```

---

## ⚙️ Configuração

Os arquivos de configuração e dados locais residem no diretório `./config`:

| Arquivo | Descrição |
| :--- | :--- |
| `credentials.json` | Credenciais da Conta de Serviço (Service Account) ou OAuth da Google Cloud Platform para acesso à API do Google Sheets. |
| `token.json` | Token de autenticação gerado automaticamente após a autorização do Google. |
| `spreadsheet.json` | Contém o ID/chave da planilha do Google Sheets utilizada para sincronização. |
| `lanches.json` | Lista e opções de itens de refeição/lanche disponíveis para seleção rápida. |
| `presets_turmas.json` | Predefinições de turmas e grupos para facilidade na abertura de sessões. |
| `session.json` | Estado da sessão de refeição atualmente ativa (gerenciado automaticamente pelo sistema). |
| `registro.db` | Banco de dados SQLite local contendo alunos, turmas, reservas e consumos registrados. |
| `students.xlsx` / `reserves.xlsx` | Planilhas modelo ou de importação em lote de alunos e reservas. |

### Configuração da API do Google Sheets
Para habilitar a sincronização online com planilhas:
1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto e ative a **Google Sheets API** e a **Google Drive API**.
2. Crie uma Conta de Serviço ou credencial de aplicativo de desktop e baixe o arquivo JSON.
3. Salve o arquivo como `./config/credentials.json`.
4. Defina o ID da sua planilha Google em `./config/spreadsheet.json`:
   ```json
   {
     "spreadsheet_id": "SEU_ID_DE_PLANILHA_AQUI"
   }
   ```

---

## 💻 Como Executar

### 1. Ponto de Entrada Principal: Lançador Unificado (`registro`)

O lançador central é o método recomendado de inicialização da aplicação:

```bash
uv run registro
```

Ao executar sem parâmetros, um menu gráfico interativo é exibido, permitindo abrir qualquer um dos módulos com facilidade. Você também pode disparar diretamente um módulo específico através de argumentos na linha de comando:

| Parâmetro | Ação |
| :--- | :--- |
| `uv run registro --reg` (ou `/reg`) | Abre diretamente o **Registro de Refeições (Operador)** |
| `uv run registro --painel` (ou `/painel`) | Abre diretamente o **Painel Administrativo** |
| `uv run registro --auto` (ou `/auto`) | Abre diretamente o **Totem de Autoatendimento** |
| `uv run registro --setup` (ou `/setup`, `--config`) | Abre a **Central de Configurações & Início Rápido** |
| `uv run registro --help` (ou `/help`) | Exibe a mensagem de ajuda e opções disponíveis |

### 2. Comandos Diretos / Atalhos

Se preferir iniciar diretamente um módulo sem passar pelo menu ou pelas flags do lançador:

* **Central de Configurações & Início Rápido:**
  ```bash
  uv run setup
  ```

* **Totem de Autoatendimento:**
  ```bash
  uv run autoatendimento
  ```
  > **Dica do Operador:** Pressione `F2` ou clique com o botão direito no cabeçalho para acessar o menu de controle do operador protegido por PIN.

* **Terminal do Operador / Registro:**
  ```bash
  uv run registrar
  ```

* **Painel Administrativo:**
  ```bash
  uv run painel
  ```

---

## 🖨️ Utilitários e Ferramentas

### Geração de Cartões de Acesso / Crachás (`registro.cards` / `cards.py`)

O repositório disponibiliza uma ferramenta gráfica moderna (`ttkbootstrap`) com motor de renderização vetorial de alta precisão em **PDF** (ReportLab) e **HTML** para impressão de crachás/cartões de identificação com QR Code em folhas A4:

* **Inicialização da Ferramenta:**
  ```bash
  uv run cards
  # ou via script na raiz:
  uv run python cards.py
  ```

* **Recursos da Interface Gráfica:**
  * **Importação Flexível:** Suporte a arquivos CSV e planilhas Excel (`.xlsx`, `.xls`), com detecção automática de delimitadores e mapeamento inteligente de colunas (matrícula, nome, turma), além de atalho para carregar o arquivo padrão (`config/students.csv`).
  * **Tabela e Busca Dinâmica:** Pré-visualização com filtro/busca em tempo real e contador de discentes e páginas A4 estimadas.
  * **Personalização de Grade:** Ajuste de colunas e linhas (padrão 3×7 = 21 cartões por folha A4).
  * **Guias de Corte e Metadados:** Linhas de corte opcionais para facilitar recorte com guilhotina ou tesoura, numeração de páginas (`P.1`, `P.2`...) e cabeçalho institucional personalizável.
  * **Exportação:** Exportação direta para **PDF vetorial** milimétrico (`ReportLab`) ou **HTML** com grade CSS flexível.

* **Compilação do Executável Independente (`cards.exe`):**
  ```bash
  uv run pyinstaller cards.spec
  ```
  Gera o executável autocontido `dist/cards.exe`.

---

## 🔨 Compilação e Distribuição (Executáveis Windows)

O projeto disponibiliza arquivos de especificação do PyInstaller pré-configurados com todas as dependências (incluindo binários do `pyzbar`, temas do `ttkbootstrap`, fonte `roboto.ttf` e metadados de versão `version_info.txt`).

### Opção 1: Executável Único Portátil (`onefile`)

Gera um único arquivo `.exe` autocontido (`dist/registro.exe`), ideal para distribuição simplificada:

```bash
uv run pyinstaller registro_onefile.spec
```

* O executável final é salvo em `dist/registro.exe`.
* Pode ser executado com duplo clique (abre o menu gráfico) ou via linha de comando com os parâmetros `--painel`, `--reg`, `--auto`.
* **Nota de Distribuição:** Ao distribuir o executável, certifique-se de que a pasta `config/` esteja localizada junto ao `.exe` (ou no diretório de execução).

### Opção 2: Pasta com Executáveis Compartilhados (`onedir`)

Gera uma pasta com todos os executáveis individuais (`dist/registro/`) compartilhando bibliotecas e DLLs:

```bash
uv run pyinstaller registro_onedir.spec
```

* Gera em `dist/registro/` os executáveis: `registro.exe`, `registrar.exe`, `painel.exe` e `autoatendimento.exe`.
* Ideal para inicialização rápida e menor tempo de extração na inicialização.

---

## 🧪 Testes Automatizados

O projeto conta com uma ampla suíte de testes unitários e de integração, garantindo a integridade dos serviços, fachada, regras de negócio e interfaces:

```bash
uv run pytest
```

Para verificar análise estática e regras de estilo com o Ruff:
```bash
uv run ruff check .
```

---

## 📄 Licença

Este projeto está licenciado sob os termos da [Licença MIT](LICENSE).

---

## 👤 Autoria e Contato

**Mateus G. Pereira**  
* GitHub: [@MateusGPe](https://github.com/MateusGPe)  
* E-mail: [mateus.pereira@ifsp.edu.br](mailto:mateus.pereira@ifsp.edu.br)  
* Copyright (c) 2024-2026 Mateus G. Pereira