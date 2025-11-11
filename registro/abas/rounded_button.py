import tkinter as tk
from tkinter import font as tkFont
from typing import Any, Callable, Optional, Tuple

import ttkbootstrap as ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageColor
from ttkbootstrap.style import Colors


try:
    from PIL.Image import Resampling

    BICUBIC = Resampling.BICUBIC
except ImportError:
    BICUBIC = Image.ANTIALIAS


class RoundedButton(tk.Canvas):
    """
    Um botão personalizado com cantos arredondados e feedback visual de
    encolhimento ao ser pressionado.

    Este widget utiliza a biblioteca Pillow para renderizar sua aparência,
    permitindo um alto grau de customização visual.
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
        """
        Inicializa o widget RoundedButton.

        Args:
            master: O widget pai.
            text: O texto a ser exibido no botão.
            command: A função a ser chamada quando o botão for clicado.
            bootstyle: O estilo do ttkbootstrap para cores (ex: 'primary', 'success').
            radius: O raio dos cantos arredondados.
            font: Uma tupla contendo o nome da família da fonte e o tamanho.
            padding: Uma tupla (padx, pady) para o espaçamento interno.
            shrink_size: O número de pixels que o botão encolhe ao ser pressionado.
            state: O estado inicial do botão ('normal' ou 'disabled').
        """
        super().__init__(master, borderwidth=0, highlightthickness=0, **kwargs)

        self.command = command
        self.enabled = state.lower() != "disabled"

        padding = padding or (padx or 10, pady or 10)

        # 1. Configura os parâmetros e estilos
        self._setup_parameters(
            text,
            bootstyle,
            radius,
            font,
            padding,
            shrink_size,
            bg,
            fg,
            disabled_bg,
            disabled_fg,
            hover_color,
            press_color,
        )

        # 2. Calcula as dimensões necessárias com base no texto e padding
        self._calculate_dimensions()
        self.config(width=self.width, height=self.height)

        # 3. Cria as imagens para todos os estados do botão
        self._create_all_images()

        # 4. Exibe a imagem inicial e vincula os eventos do mouse
        self.shape_id = self.create_image(0, 0, image=self.normal_image, anchor="nw")
        self._bind_events()

        # 5. Define o estado inicial do widget
        self.configure(state=state)

    def _setup_parameters(
        self,
        text: str,
        bootstyle: Optional[str],
        radius: int,
        font_tuple: Tuple[str, int],
        padding: Tuple[int, int],
        shrink_size: int,
        bg_color: str,
        fg_color: str,
        disabled_bg: str,
        disabled_fg: str,
        hover_color: Optional[str],
        press_color: Optional[str],
    ) -> None:
        """Extrai e armazena os parâmetros de configuração como atributos da instância."""
        self.text = text
        self.radius = radius
        self.padding_x, self.padding_y = padding
        self.shrink_size = shrink_size
        self.scale_factor = 10  # Fator de superamostragem para anti-aliasing

        # Carrega a fonte com fallback
        self.font = self._load_font(font_tuple)
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.disabled_bg = disabled_bg
        self.disabled_fg = disabled_fg
        self.theme_bg_color = "#ffffff"
        # Define as cores com base no bootstyle ou em valores padrão
        if bootstyle:
            try:
                style = ttk.Style.get_instance()
                self.theme_bg_color = style.colors.get("bg")  # type: ignore
                self.bg_color = style.colors.get(bootstyle) or bg_color  # type: ignore
                self.fg_color = style.colors.get_foreground(bootstyle) or fg_color  # type: ignore
                self.disabled_bg = style.colors.get("light") or disabled_bg  # type: ignore
                self.disabled_fg = style.colors.get("secondary") or disabled_fg  # type: ignore
            except (AttributeError, ValueError):
                pass
        else:
            try:
                self.theme_bg_color = self.master.cget("bg")
            except tk.TclError:
                pass  # Ignora o erro se a cor de fundo não puder ser obtida
        # Tenta herdar a cor de fundo do widget pai

        self.hover_color = hover_color or Colors.update_hsv(self.bg_color, vd=0.15)  # type: ignore
        self.press_color = press_color or Colors.update_hsv(self.bg_color, vd=-0.15)  # type: ignore
        self.config(bg=self.theme_bg_color, highlightthickness=0)

    def _load_font(self, font_tuple: Tuple[str, int]) -> ImageFont.FreeTypeFont:
        """Carrega o objeto de fonte da Pillow, com fallback para a fonte padrão."""
        family, size = font_tuple
        try:
            return ImageFont.truetype(f"{family}.ttf", size)
        except (IOError, OSError):
            try:
                # Tenta encontrar a fonte no sistema (mais robusto)
                tk_font = tkFont.Font(family=family, size=size)
                font_path = tkFont.Font(name=tk_font.name, exists=True).actual()[
                    "family"
                ]
                return ImageFont.truetype(f"{font_path}", size)
            except Exception as e:
                # Carrega a fonte padrão da Pillow se tudo falhar
                print(e)
                return ImageFont.load_default(size=size)  # type: ignore

    def _calculate_dimensions(self) -> None:
        """Calcula a largura e altura do botão com base no texto e no padding."""
        # Usa um canvas temporário para medir o texto com precisão
        temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        text_bbox = temp_draw.textbbox((0, 0), self.text, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        self.width = int(text_width + (2 * self.padding_x))
        self.height = int(text_height + (2 * self.padding_y))

    def _create_all_images(self) -> None:
        """Renderiza e armazena as imagens para cada estado do botão."""
        shrunken_width = self.width - self.shrink_size
        shrunken_height = self.height - self.shrink_size

        shrunken_radius = (self.radius / self.width) * shrunken_width

        self.normal_image = self._create_button_image(
            self.width, self.height, self.bg_color, self.fg_color, self.radius
        )
        self.hover_image = self._create_button_image(
            self.width, self.height, self.hover_color, self.fg_color, self.radius
        )
        self.press_image = self._create_button_image(
            self.width, self.height, self.press_color, self.fg_color, self.radius
        )
        self.disabled_image = self._create_button_image(
            self.width, self.height, self.disabled_bg, self.disabled_fg, self.radius
        )
        self.shrink_image = self._create_button_image(
            shrunken_width,
            shrunken_height,
            self.press_color,
            self.fg_color,
            shrunken_radius,
        )

        self.shrink_offset_x = (self.width - shrunken_width) / 2
        self.shrink_offset_y = (self.height - shrunken_height) / 2

    def _create_button_image(
        self, width: int, height: int, bg_color: str, fg_color: str, radius: float
    ) -> ImageTk.PhotoImage:
        """
        Cria uma única imagem de botão com cantos arredondados e texto.

        Usa superamostragem (scaling) para criar bordas suaves (anti-aliasing).
        """
        # Cria uma imagem em alta resolução para o anti-aliasing
        high_res_img = Image.new(
            "RGB",
            (width * self.scale_factor, height * self.scale_factor),
            ImageColor.getrgb(self.theme_bg_color),
        )
        draw = ImageDraw.Draw(high_res_img)

        # Desenha o retângulo arredondado em alta resolução
        draw.rounded_rectangle(
            (0, 0, width * self.scale_factor, height * self.scale_factor),
            radius=radius * self.scale_factor,
            fill=bg_color,
        )

        # Reduz a imagem para o tamanho final, resultando em bordas suaves
        final_image = high_res_img.resize((width, height), BICUBIC)
        draw = ImageDraw.Draw(final_image)

        # Desenha o texto centralizado na imagem final
        draw.text(
            (width / 2, height / 2),
            self.text,
            fill=fg_color,
            font=self.font,
            anchor="mm",
        )
        return ImageTk.PhotoImage(final_image)

    def _bind_events(self) -> None:
        """Vincula os eventos do mouse aos métodos de callback."""
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def configure(self, cnf: Any = None, **kwargs) -> Any:
        """Configura o estado do botão ('normal' ou 'disabled')."""

        if "state" in kwargs:
            state = kwargs.get("state") or ""
            self.enabled = state.lower() != "disabled"
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
        """Callback para quando o mouse entra na área do botão."""
        if self.enabled:
            self.itemconfig(self.shape_id, image=self.hover_image)
            self.moveto(self.shape_id, 0, 0)

    def _on_leave(self, _event: tk.Event) -> None:
        """Callback para quando o mouse sai da área do botão."""
        if self.enabled:
            self.itemconfig(self.shape_id, image=self.normal_image)
            self.moveto(self.shape_id, 0, 0)

    def _on_press(self, _event: tk.Event) -> None:
        """Callback para quando o botão do mouse é pressionado."""
        if self.enabled:
            self.itemconfig(self.shape_id, image=self.shrink_image)
            self.moveto(self.shape_id, self.shrink_offset_x, self.shrink_offset_y)

    def _on_release(self, event: tk.Event) -> None:
        """
        Callback para quando o botão do mouse é solto.
        Executa o comando se o mouse ainda estiver sobre o botão.
        """
        if self.enabled:
            self.moveto(self.shape_id, 0, 0)
            # Verifica se o cursor ainda está sobre o widget no momento da liberação
            if self.winfo_containing(event.x_root, event.y_root) == self:
                self.itemconfig(self.shape_id, image=self.hover_image)
                if self.command:
                    self.after(10, self.command)
            else:
                self.itemconfig(self.shape_id, image=self.normal_image)
