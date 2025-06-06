import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass
from typing import Optional, Union

from cereja import Window
from cereja.config.cj_types import RECT

try:
    import tkinter as tk
    from tkinter import messagebox, filedialog, simpledialog
except ImportError:
    raise ImportError("Tkinter is required for this module. Please install it with 'pip install tk'.")


class RegionSelector:
    def __init__(self,
                 root):
        """
        Inicializa o seletor de região usando um Toplevel transparente
        que ocupa toda a tela. Permite ao usuário clicar e arrastar
        para definir um novo retângulo. Se for passado um retângulo
        inicial, ele será desenhado como referência antes do ajuste.
        """
        self.root = root
        self.start_x = 0
        self.start_y = 0
        self.rect_id: Optional[int] = None
        self.coords: Optional[RECT] = None  # Tupla (x1, y1, x2, y2)
        self.initial_rect: Optional[RECT] = None

    def select_region(self,
                      initial_rect: Optional[RECT] = None) -> Optional[RECT]:
        """
        Abre uma janela sobre toda a tela para o usuário desenhar
        ou ajustar o retângulo. Se initial_rect for fornecido, desenha
        esse retângulo inicialmente como referência. Retorna uma tupla
        de quatro inteiros (x1, y1, x2, y2).
        """
        self.initial_rect = initial_rect

        # Cria Toplevel transparente
        self.top = tk.Toplevel(self.root)
        self.top.attributes('-fullscreen', True)  # Ocupa toda a tela
        self.top.attributes('-alpha', 0.3)  # Transparência
        self.top.attributes('-topmost', True)  # Fica acima de todas as janelas
        self.top.config(cursor="crosshair")  # Cursor em cruz para seleção

        # Canvas para desenhar o retângulo de seleção
        self.canvas = tk.Canvas(self.top, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Se houver retângulo inicial, desenha com cor azul clara
        if self.initial_rect:
            x1, y1, x2, y2 = self.initial_rect
            self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline="cyan", width=2, dash=(4, 2)
            )
            # Define coords inicialmente para o valor atual
            self.coords = self.initial_rect

        # Bind de eventos de mouse para permitir novo desenho/ajuste
        self.canvas.bind("<ButtonPress-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)

        # Impede interação com a janela principal enquanto seleciona
        self.top.grab_set()
        self.root.wait_window(self.top)  # Aguarda até que a janela de seleção seja fechada

        return self.coords  # Retorna as coordenadas finais (ou o initial se não houver ajuste)

    def select_region_from_image(self,
                                 img: Union[str, bytes],
                                 initial_rect: Optional[RECT] = None) -> Optional[RECT]:
        """
        Abre uma janela para o usuário selecionar uma região de um arquivo de imagem.
        O usuário pode clicar e arrastar para definir um retângulo, que será retornado
        como coordenadas (x1, y1, x2, y2).
        """
        self.initial_rect = initial_rect if initial_rect else self.coords
        # Necessário alocarar uma janela para exibir a imagem
        self.top = tk.Toplevel(self.root)
        self.top.title("Seleção de Região")
        # self.top.attributes('-fullscreen', True)  # Ocupa toda a tela
        # self.top.attributes('-alpha', 0.3)  # Transparência
        self.top.attributes('-topmost', True)  # Fica acima de todas as janelas
        self.top.config(cursor="crosshair")  # Cursor em cruz para seleção
        # focus inicial na janela
        self.top.focus_set()
        self.canvas = tk.Canvas(self.top, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Carrega a imagem no canvas
        try:
            # Se for uma string, assume que é um caminho de arquivo
            self.tk_image = tk.PhotoImage(file=img) if isinstance(img, str) else tk.PhotoImage(
                    data=img.decode("latin1"))
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar imagem': {e}")
            self.top.destroy()
            return None
        self.display_image = self.tk_image
        orig_w = self.tk_image.width()
        orig_h = self.tk_image.height()
        self.canvas.config(width=orig_w, height=orig_h)
        self.canvas.create_image(0, 0, anchor="nw", image=self.display_image)
        # Se houver retângulo inicial, desenha com cor azul clara
        if self.initial_rect:
            x1, y1, x2, y2 = self.initial_rect
            self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline="cyan", width=2, dash=(4, 2)
            )
            # Define coords inicialmente para o valor atual
            self.coords = self.initial_rect
        # Bind de eventos de mouse para permitir novo desenho/ajuste
        self.canvas.bind("<ButtonPress-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)
        # bind ESC para fechar a janela sem retornar nada
        self.top.bind("<Escape>", self._on_escape)
        self.root.wait_window(self.top)  # Aguarda até que a janela de seleção seja fechada
        return self.coords  # Retorna as coordenadas finais (ou o initial se não houver ajuste)

    def _on_escape(self,
                   event):
        """
        Cancela a seleção e fecha a janela de seleção.
        """
        # Fecha a janela de seleção
        self.top.destroy()

    def _on_button_press(self,
                         event):
        # Quando o usuário inicia um novo clique, remove retângulo anterior (se desenhado)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        # Registra o ponto inicial do clique para novo desenho
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        # Cria um retângulo inicial (invisível até arrastar)
        self.rect_id = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y,
                outline="red", width=2
        )

    def _on_mouse_drag(self,
                       event):
        # Atualiza o retângulo enquanto o mouse é arrastado
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        # Atualiza as coordenadas do retângulo desenhado
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def _on_button_release(self,
                           event):
        # Quando o botão do mouse é liberado, armazena as coordenadas finais
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        x1 = int(min(self.start_x, end_x))
        y1 = int(min(self.start_y, end_y))
        x2 = int(max(self.start_x, end_x))
        y2 = int(max(self.start_y, end_y))
        self.coords = (x1, y1, x2, y2)
        # Fecha a janela de seleção
        self.top.destroy()


class BaseImageWindow:
    """
    Base class for image display windows.
    Provides:
      - Toplevel + Canvas setup
      - ESC key to close
      - CTRL+MouseWheel for zoom, centered under cursor
      - Métodos para recarregar a imagem sem destruir a janela:
           .load_image_from_path(path: str)
           .load_image_from_data(ppm_bytes: bytes)
    """

    def __init__(self,
                 parent: tk.Tk,
                 title: str = "Image Window",
                 resizable: bool = False):
        """
        Inicializa um Toplevel vazio e configura variáveis de zoom/offset.
        """
        self.parent = parent

        # parâmetros de zoom/offset
        self.zoom_factor = 1
        self.offset_x = 0
        self.offset_y = 0

        # referências a imagens
        self.tk_image: Optional[tk.PhotoImage] = None  # imagem original (PhotoImage)
        self.display_image: Optional[tk.PhotoImage] = None  # imagem redimensionada

        # dimensões do canvas
        self.canvas_width = 0
        self.canvas_height = 0

        # coordenadas iniciais de clique (para subclasses usarem, se houver)
        self.start_x = 0
        self.start_y = 0

        # ID do retângulo (para subclasses)
        self.rect_id: Optional[int] = None

        # cria Toplevel e Canvas (a subclasse irá configurá-lo em _setup_canvas)
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        if resizable:
            self.window.resizable(True, True)
        else:
            self.window.resizable(False, False)
        self.window.config(cursor="crosshair")
        # focus inicial na janela
        self.window.focus_set()

        # variável que armazenará o Canvas
        self.canvas: Optional[tk.Canvas] = None
        self._setup_canvas()

        # ESC para fechar
        self.window.bind("<Escape>", self._on_escape)
        # CTRL+Scroll para zoom
        self.window.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)

    @property
    def is_destroyed(self) -> bool:
        """
        Verifica se a janela foi destruída.
        """
        return not self.window.winfo_exists()

    def _setup_canvas(self):
        """
        Deve ser sobrescrito pela subclasse:
          • criar Canvas
          • definir self.canvas_width, self.canvas_height
          • carregar imagem inicial em self.tk_image
          • definir self.display_image = self.tk_image
          • exibir no Canvas com self.canvas.create_image(...)
        """
        raise NotImplementedError()

    def _on_escape(self,
                   event):
        """
        Fecha a janela sem retornar nada.
        """
        self.window.destroy()

    def _on_ctrl_mousewheel(self,
                            event):
        """
        Controla o zoom via CTRL + roda do mouse:
         - Se event.delta > 0 e zoom < 8: zoom in (x2), até 8×.
         - Se event.delta < 0 e zoom > 1: zoom out (/2), até 1×.
        Ajusta offset_x/offset_y para manter o pixel sob o cursor fixo.
        Depois, redesenha o canvas inteiro (imagem + elementos extras).
        """
        old_zoom = self.zoom_factor
        new_zoom = old_zoom

        if event.delta > 0 and old_zoom < 8:
            new_zoom = old_zoom * 2
            if new_zoom > 8:
                new_zoom = 8
        elif event.delta < 0 and old_zoom > 1:
            new_zoom = old_zoom // 2
            if new_zoom < 1:
                new_zoom = 1

        if new_zoom == old_zoom:
            return

        # determina pixel (original) sob cursor
        img_x = int((event.x - self.offset_x) / old_zoom)
        img_y = int((event.y - self.offset_y) / old_zoom)

        # atualiza zoom_factor e cria nova display_image
        self.zoom_factor = new_zoom
        self._apply_zoom()

        new_w = self.display_image.width()
        new_h = self.display_image.height()

        # recalcula offset para manter o pixel sob o cursor
        self.offset_x = event.x - img_x * new_zoom
        self.offset_y = event.y - img_y * new_zoom

        # limita offset para não mostrar área vazia
        if self.offset_x > 0:
            self.offset_x = 0
        if self.offset_y > 0:
            self.offset_y = 0
        if new_w + self.offset_x < self.canvas_width:
            self.offset_x = self.canvas_width - new_w
        if new_h + self.offset_y < self.canvas_height:
            self.offset_y = self.canvas_height - new_h

        # redesenha o conteúdo do canvas
        self._redraw_canvas()

    def _apply_zoom(self):
        """
        Substitui self.display_image, aplicando self.zoom_factor em self.tk_image.
        PhotoImage.zoom() e subsample() esperam inteiros:
          - Se zoom_factor >=1: use tk_image.zoom(int, int)
          - Se zoom_factor <1: use tk_image.subsample(int, int)
        """
        if not self.tk_image:
            return

        if self.zoom_factor >= 1:
            z = int(self.zoom_factor)
            self.display_image = self.tk_image.zoom(z, z)
        else:
            inv = int(1 / self.zoom_factor)
            if inv < 1:
                inv = 1
            self.display_image = self.tk_image.subsample(inv, inv)

    def _on_zoom_redraw(self):
        """
        Hook para subclasses: chamado após zoom para redesenhar retângulos,
        guias ou outros elementos adicionais sobre a imagem.
        """
        pass

    def _redraw_canvas(self):
        """
        Limpa e redesenha completamente o canvas:
         1) ajusta tamanho do canvas (self.canvas.config)
         2) desenha self.display_image em (self.offset_x, self.offset_y)
         3) chama _on_zoom_redraw para que subclasses desenhem retângulos, guias etc.
        """
        if not self.canvas or not self.display_image:
            return

        self.canvas.delete("all")
        self.canvas.config(width=self.canvas_width, height=self.canvas_height)
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self.display_image)
        self._on_zoom_redraw()

    def load_image_from_path(self,
                             path: str):
        """
        Recarrega uma nova imagem a partir de arquivo (PNG, PPM etc.):
         - carrega PhotoImage em self.tk_image
         - reseta zoom_factor = 1, offset_x = offset_y = 0
         - define display_image = tk_image
         - atualiza canvas_width/canvas_height ao tamanho original
         - chama _redraw_canvas() para desenhar a nova imagem
        Se falhar ao carregar, mostra um messagebox e mantém a janela.
        """
        try:
            new_img = tk.PhotoImage(file=path)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar imagem '{path}': {e}")
            return

        # atualiza referências
        self.tk_image = new_img
        self.zoom_factor = 1
        self.offset_x = 0
        self.offset_y = 0
        self.display_image = new_img

        # ajusta tamanho do canvas
        orig_w = new_img.width()
        orig_h = new_img.height()
        self.canvas_width = orig_w
        self.canvas_height = orig_h

        # redesenha toda a área
        self._redraw_canvas()

    def load_image_from_data(self,
                             ppm_bytes: bytes):
        """
        Recarrega a janela a partir de bytes PPM em memória (P6):
         - converte ppm_bytes em string para PhotoImage(data=…)
         - reseta zoom_factor = 1, offset_x = offset_y = 0
         - define display_image = tk_image e atualiza canvas_width/height
         - chama _redraw_canvas() para desenhar a nova imagem
        Se falhar ao criar PhotoImage, exibe messagebox e mantém a janela.
        """
        try:
            # aqui decodificamos os bytes PPM diretamente em string "raw"
            ppm_str = ppm_bytes.decode("latin1")
            new_img = tk.PhotoImage(data=ppm_str)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar PPM em memória: {e}")
            return

        # atualiza referências
        self.tk_image = new_img
        self.zoom_factor = 1
        self.offset_x = 0
        self.offset_y = 0
        self.display_image = new_img

        # ajusta tamanho do canvas
        orig_w = new_img.width()
        orig_h = new_img.height()
        self.canvas_width = orig_w
        self.canvas_height = orig_h

        # redesenha toda a área
        self._redraw_canvas()


