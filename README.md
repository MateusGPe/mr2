# Registro de Refeições

Sistema completo para gestão, controle e registro de presença em refeições de estudantes, projetado para instituições de ensino e refeitórios escolares. A aplicação oferece interfaces gráficas modernas construídas com Tkinter e `ttkbootstrap`, suporte a autoatendimento autônomo com leitura de QR Code, sincronização bidirecional com Google Sheets e persistência local via SQLite e SQLAlchemy 2.0.

---

## 🚀 Funcionalidades Principais

* **Totem de Autoatendimento (`autoatendimento`):** Interface autônoma otimizada para terminais e totens interativos. Oferece validação em tempo real com leitura de QR Code via webcam (OpenCV e PyZbar), leitor USB de código de barras ou digitação manual com busca incremental de matrículas. Conta com menu de contexto rápido para o operador, dashboard embutido e gestão de consumos.
* **Terminal de Registro do Operador (`registrar`):** Interface desktop para atendentes e operadores. Permite a busca rápida de estudantes por nome ou matrícula, confirmação visual/sonora de atendimento, controle de sessão ativa e filtragem instantânea de turmas autorizadas.
* **Painel Administrativo (`painel`):** Central de controle com abas dedicadas para:
  * **Alunos:** Consulta, cadastro, edição e exclusão de estudantes e suas turmas.
  * **Reservas:** Gestão de refeições reservadas por data e estudante.
  * **Importação:** Carga em lote inteligente de listas de alunos e reservas a partir de planilhas CSV ou Excel (`.xlsx`).
  * **Dashboard:** Visualização de indicadores estatísticos e métricas consolidadas de consumo.
* **Gerenciamento de Sessões de Refeição:** Criação e configuração de sessões com tipo de refeição (almoço, lanche, jantar, etc.), data, horário, período e vinculação com as turmas autorizadas.
* **Sincronização com Google Sheets:** Sincronização automática e sob demanda com planilhas do Google Drive via Google Sheets API (gspread), garantindo envio seguro de registros e controle de duplicidade.
* **Exportação de Relatórios:** Exportação dos dados de consumo e frequência de refeições para relatórios formatados em Excel (`.xlsx`) na pasta de Documentos do usuário.
* **Persistência Confiável:** Armazenamento local estruturado em banco de dados SQLite orquestrado pelo ORM SQLAlchemy 2.0 com integridade referencial e suporte a migrações em memória para testes automatizados.

---

## 🛠️ Requisitos e Pré-requisitos

* **Python:** Versão 3.11 ou superior (até 3.13).
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
| `registro.db` | Banco de dados SQLite local contendo alunos, grupos, reservas e consumos registrados. |
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

A aplicação disponibiliza três comandos principais registrados no `pyproject.toml`:

### 1. Totem de Autoatendimento
Inicia o terminal autônomo com suporte a leitura por câmera de QR Code, leitor de código de barras USB ou busca manual:
```bash
uv run autoatendimento
```
> **Dica do Operador:** Clique com o botão direito no cabeçalho ou use `F2` para abrir o menu de controle do operador (abertura de sessão, filtros de turma, dashboard e CRUD de consumos).

### 2. Terminal do Operador / Registro
Inicia a interface de registro assistido pelo atendente:
```bash
uv run registrar
```

### 3. Painel Administrativo
Inicia a central de cadastros, importação de dados e análise estatística:
```bash
uv run painel
```

---

## 🧪 Testes Automatizados

O projeto conta com uma ampla suíte de testes unitários e de integração, garantindo a integridade dos serviços, fachada, regras de negócio e interface:

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
E-mail: [mateus.pereira@ifsp.edu.br](mailto:mateus.pereira@ifsp.edu.br)  
Copyright (c) 2024-2025 Instituto Federal de Educação, Ciência e Tecnologia de São Paulo (IFSP)