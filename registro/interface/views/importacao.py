import traceback
from datetime import datetime
from typing import Optional, Dict, List
import flet as ft
from registro.nucleo.facade import FachadaRegistro
from registro.importar.facade import FachadaImportacao
from registro.interface.utils import show_error, show_success

class ImportacaoWizard(ft.Container):
    """Wizard de 4 passos para importação de dados externos."""

    def __init__(self, fachada_nucleo: FachadaRegistro, fachada_imp: FachadaImportacao):
        super().__init__()
        self.fachada_nucleo = fachada_nucleo
        self.fachada_imp = fachada_imp
        self.expand = True
        self.padding = 20
        self.file_picker = ft.FilePicker(on_result=self._on_file_pick)
        
        # Estado
        self.current_path: Optional[str] = None
        self.itens_revisao: List[Dict] = []
        self.resumo_analise: Optional[Dict] = None

        self.step_content = ft.Container(expand=True)
        self.progress = ft.ProgressBar(value=0.0, height=5)
        self.lbl_titulo = ft.Text("Assistente de Importação", size=20, weight="bold")

        self.content = ft.Column([
            self.lbl_titulo, self.progress,
            ft.Divider(color=ft.Colors.TRANSPARENT, height=20),
            self.step_content
        ], expand=True)

    def did_mount(self):
        if self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)
            self.page.update()
        self._go_step_1()
    
    def will_unmount(self):
        if self.file_picker in self.page.overlay: self.page.overlay.remove(self.file_picker)

    # --- PASSO 1 ---
    def _go_step_1(self):
        self.progress.value, self.lbl_titulo.value = 0.25, "Passo 1: Selecionar Arquivo"
        self.txt_file = ft.TextField(read_only=True, label="Caminho", expand=True, value=self.current_path or "")
        self.rg_tipo = ft.RadioGroup(content=ft.Column([
            ft.Radio(value="auto", label="Automático"),
            ft.Radio(value="simples", label="Lista Simples (.txt)"),
            ft.Radio(value="header", label="CSV com Cabeçalho"),
            ft.Radio(value="sheets", label="Google Sheets (ID)")
        ]), value="auto")

        self.step_content.content = ft.Column([
            ft.Container(content=ft.Column([ft.Text("Fonte", weight="bold"), self.rg_tipo]), padding=10, border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=10),
            ft.Divider(height=20, color="transparent"),
            ft.Row([self.txt_file, ft.ElevatedButton("Buscar...", icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: self.file_picker.pick_files())]),
            ft.Container(expand=True),
            ft.Row([ft.FilledButton("Analisar >", on_click=self._iniciar_analise)], alignment=ft.MainAxisAlignment.END)
        ])
        self.update()

    def _on_file_pick(self, e):
        if e.files:
            self.current_path = e.files[0].path
            self.txt_file.value = self.current_path
            self.txt_file.update()

    def _iniciar_analise(self, e):
        if not self.txt_file.value: return show_error(self.page, "Selecione um arquivo.")
        try:
            res = self.fachada_imp.analisar_arquivo(self.txt_file.value, self.rg_tipo.value)
            self.resumo_analise, self.itens_revisao = res["resumo"], res["itens_revisao"]
            show_success(self.page, "Análise concluída!")
            self._go_step_2()
        except Exception as ex: show_error(self.page, f"Erro: {ex}")

    # --- PASSO 2 ---
    def _go_step_2(self):
        self.progress.value, self.lbl_titulo.value = 0.50, "Passo 2: Revisão"
        res = self.resumo_analise
        self.txt_data_def = ft.TextField(label="Data Padrão", width=150, value=datetime.now().strftime("%d/%m/%Y"))
        self.dd_prato_def = ft.Dropdown(label="Refeição", width=150, options=[ft.dropdown.Option("Almoço"), ft.dropdown.Option("Jantar")], value="Almoço")
        
        lv_itens = ft.ListView(expand=True, spacing=10)
        if not self.itens_revisao: lv_itens.controls.append(ft.Text("Sem conflitos.", size=16))
        else:
            for item in self.itens_revisao: lv_itens.controls.append(self._criar_linha_revisao(item))

        self.step_content.content = ft.Column([
            ft.Container(content=ft.Text(f"✅ {res['automaticos']} OK | ⚠️ {res['para_revisao']} Revisar | ❌ {res['invalidos']} Inválidos", weight="bold", color=ft.Colors.ON_SECONDARY_CONTAINER), bgcolor=ft.Colors.SECONDARY_CONTAINER, padding=10, border_radius=5),
            ft.Row([self.txt_data_def, self.dd_prato_def]), ft.Divider(),
            lv_itens,
            ft.Row([ft.OutlinedButton("Voltar", on_click=lambda _: self._go_step_1()), ft.FilledButton("Simular >", on_click=self._ir_preview)], alignment="spaceBetween")
        ])
        self.update()

    def _criar_linha_revisao(self, item):
        dados = item["dados_csv"]
        dd_acao = ft.Dropdown(width=140, options=[ft.dropdown.Option("CRIAR_NOVO"), ft.dropdown.Option("VINCULAR"), ft.dropdown.Option("IGNORAR")], value=item["resolucao_escolhida"], dense=True, text_size=12)
        
        opts_cand = [ft.dropdown.Option(key=str(c['id']), text=f"{c['nome']} ({c['score']}%)") for c in item.get("candidatos", [])]
        dd_cand = ft.Dropdown(width=200, options=opts_cand, dense=True, text_size=12, disabled=(len(opts_cand) == 0), value=str(item.get("candidatos", [{}])[0].get('id')) if item.get("candidatos") else None)
        
        def on_change_acao(e):
            item["resolucao_escolhida"] = dd_acao.value
            dd_cand.disabled = (dd_acao.value != "VINCULAR")
            dd_cand.update()
        
        def on_change_cand(e):
            if dd_cand.value: item["id_estudante_vinculo"] = int(dd_cand.value)

        dd_acao.on_change, dd_cand.on_change = on_change_acao, on_change_cand
        if item.get("candidatos") and item["resolucao_escolhida"] == "VINCULAR": item["id_estudante_vinculo"] = item["candidatos"][0]['id']

        return ft.Container(content=ft.Row([
            ft.Column([ft.Text(f"{dados.get('nome','?')} ({dados.get('prontuario','')})", weight="bold"), ft.Text(f"Problema: {item['tipo_conflito']}", size=11, color="red")], expand=True),
            dd_cand, dd_acao
        ]), padding=10, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=8)

    # --- PASSO 3 ---
    def _ir_preview(self, e):
        defaults = {"data": self.txt_data_def.value, "prato": self.dd_prato_def.value} if self.txt_data_def.value else {}
        try:
            self.preview_dados = self.fachada_imp.simular_importacao(self.itens_revisao, defaults)
            self._go_step_3()
        except Exception as ex: show_error(self.page, f"Erro: {ex}")

    def _go_step_3(self):
        self.progress.value, self.lbl_titulo.value = 0.75, "Passo 3: Confirmação"
        novos, reservas = self.preview_dados.get("novos_estudantes", []), self.preview_dados.get("reservas", [])
        
        t1 = ft.DataTable(columns=[ft.DataColumn(ft.Text("Prontuário")), ft.DataColumn(ft.Text("Nome"))], rows=[ft.DataRow(cells=[ft.DataCell(ft.Text(n['prontuario'])), ft.DataCell(ft.Text(n['nome']))]) for n in novos[:50]])
        t2 = ft.DataTable(columns=[ft.DataColumn(ft.Text("Data")), ft.DataColumn(ft.Text("Nome"))], rows=[ft.DataRow(cells=[ft.DataCell(ft.Text(r['data'])), ft.DataCell(ft.Text(r['aluno']))]) for r in reservas[:50]])
        
        tabs = ft.Tabs(tabs=[ft.Tab(text=f"Novos ({len(novos)})", content=ft.Column([t1], scroll=True)), ft.Tab(text=f"Reservas ({len(reservas)})", content=ft.Column([t2], scroll=True))], expand=True)
        self.step_content.content = ft.Column([
            ft.Text("Pré-visualização (Amostra dos primeiros 50).", color="grey"), tabs,
            ft.Row([ft.OutlinedButton("Voltar", on_click=lambda _: self._go_step_2()), ft.FilledButton("SALVAR TUDO", on_click=self._executar_salvar, style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN))], alignment="spaceBetween")
        ])
        self.update()

    def _executar_salvar(self, e):
        def confirmar(ev):
            self.page.close(dlg)
            self._processar_final()
        dlg = ft.AlertDialog(title=ft.Text("Confirmar?"), content=ft.Text("Alteração permanente no banco."), actions=[ft.TextButton("Não", on_click=lambda e: self.page.close(dlg)), ft.FilledButton("Sim", on_click=confirmar)])
        self.page.open(dlg)

    def _processar_final(self):
        defaults = {"data": self.txt_data_def.value, "prato": self.dd_prato_def.value}
        try:
            self.res_final = self.fachada_imp.confirmar_importacao(self.itens_revisao, defaults)
            self._go_step_4()
        except Exception as e: show_error(self.page, f"Erro fatal: {e}")

    # --- PASSO 4 ---
    def _go_step_4(self):
        self.progress.value, self.lbl_titulo.value = 1.0, "Concluído!"
        self.step_content.content = ft.Container(content=ft.Column([
            ft.Icon(ft.Icons.CHECK_CIRCLE, size=80, color=ft.Colors.GREEN),
            ft.Text("Sucesso!", size=24, weight="bold"),
            ft.Text(f"Estudantes: {self.res_final.get('estudantes_criados',0)}\nReservas: {self.res_final.get('reservas_criadas',0)}", text_align="center"),
            ft.ElevatedButton("Nova Importação", on_click=lambda _: self._go_step_1())
        ], alignment="center", horizontal_alignment="center"), alignment=ft.alignment.center, expand=True)
        self.update()