class ImageWindow(BaseImageWindow):
    """
    Janela básica para apenas exibir uma imagem com zoom e ESC para fechar.
    """

    def __init__(self,
                 parent: tk.Tk,
                 image_path: str,
                 title: str = "Image Viewer"):
        self.image_path = image_path
        super().__init__(parent, title)

    def _setup_canvas(self):
        """
        Carrega a imagem inicial e exibe-a no Canvas, sem seleção de retângulos.
        """
        try:
            self.tk_image = tk.PhotoImage(file=self.image_path)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar imagem '{self.image_path}': {e}")
            self.window.destroy()
            return

        # display_image começa igual ao tk_image (zoom=1)
        self.display_image = self.tk_image
        orig_w = self.tk_image.width()
        orig_h = self.tk_image.height()
        self.canvas_width = orig_w
        self.canvas_height = orig_h

        # configura Canvas
        self.canvas = tk.Canvas(self.window, width=orig_w, height=orig_h)
        self.canvas.pack()

        # exibe a imagem
        self.canvas.create_image(0, 0, anchor="nw", image=self.display_image)


class ImageRegionSelector(ImageWindow):
    """
    Permite desenhar/selecionar um retângulo sobre a imagem exibida,
    retornando as coordenadas (x1, y1, x2, y2) na escala original.
    """

    def __init__(self,
                 parent: tk.Tk,
                 image_path: str,
                 initial_rect: Optional[RECT] = None):
        """
        initial_rect, se fornecido, deve ser (x1, y1, x2, y2) na escala original.
        """
        self.initial_rect = initial_rect
        self.coords: Optional[RECT] = None
        super().__init__(parent, image_path, title="Selecione Região")
        # Ao final do __init__, a janela já está aberta e pronta para interação

    def _setup_canvas(self):
        """
        Carrega a imagem inicial e configura Canvas, além de bindar eventos de clique/arrasto.
        """
        try:
            self.tk_image = tk.PhotoImage(file=self.image_path)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar imagem '{self.image_path}': {e}")
            self.window.destroy()
            return

        # display_image = tk_image (zoom=1×)
        self.display_image = self.tk_image
        orig_w = self.tk_image.width()
        orig_h = self.tk_image.height()
        self.canvas_width = orig_w
        self.canvas_height = orig_h

        # configura Canvas
        self.canvas = tk.Canvas(self.window, width=orig_w, height=orig_h)
        self.canvas.pack()

        # exibe a imagem
        self.canvas.create_image(0, 0, anchor="nw", image=self.display_image)

        # se tiver retângulo inicial, desenha em ciano pontilhado
        if self.initial_rect:
            x1, y1, x2, y2 = self.initial_rect
            self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline="cyan", width=2, dash=(4, 2)
            )

        # bind de mouse para desenhar retângulo
        self.canvas.bind("<ButtonPress-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)

    def _on_zoom_redraw(self):
        """
        Redesenha o retângulo inicial (se existir) após zoom.
        """
        if not self.initial_rect:
            return

        x1, y1, x2, y2 = self.initial_rect
        z = self.zoom_factor
        ox = self.offset_x
        oy = self.offset_y

        zx1 = int(x1 * z + ox)
        zy1 = int(y1 * z + oy)
        zx2 = int(x2 * z + ox)
        zy2 = int(y2 * z + oy)

        self.canvas.create_rectangle(
                zx1, zy1, zx2, zy2,
                outline="cyan", width=2, dash=(4, 2)
        )

    def _on_button_press(self,
                         event):
        # Remove retângulo anterior, se houver
        if self.rect_id:
            self.canvas.delete(self.rect_id)

        # Converte coords do clique para a escala original
        x = int((event.x - self.offset_x) / self.zoom_factor)
        y = int((event.y - self.offset_y) / self.zoom_factor)
        self.start_x = x
        self.start_y = y

        # Desenha retângulo inicial (aplicando zoom + offset)
        self.rect_id = self.canvas.create_rectangle(
                int(self.start_x * self.zoom_factor + self.offset_x),
                int(self.start_y * self.zoom_factor + self.offset_y),
                int(self.start_x * self.zoom_factor + self.offset_x),
                int(self.start_y * self.zoom_factor + self.offset_y),
                outline="red", width=2
        )

    def _on_mouse_drag(self,
                       event):
        # Converte coords atuais para a escala original
        cur_x = int((event.x - self.offset_x) / self.zoom_factor)
        cur_y = int((event.y - self.offset_y) / self.zoom_factor)

        # Atualiza retângulo no display (zoom + offset)
        self.canvas.coords(
                self.rect_id,
                int(self.start_x * self.zoom_factor + self.offset_x),
                int(self.start_y * self.zoom_factor + self.offset_y),
                int(cur_x * self.zoom_factor + self.offset_x),
                int(cur_y * self.zoom_factor + self.offset_y)
        )

    def _on_button_release(self,
                           event):
        # Converte coords finais para a escala original
        end_x = int((event.x - self.offset_x) / self.zoom_factor)
        end_y = int((event.y - self.offset_y) / self.zoom_factor)

        x1 = int(min(self.start_x, end_x))
        y1 = int(min(self.start_y, end_y))
        x2 = int(max(self.start_x, end_x))
        y2 = int(max(self.start_y, end_y))

        self.coords = (x1, y1, x2, y2)
        self.window.destroy()

    def _on_escape(self,
                   event):
        """
        Cancela seleção e fecha.
        """
        self.coords = None
        self.window.destroy()

    def show(self) -> Optional[RECT]:
        """
        Exibe a janela e aguarda até fechar. Retorna as coordenadas selecionadas
        (x1, y1, x2, y2) na escala original, ou None se ESC for pressionado.
        """
        self.window.grab_set()
        self.parent.wait_window(self.window)
        return self.coords


class WindowStream:
    """
    Utilitário para exibir um stream contínuo de capturas de tela de uma janela do Windows,
    usando a classe CaptureWindow para capturar frames e ImageWindow para exibição com zoom.

    Exemplo de uso:
        from cereja.window import Window as CaptureWindow
        from cereja.ui.window_stream import WindowStream

        # supondo que 'cw' seja uma instância de CaptureWindow
        stream = WindowStream(cw, interval=300, only_window_content=True)
        stream.start()
    """

    def __init__(
            self,
            capture_window: Window,
            interval: int = 500,
            only_window_content: bool = True
    ):
        """
        Args:
            capture_window (CaptureWindow):
                Instância de sua classe Window que contém capture_image_ppm.
            interval (int):
                Intervalo entre frames, em milissegundos.
            only_window_content (bool):
                Se True, captura apenas a área cliente da janela; se False, captura a janela inteira.
        """
        self.capture_window = capture_window
        self.interval = interval
        self.only_window_content = only_window_content

        # sinaliza ao thread de captura para parar
        self._stop_event = threading.Event()

        # referências a Tk e ao viewer (ImageWindow)
        self._viewer: Optional[ImageWindow] = None
        self._root: Optional[tk.Tk] = None

    def start(self):
        """
        Cria a janela de stream e inicia o thread de captura em background.
        O loop principal do Tkinter (mainloop) ficará rodando até o usuário fechar.
        """
        # 1) Cria um Tk oculto para ser pai do ImageWindow (main thread)
        self._root = tk.Tk()
        self._root.withdraw()

        # 2) Captura o primeiro frame em memória
        try:
            first_ppm = self.capture_window.capture_image_ppm(
                    ppm_path=None,
                    only_window_content=self.only_window_content
            )
        except Exception as e:
            self._root.destroy()
            raise RuntimeError(f"Falha ao capturar primeiro frame: {e}")

        # 3) Salva temporariamente o primeiro PPM só para abrir o ImageWindow
        fd, temp_path = tempfile.mkstemp(suffix=".ppm")
        os.close(fd)
        with open(temp_path, "wb") as f:
            f.write(first_ppm)

        # 4) Cria o ImageWindow UMA vez, exibindo o primeiro frame
        self._viewer = ImageWindow(self._root, image_path=temp_path,
                                   title=f"Stream: {self.capture_window.title}")
        # O PhotoImage já carregou o conteúdo em memória; podemos remover o arquivo
        try:
            os.remove(temp_path)
        except:
            pass

        # 5) Define protocolo de fechamento para o Toplevel
        #    Quando o usuário clicar no “X” ou pressionar ESC, _on_close() é chamado
        self._viewer.window.protocol("WM_DELETE_WINDOW", self._on_close)

        # 6) Inicia o thread de captura como daemon
        t = threading.Thread(target=self._capture_loop, daemon=True)
        t.start()

        # 7) Inicia o mainloop do Tkinter; bloqueia aqui até chamar root.quit()
        self._root.mainloop()

        # 8) Ao sair do mainloop (janela fechada), garante limpeza
        self._cleanup()

    def _capture_loop(self):
        """
        Executa em thread separado: captura cada frame e agenda
        a atualização da imagem no thread principal via after().
        """
        while not self._stop_event.is_set():
            try:
                ppm_bytes = self.capture_window.capture_image_ppm(
                        ppm_path=None,
                        only_window_content=self.only_window_content
                )
            except Exception:
                # falha ao capturar → sinaliza parada e agenda fechamento da janela
                self._stop_event.set()
                if self._viewer and self._viewer.window.winfo_exists():
                    # agenda fechamento para o thread principal
                    self._viewer.window.after(0, self._on_close)
                return
            if self._viewer.is_destroyed:
                # se a janela foi fechada, sinaliza parada e sai do loop
                self._stop_event.set()
                self._viewer.window.after(0, self._on_close)
                return

            def _update():
                # Este código roda no thread principal (via after). Verifica
                # se a janela ainda existe antes de chamar load_image_from_data.
                if not self._viewer or not self._viewer.window.winfo_exists():
                    return
                self._viewer.load_image_from_data(ppm_bytes)

            # agenda a atualização no thread principal
            if self._viewer:
                self._viewer.window.after(0, _update)

    def _on_close(self):
        """
        Chamado quando o usuário fecha o Toplevel de stream.
        Sinaliza o thread de captura para parar e interrompe o mainloop chamando root.quit().
        """
        self._stop_event.set()
        # destrói o Toplevel, se ainda existir
        if self._viewer and self._viewer.window.winfo_exists():
            try:
                self._viewer.window.destroy()
            except:
                pass
        # interrompe o mainloop para que start() retorne
        if self._root:
            try:
                self._root.quit()
            except:
                pass

    def _cleanup(self):
        """
        Garante que o stop_event esteja sinalizado e destrói o root, se necessário.
        """
        self._stop_event.set()
        if self._root:
            try:
                self._root.destroy()
            except:
                pass


class FileSelector:
    """
    Classe utilitária para abrir um diálogo de seleção de arquivo.
    Retorna o caminho do arquivo selecionado ou None se cancelado.
    """

    @staticmethod
    def select_file(parent: tk.Tk,
                    title: str = "Selecione um arquivo") -> Optional[str]:
        """
        Abre um diálogo para selecionar um arquivo e retorna o caminho selecionado.
        Se o usuário cancelar, retorna None.
        """
        file_path = filedialog.askopenfilename(parent=parent, title=title)
        if file_path:
            return file_path
        return None


# Type File
FILE = Union[str, bytes, os.PathLike]
# FieldName
FIELDNAME = str


@dataclass
class WindowCaptureConfig:
    """
    Configurações para captura de janela, definidas como dataclass.
    Cada atributo é uma tupla de quatro inteiros representando um retângulo
    (x1, y1, x2, y2) na tela.
    """
    image: FILE = None  # Caminho para imagem (opcional)
    name: FIELDNAME = ""  # Nome da janela a ser capturada
    window_rect: RECT = (0, 0, 800, 600)


class ConfigApp:
    def __init__(self,
                 img_path: str = None,
                 img_data: bytes = None,
                 default_config=None):
        # Inicializa a janela principal
        self.root = tk.Tk()
        self.root.title("Configurações do Sistema")
        self.root.minsize(650, 700)

        self._default_config = WindowCaptureConfig() if default_config is None else default_config
        self.img_path = img_path if img_path else self._default_config.image
        self.img_data = img_data
        # Dicionário para armazenar referências dos campos de entrada
        self.entries = {}

        # Instância de RegionSelector para reutilizar
        self.region_selector = RegionSelector(self.root)

        # Chama método para criar widgets na janela
        self._create_widgets()

    def _on_select_image(self,
                         entry_widget: tk.Entry):
        """
        Abre um diálogo para selecionar uma imagem e preenche o campo de entrada
        """
        file_path = FileSelector.select_file(self.root, title="Selecione uma imagem")
        if file_path:
            print("Arquivo selecionado:", file_path)
            # Se o usuário selecionou um arquivo, preenche a Entry com o caminho
            entry_widget.config(state="normal")
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, file_path)
            self.img_path = file_path
            entry_widget.config(state="readonly")  # Volta para readonly após inserir

    def _create_widgets(self):
        """
        Cria e posiciona os widgets (labels, entradas e botões de seleção)
        para cada atributo de WindowCaptureConfig. Cada botão de seleção
        carrega a região definida no campo e permite ajuste gráfico.
        """
        # Frame para conter todos os campos, com padding interno
        container = tk.Frame(self.root, padx=10, pady=10)
        container.pack(fill="both", expand=True)

        # Lista de campos da dataclass e seus valores padrão (usados como placeholders)
        config_fields = asdict(self._default_config).items()

        # Para cada campo, cria Label, Entry e botão "Selecionar"
        row_index = 0
        for field_name, default_value in config_fields:

            # Label do campo (em português para usuário entender)
            label = tk.Label(container, text=f"{field_name.replace('_', ' ').title()}:")
            label.grid(row=row_index, column=0, sticky="w", pady=5)

            # Entry onde o usuário poderá ver ou digitar o valor
            entry = tk.Entry(container, width=50)
            # responsive .. para que o texto não fique cortado
            entry.grid_propagate(False)

            if self._default_config.__annotations__[field_name] is FILE:
                # Se for o campo de imagem, preenche com o caminho da imagem
                entry.insert(0, self.img_path if self.img_path else "")
                entry.grid(row=row_index, column=1, pady=5, padx=5)
                # Botão para selecionar arquivo de imagem
                select_btn = tk.Button(
                        container,
                        text="Selecionar Imagem",
                        command=lambda e=entry: self._on_select_image(e)
                )
                select_btn.grid(row=row_index, column=2, pady=5, padx=5)
            elif self._default_config.__annotations__[field_name] is FIELDNAME:
                # Se for o campo de nome da janela, preenche com o valor padrão
                entry.insert(0, default_value)
                entry.grid(row=row_index, column=1, pady=5, padx=5)
                # Botão apenas para editar o nome da janela e ao sair do campo
                # desabilita a edição
                select_btn = tk.Button(
                        container,
                        text="Editar Nome",
                        command=lambda e=entry: e.config(state="normal"),
                )
                # Após clicar no botão, o usuário pode editar o campo
                # e depois clicar fora para desabilitar a edição
                entry.bind("<FocusOut>", lambda e, btn=select_btn: (
                    btn.config(text="Editar Nome"),
                    e.widget.config(state="readonly")
                ))
                select_btn.grid(row=row_index, column=2, pady=5, padx=5)
            else:
                # Exibe valor padrão no formato "int,int,int,int"
                entry.insert(0, ",".join(str(v) for v in default_value))
                entry.grid(row=row_index, column=1, pady=5, padx=5)

                # Botão de seleção de região para campos tipo RECT
                select_btn = tk.Button(
                        container,
                        text="Selecionar Região",
                        command=lambda fn=field_name,
                                       e=entry: self._on_select_region(fn, e)
                )
                select_btn.grid(row=row_index, column=2, pady=5, padx=5)
            entry.config(readonlybackground="#f0f0f0", state="readonly")
            # Armazena referência do widget de entrada
            self.entries[field_name] = entry

            row_index += 1

        # Botão para salvar as configurações
        save_button = tk.Button(
                container,
                text="Salvar Configurações",
                command=self._save_settings
        )
        save_button.grid(row=row_index, column=0, columnspan=3, pady=20)


    def _on_select_region(self,
                          field_name: str,
                          entry_widget: tk.Entry):
        """
        Chamado ao clicar em "Selecionar Região". Obtém o valor atual do campo,
        converte para tupla e passa como região inicial para o RegionSelector.
        Depois, preenche a Entry com as coordenadas ajustadas.
        """
        try:
            # Lê valores atuais do entry e converte para tupla
            current_text = entry_widget.get()
            initial_rect = self._parse_tuple(current_text)

            # Inicia seleção de região com o retângulo inicial carregado
            if self.img_path is not None or self.img_data is not None:
                new_rect = self.region_selector.select_region_from_image(
                        img=self.img_path if self.img_path else self.img_data,
                        initial_rect=initial_rect
                )
            else:
                new_rect = self.region_selector.select_region(initial_rect=initial_rect)
            if new_rect:
                # Se o campo estiver desabilitado, habilita, atualiza e desabilita novamente
                # Atualiza a Entry com o valor no formato "x1,y1,x2,y2"
                entry_widget.config(state="normal")
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, ",".join(str(v) for v in new_rect))
                entry_widget.config(state="readonly")
        except ValueError as e:
            messagebox.showerror("Erro de Validação", f"Valor atual inválido: {e}")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível selecionar a região: {e}")

    def _parse_tuple(self,
                     text: str) -> RECT:
        """
        Recebe uma string no formato "x1,x2,x3,x4" e retorna uma tupla de quatro ints.
        Caso não seja possível converter, levanta ValueError.
        """
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 4:
            raise ValueError("Devem ser quatro valores separados por vírgula.")
        try:
            nums = tuple(int(p) for p in parts)
        except ValueError:
            raise ValueError("Todos os valores devem ser números inteiros.")
        return nums  # type: ignore

    @classmethod
    def from_json(cls,
                  json_file: str) -> 'ConfigApp':
        """
        Lê um arquivo JSON com as configurações e cria uma instância de ConfigApp.
        O JSON deve conter os campos definidos na dataclass WindowCaptureConfig.
        """
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            config = WindowCaptureConfig(**config_data)
            return cls(default_config=config)
        except Exception as e:
            messagebox.showerror("Erro ao carregar configurações", str(e))
            return cls()

    def _save_settings(self):
        """
        Lê cada campo de entrada, converte para tupla de ints e cria
        uma instância de WindowCaptureConfig. Caso haja erro na conversão,
        exibe uma mensagem de erro. Se tudo der certo, salva em arquivo JSON
        e exibe confirmação.
        """
        kwargs = {}
        try:
            for field_name, entry_widget in self.entries.items():
                # Verifica se o campo é FILE (caminho de imagem)
                if self._default_config.__annotations__[field_name] is FILE:
                    # Se for FILE, pega o caminho da imagem
                    # salva imagem no mesmo diretório
                    text_value = os.path.abspath("capture_image.png")
                    self.region_selector.tk_image.write(
                            text_value, format="png"
                    )
                    kwargs[field_name] = text_value
                elif self._default_config.__annotations__[field_name] is FIELDNAME:
                    # Se for FIELDNAME, pega o texto do campo
                    text_value = entry_widget.get().strip()
                    if not text_value:
                        raise ValueError(f"O campo '{field_name}' não pode estar vazio.")
                    kwargs[field_name] = text_value
                else:
                    text_value = entry_widget.get()
                    tuple_value = self._parse_tuple(text_value)
                    kwargs[field_name] = tuple_value

            # Cria instância da dataclass com os valores coletados
            config = WindowCaptureConfig(**kwargs)

            # Converte para dicionário e salva em arquivo JSON
            config_dict = asdict(config)
            with open("window_capture_config.json", "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=4, ensure_ascii=False)

            # Exibe confirmação para o usuário
            messagebox.showinfo("Configurações", "Configurações salvas com sucesso!")
        except ValueError as e:
            # Se ocorrer erro de parsing, informa ao usuário
            messagebox.showerror("Erro de Validação", str(e))
        except Exception as e:
            # Qualquer outro erro inesperado
            messagebox.showerror("Erro", f"Ocorreu um erro ao salvar: {e}")

    def run(self):
        # Inicia o loop principal do Tkinter
        self.root.mainloop()