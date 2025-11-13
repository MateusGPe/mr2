import tkinter as tk
from typing import Any, Callable, Optional, Tuple, cast

import ttkbootstrap as ttk
from ttkbootstrap.style import Colors
from PIL import Image, ImageDraw, ImageFont, ImageTk

try:
    from PIL.Image import Resampling

    BICUBIC = Resampling.BICUBIC
except ImportError:
    BICUBIC = Image.ANTIALIAS


class RoundedButton(tk.Canvas):
    """
    Um botão personalizado com cantos arredondados que suporta
    redimensionamento dinâmico com `pack` e `grid`.

    Este widget utiliza a biblioteca Pillow para renderizar sua aparência,
    permitindo um alto grau de customização visual e flexibilidade de layout.
    """

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None] | None = None,
        bootstyle: Optional[str] = None,
        radius: int = 10,
        font: Tuple[str, int] = ("./roboto", 16),
        padding: Optional[Tuple[int, int]] = None,
        shrink_size: int = 2,
        state: str = "normal",
        bg: str = "#5e5e5e",
        fg: str = "white",
        disabled_bg: str = "#f0f0f0",
        disabled_fg: str = "#a0a0a0",
        hover_color: Optional[str] = None,
        press_color: Optional[str] = None,
        padx: Optional[int] = None,
        pady: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(master, borderwidth=0, highlightthickness=0, **kwargs)
        self.normal_image: Optional[ImageTk.PhotoImage] = None
        self.hover_image: Optional[ImageTk.PhotoImage] = None
        self.press_image: Optional[ImageTk.PhotoImage] = None
        self.disabled_image: Optional[ImageTk.PhotoImage] = None
        self.shrink_image: Optional[ImageTk.PhotoImage] = None
        self.shrink_offset_x: int
        self.shrink_offset_y: int
        self.command = command
        self.enabled = state.lower() != "disabled"

        # Guarda o padding original para referência
        self._original_padding = padding or (padx or 10, pady or 10)
        self._original_font_tuple = font

        # Variáveis para evitar redesenhos desnecessários
        self._last_width = 0
        self._last_height = 0

        # 1. Configura os parâmetros e estilos
        self._setup_parameters(
            text,
            bootstyle,
            radius,
            self._original_font_tuple,
            self._original_padding,
            shrink_size,
            bg,
            fg,
            disabled_bg,
            disabled_fg,
            hover_color,
            press_color,
        )

        # 2. Calcula as dimensões INICIAIS para a primeira renderização
        self._calculate_initial_dimensions()

        # 3. Cria a forma (imagem) no canvas que será atualizada
        self.shape_id = self.create_image(0, 0, anchor="nw")

        # 4. Vincula os eventos, incluindo o crucial <Configure>
        self._bind_events()

        # 5. Define o estado inicial do widget
        self.configure(state=state)

    def _setup_parameters(
        self,
        text,
        bootstyle,
        radius,
        font_tuple,
        padding,
        shrink_size,
        bg_color,
        fg_color,
        disabled_bg,
        disabled_fg,
        hover_color,
        press_color,
    ):
        """Extrai e armazena os parâmetros de configuração como atributos da instância."""
        self.text = text
        self.radius = radius
        self.padding_x, self.padding_y = padding
        self.shrink_size = shrink_size
        self.scale_factor = 10
        self.font_family = font_tuple[0]
        self._initial_font_size = font_tuple[1]

        self.bg_color = bg_color
        self.fg_color = fg_color
        self.disabled_bg = disabled_bg
        self.disabled_fg = disabled_fg
        self.theme_bg_color = "#ffffff"

        if bootstyle and (style := ttk.Style.get_instance()):
            try:
                scolors = cast(Colors, style.colors)
                self.theme_bg_color = scolors.bg
                self.bg_color = scolors.get(bootstyle) or bg_color
                self.fg_color = scolors.get_foreground(bootstyle) or fg_color
                self.disabled_bg = scolors.light or disabled_bg
                self.disabled_fg = scolors.secondary or disabled_fg
            except (AttributeError, ValueError):
                pass
        else:
            try:
                self.theme_bg_color = self.master.cget("bg")
            except tk.TclError:
                pass

        self.hover_color = hover_color or Colors.update_hsv(self.bg_color, vd=0.15)  # type: ignore
        self.press_color = press_color or Colors.update_hsv(self.bg_color, vd=-0.15)  # type: ignore
        self.config(bg=self.theme_bg_color, highlightthickness=0)

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Carrega o objeto de fonte da Pillow com um tamanho específico."""
        try:
            return ImageFont.truetype(f"{self.font_family}.ttf", size, encoding="unic")
        except (IOError, OSError):
            return ImageFont.load_default(size=size)

    def _calculate_initial_dimensions(self) -> None:
        """Calcula a largura e altura INICIAIS do botão com base no texto."""
        font = self._load_font(self._initial_font_size)
        temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        text_bbox = temp_draw.textbbox((0, 0), self.text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Define as dimensões mínimas/iniciais
        self.width = int(text_width + (2 * self.padding_x))
        self.height = int(text_height + (2 * self.padding_y))

        # Configura o tamanho mínimo que o widget pode ter
        self.config(width=self.width, height=self.height)

    def _get_best_font_size(
        self, width: int, height: int
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """
        Encontra o maior tamanho de fonte que cabe DENTRO da largura e altura
        disponíveis do botão, considerando o padding.
        """
        available_width = width - (2 * self.padding_x)
        available_height = height - (2 * self.padding_y)

        # Retorna uma fonte mínima se não houver espaço
        if available_width < 1 or available_height < 1:
            return self._load_font(1)

        font_size = 1  # Começa com o menor tamanho possível
        last_good_font = self._load_font(font_size)

        while True:
            font = self._load_font(font_size)

            # Mede as dimensões do texto com a fonte atual
            text_bbox = font.getbbox(self.text)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # Se o texto estourou a largura OU a altura, a fonte anterior era a melhor
            if text_width > available_width or text_height > available_height:
                return last_good_font

            last_good_font = font
            font_size += 1

    def _redraw_images(self, width: int, height: int) -> None:
        """Renderiza e armazena as imagens para cada estado do botão com as dimensões dadas."""
        if width <= 0 or height <= 0:
            return

        shrunken_width = width - self.shrink_size
        shrunken_height = height - self.shrink_size

        # Raio proporcional
        radius = min(self.radius, width / 2, height / 2)
        shrunken_radius = (radius / width) * shrunken_width if width > 0 else 0

        font = self._get_best_font_size(width, height)
        shrunken_font = self._get_best_font_size(shrunken_width, shrunken_height)

        self.normal_image = self._create_button_image(
            width, height, self.bg_color, self.fg_color, radius, font
        )
        self.hover_image = self._create_button_image(
            width, height, self.hover_color, self.fg_color, radius, font
        )
        self.press_image = self._create_button_image(
            width, height, self.press_color, self.fg_color, radius, font
        )
        self.disabled_image = self._create_button_image(
            width, height, self.disabled_bg, self.disabled_fg, radius, font
        )
        self.shrink_image = self._create_button_image(
            shrunken_width,
            shrunken_height,
            self.press_color,
            self.fg_color,
            shrunken_radius,
            shrunken_font,
        )

        self.shrink_offset_x = (width - shrunken_width) / 2
        self.shrink_offset_y = (height - shrunken_height) / 2

        # Atualiza a imagem exibida para o estado atual
        if not self.enabled:
            self.itemconfig(self.shape_id, image=self.disabled_image)
        else:
            self.itemconfig(self.shape_id, image=self.normal_image)
        self.moveto(self.shape_id, 0, 0)

    def _create_button_image(self, width, height, bg_color, fg_color, radius, font):
        """Cria uma única imagem de botão com anti-aliasing."""
        # Garante que a imagem não tenha dimensão zero
        w, h = max(1, int(width)), max(1, int(height))

        high_res_img = Image.new(
            "RGB", (w * self.scale_factor, h * self.scale_factor), self.theme_bg_color
        )
        draw = ImageDraw.Draw(high_res_img)

        draw.rounded_rectangle(
            (0, 0, w * self.scale_factor, h * self.scale_factor),
            radius=radius * self.scale_factor,
            fill=bg_color,
        )

        final_image = high_res_img.resize((w, h), BICUBIC)
        draw = ImageDraw.Draw(final_image)

        draw.text(
            (w / 2, h / 2),
            self.text,
            fill=fg_color,
            font=font,
            anchor="mm",
        )
        return ImageTk.PhotoImage(final_image)

    def _bind_events(self) -> None:
        """Vincula os eventos do mouse e o evento de configuração."""
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event: tk.Event) -> None:
        """Callback para quando o widget é redimensionado."""
        new_width = event.width
        new_height = event.height

        # Redesenha apenas se o tamanho realmente mudou
        if new_width != self._last_width or new_height != self._last_height:
            if (
                new_width > 1 and new_height > 1
            ):  # Evita redesenhar para tamanhos inválidos
                self._last_width = new_width
                self._last_height = new_height
                self._redraw_images(new_width, new_height)

    def configure(self, cnf: Any = None, **kwargs) -> Any:
        if "state" in kwargs:
            state = kwargs.get("state") or ""
            self.enabled = state.lower() != "disabled"
            if (
                self.disabled_image and self.normal_image
            ):  # Garante que as imagens existem
                if not self.enabled:
                    self.itemconfig(self.shape_id, image=self.disabled_image)
                else:
                    self.itemconfig(self.shape_id, image=self.normal_image)
            return
        elif cnf and cnf == "state":
            return "normal" if self.enabled else "disable"
        return super().configure(cnf, **kwargs)

    config = configure

    def _on_enter(self, _event: tk.Event) -> None:
        if self.enabled:
            self.itemconfig(self.shape_id, image=self.hover_image)
            self.moveto(self.shape_id, 0, 0)

    def _on_leave(self, _event: tk.Event) -> None:
        if self.enabled:
            self.itemconfig(self.shape_id, image=self.normal_image)
            self.moveto(self.shape_id, 0, 0)

    def _on_press(self, _event: tk.Event) -> None:
        if self.enabled:
            self.itemconfig(self.shape_id, image=self.shrink_image)
            self.moveto(self.shape_id, self.shrink_offset_x, self.shrink_offset_y)

    def _on_release(self, event: tk.Event) -> None:
        if self.enabled:
            self.moveto(self.shape_id, 0, 0)
            if self.winfo_containing(event.x_root, event.y_root) == self:
                self.itemconfig(self.shape_id, image=self.hover_image)
                if self.command:
                    self.after(10, self.command)
            else:
                self.itemconfig(self.shape_id, image=self.normal_image)


# --- Exemplo de Uso ---
if __name__ == "__main__":
    root = ttk.Window(themename="litera")
    root.title("RoundedButton - Verificação de Largura e Altura")
    root.geometry("600x400")
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    # Este botão irá demonstrar a eficácia do novo método
    LONG_TEXT = "Este é um texto bem longo para testar o ajuste da fonte"
    btn = RoundedButton(root, text=LONG_TEXT, bootstyle="warning", radius=15)
    btn.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

    root.mainloop()
