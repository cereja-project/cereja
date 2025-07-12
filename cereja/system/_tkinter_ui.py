import os
import time

from typing import Optional, Union, List, Dict
from cereja import Window, Path, FileIO
from cereja.config.cj_types import T_RECT, T_POINT
from cereja import hashtools
from cereja.system.action_runner import ActionRunner, Action

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, simpledialog
except ImportError:
    raise ImportError("Tkinter is required for this module. Please install it.")


def _get_hash_window_tittle(title: str) -> str:
    """
    Gera um hash simples para o título da janela.
    Remove espaços e caracteres especiais.
    """
    tittle = title.strip().lower()
    preprocessed_title = ''.join(c for c in tittle if c.isalnum() or c.isspace())
    preprocessed_title = preprocessed_title.replace(' ', '_')
    return f"{hashtools.md5(tittle)}_{preprocessed_title}"


class ListboxManager:
    def __init__(self,
                 parent,
                 config_key,
                 listbox,
                 operations):
        """
        Generic manager for listbox operations

        Args:
            parent: The parent widget that owns the listbox
            config_key: Key in the config dictionary for this list
            listbox: The Listbox widget
            operations: Dict with operations like 'add', 'view', 'test', 'remove'
        """
        self.parent = parent
        self.config_key = config_key
        self.listbox = listbox
        self.operations = operations

    def get_selected_item(self):
        """Get the currently selected item or show warning"""
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Faltando", f"Selecione um item primeiro.")
            return None, None
        idx = sel[0]
        item = self.parent.config.get(self.config_key, [])[idx]
        return idx, item

    def remove_item(self):
        """Remove selected item from the list"""
        idx, _ = self.get_selected_item() or (None, None)
        if idx is not None:
            self.parent.config.get(self.config_key, []).pop(idx)
            self.update_list()

    def update_list(self):
        """Update the listbox with current items"""
        self.listbox.delete(0, tk.END)
        formatter = self.operations.get('format_item', lambda i,
                                                              item: f"{i}: {item['name']}")

        for i, item in enumerate(self.parent.config.get(self.config_key, [])):
            self.listbox.insert(tk.END, formatter(i, item))


class ImagePointSelector:
    """
    Exibe apenas a região selecionada (crop) da janela usando Tkinter nativo.
    Permite ao usuário clicar em um ponto dentro dela.
    Retorna coordenadas absolutas (tela cliente).
    """

    def __init__(self,
                 root,
                 img_data: Union[str, bytes],
                 region: T_RECT):
        self.root = root
        self.img_data = img_data
        self.region = region
        self.point: Optional[T_POINT] = None

    def select(self) -> Optional[T_POINT]:
        raw = self.img_data.decode('latin1') if isinstance(self.img_data, (bytes, bytearray)) else self.img_data
        try:
            img = tk.PhotoImage(data=raw)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar imagem: {e}")
            return None

        x1, y1, x2, y2 = self.region
        width, height = x2 - x1, y2 - y1

        top = tk.Toplevel(self.root)
        top.title("Selecione Posição na Região")
        top.config(cursor="crosshair")
        top.attributes('-topmost', True)
        top.focus_force()

        canvas = tk.Canvas(top, width=width, height=height)
        canvas.pack(padx=10, pady=10)
        canvas.create_image(-x1, -y1, anchor='nw', image=img)
        canvas.image = img

        def on_click(event):
            abs_x = x1 + event.x
            abs_y = y1 + event.y
            self.point = (abs_x, abs_y)
            top.destroy()

        canvas.bind("<Button-1>", on_click)
        top.grab_set()
        self.root.wait_window(top)
        return self.point


class RegionSelector:
    def __init__(self,
                 root):
        self.root = root
        self.start_x = self.start_y = 0
        self.rect_id: Optional[int] = None
        self.coords: Optional[T_RECT] = None
        self.initial_rect: Optional[T_RECT] = None

    def select_region_from_image(self,
                                 img: Union[str, bytes],
                                 initial_rect: Optional[T_RECT] = None,
                                 crop_from_initial=False) -> Optional[T_RECT]:
        self.initial_rect = initial_rect
        raw = img.decode('latin1') if isinstance(img, (bytes, bytearray)) else img

        top = tk.Toplevel(self.root)
        top.title("Seleção de Região")
        top.config(cursor="crosshair")
        top.attributes('-topmost', True)
        top.focus_force()

        canvas = tk.Canvas(top)
        canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        try:
            photo = tk.PhotoImage(data=raw)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar imagem: {e}")
            top.destroy()
            return None

        if self.initial_rect:
            x1, y1, x2, y2 = self.initial_rect
            canvas.create_rectangle(x1, y1, x2, y2, outline='cyan', width=2, dash=(4, 2))
        if crop_from_initial and self.initial_rect:
            x1, y1, x2, y2 = self.initial_rect
            width, height = x2 - x1, y2 - y1
            canvas.config(width=width, height=height)
            canvas.create_image(-x1, -y1, anchor='nw', image=photo)
            canvas.image = photo
        else:
            canvas.config(width=photo.width(), height=photo.height())
            canvas.create_image(0, 0, anchor='nw', image=photo)
            canvas.image = photo

        def on_press(evt):
            if self.rect_id:
                canvas.delete(self.rect_id)
            self.start_x, self.start_y = canvas.canvasx(evt.x), canvas.canvasy(evt.y)
            self.rect_id = canvas.create_rectangle(
                    self.start_x, self.start_y, self.start_x, self.start_y,
                    outline='red', width=2
            )

        def on_drag(evt):
            cur_x, cur_y = canvas.canvasx(evt.x), canvas.canvasy(evt.y)
            canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

        def on_release(evt):
            ex, ey = canvas.canvasx(evt.x), canvas.canvasy(evt.y)
            x1_, y1_ = int(min(self.start_x, ex)), int(min(self.start_y, ey))
            x2_, y2_ = int(max(self.start_x, ex)), int(max(self.start_y, ey))
            # Ajusta coordenadas para a região inicial, se fornecida
            # if self.initial_rect:
            #     x1_ += initial_rect[0]
            #     y1_ += initial_rect[1]
            #     x2_ += initial_rect[0]
            #     y2_ += initial_rect[1]
            self.coords = (x1_, y1_, x2_, y2_)
            top.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        top.bind("<Escape>", lambda e: top.destroy())
        top.grab_set()
        self.root.wait_window(top)
        return self.coords


class ConfigDialog(tk.Toplevel):
    CONFIG_DIR = Path.user_home().join(".cereja_config")

    def __init__(self,
                 parent,
                 config: Dict,
                 on_save):
        super().__init__(parent)
        self.title("Configurar Cereja Bot")
        self.resizable(False, False)
        self.on_save = on_save
        self._file_path = None
        self.config = config or {}

        # Initialize default config lists
        for key in ["hotkeys", "click_positions", "actions", "snippets", "regions"]:
            self.config.setdefault(key, [])

        self._build_ui()
        self.grab_set()
        self.wait_window(self)

    def _build_ui(self):
        pad = {'padx': 10, 'pady': 5}
        self._build_window_selection(pad)
        self._build_region_selection(pad)

        # Create notebook for tabs
        notebook = ttk.Notebook(self)
        notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # Create tab managers
        self.managers = {
            'regions':   self._create_regions_tab(notebook),
            'positions': self._create_positions_tab(notebook),
            'hotkeys':   self._create_hotkeys_tab(notebook),
            'actions':   self._create_actions_tab(notebook),
            'snippets':  self._create_snippets_tab(notebook)
        }

        # Configure the main window to expand the notebook
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Save button
        ttk.Button(self, text="Salvar", command=self.save).grid(row=3, column=0, sticky="e", padx=10, pady=10)

        # Initialize all lists
        for manager in self.managers.values():
            manager.update_list()

    def _build_window_selection(self,
                                pad):
        frame_win = ttk.LabelFrame(self, text="Janela Alvo")
        frame_win.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        frame_win.columnconfigure(0, weight=1)
        ttk.Label(frame_win, text="Selecione a Janela:").grid(row=0, column=0, sticky="w")

        self.windows = Window.get_all_windows()
        opts = [f"{w.title.strip()}" for w in self.windows]
        self.win_combo = ttk.Combobox(frame_win, values=opts, state='readonly')
        self.win_combo.bind("<<ComboboxSelected>>", self._set_file_path_on_window_selected)
        self.win_combo.grid(row=1, column=0, sticky="ew", **pad)

        if "window_title" in self.config:
            for i, w in enumerate(self.windows):
                if w.title.strip() == self.config["window_title"].strip():
                    self.win_combo.current(i)
                    self.win_combo.set(f"{w.title.strip()}")
                    self.win_combo.config(state='disabled')
                    self._set_file_path_on_window_selected()
                    break

    def _build_region_selection(self,
                                pad):
        frame_reg = ttk.LabelFrame(self, text="Região do Jogo")
        frame_reg.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        frame_reg.columnconfigure(0, weight=1)
        self.region_var = tk.StringVar(value=str(self.config.get("region", "")))
        ttk.Label(frame_reg, textvariable=self.region_var).grid(row=0, column=0, sticky="w")
        ttk.Button(frame_reg, text="Selecionar Região", command=self.select_region).grid(row=0, column=1)

    def _create_tab_with_listbox(self,
                                 notebook,
                                 tab_name,
                                 height=6):
        """Create a standard tab with listbox and scrollbar"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text=tab_name)
        tab.columnconfigure(0, weight=1)

        # Create listbox with scrollbar
        listbox = tk.Listbox(tab, height=height)
        listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=5)
        listbox.configure(yscrollcommand=scrollbar.set)

        # Create button frame
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

        return tab, listbox, btn_frame

    def _create_regions_tab(self,
                            notebook):
        tab, listbox, btn_frame = self._create_tab_with_listbox(notebook, "Regiões")
        self.rects_listbox = listbox

        ttk.Button(btn_frame, text="Adicionar", command=self.add_rect_region).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Visualizar", command=self.view_rect_region).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Remover", command=self.remove_rect_region).pack(side="left", padx=5)

        def format_region(i,
                          item):
            return f"{i}: {item['name']} ({item['region']})"

        return ListboxManager(self, "regions", listbox, {
            'format_item': format_region,
        })

    def _create_positions_tab(self,
                              notebook):
        tab, listbox, btn_frame = self._create_tab_with_listbox(notebook, "Posições")
        self.pos_listbox = listbox

        ttk.Button(btn_frame, text="Adicionar", command=self.add_position).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Testar", command=self.test_position).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Remover", command=self.remove_position).pack(side="left", padx=5)

        return ListboxManager(self, "click_positions", listbox, {})

    def _create_hotkeys_tab(self,
                            notebook):
        tab, listbox, btn_frame = self._create_tab_with_listbox(notebook, "Hotkeys")
        self.hot_listbox = listbox

        ttk.Button(btn_frame, text="Adicionar", command=self.add_hotkey).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Testar", command=self.test_hotkey).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Remover", command=self.remove_hotkey).pack(side="left", padx=5)

        return ListboxManager(self, "hotkeys", listbox, {})

    def _create_actions_tab(self,
                            notebook):
        tab, listbox, btn_frame = self._create_tab_with_listbox(notebook, "Ações")
        self.act_listbox = listbox

        ttk.Button(btn_frame, text="Adicionar", command=self.add_action).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Testar", command=self.test_action).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Remover", command=self.remove_action).pack(side="left", padx=5)

        return ListboxManager(self, "actions", listbox, {})

    def _create_snippets_tab(self,
                             notebook):
        tab, listbox, btn_frame = self._create_tab_with_listbox(notebook, "Snippets")
        self.snip_listbox = listbox

        ttk.Button(btn_frame, text="Adicionar", command=self.add_snippet).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Visualizar", command=self.view_snippet).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Remover", command=self.remove_snippet).pack(side="left", padx=5)

        return ListboxManager(self, "snippets", listbox, {})

    # Refactor methods to use managers
    def add_rect_region(self):
        """Seleciona região em relação à região do jogo."""
        idx = self.win_combo.current()
        if idx < 0:
            messagebox.showwarning("Faltando", "Selecione uma janela alvo antes de adicionar região.")
            return
        window = self.windows[idx]
        try:
            ppm = window.capture_image_ppm()
        except Exception as e:
            messagebox.showerror("Erro ao capturar imagem", str(e))
            return
        selector = RegionSelector(self)
        region = selector.select_region_from_image(ppm, initial_rect=self.config.get("region"), crop_from_initial=True)
        if not region:
            return
        name = simpledialog.askstring("Nome da Região", "Digite um nome para a região:", parent=self)
        if not name:
            return
        self.config.setdefault("regions", []).append({"name": name, "region": region})
        self.managers['regions'].update_list()

    def view_rect_region(self):
        idx, reg = self.managers['regions'].get_selected_item() or (None, None)
        if not reg:
            return

        region = reg.get("region")
        if not region:
            messagebox.showerror("Erro", "Região não encontrada.")
            return
        x1, y1, x2, y2 = self.config.get("region", (0, 0, 0, 0))

        top = tk.Toplevel(self)
        top.title(f"Região: {reg['name']}")
        canvas = tk.Canvas(top, width=x2 - x1, height=y2 - y1)
        canvas.pack(padx=10, pady=10)
        try:
            ppm = self.windows[self.win_combo.current()].capture_image_ppm()
            img = tk.PhotoImage(data=ppm.decode('latin1'))
            canvas.create_image(-x1, -y1, anchor='nw', image=img)
            canvas.image = img
            # Desenha o retângulo da região
            x1, y1, x2, y2 = region
            # ajusta coordenadas para a região inicial, se fornecida
            canvas.create_rectangle(x1, y1, x2, y2, outline='cyan', width=2)
        except Exception as e:
            messagebox.showerror("Erro ao carregar imagem", str(e))

    def remove_rect_region(self):
        self.managers['regions'].remove_item()

    # Similar refactoring for other methods...

    def remove_position(self):
        self.managers['positions'].remove_item()

    def remove_hotkey(self):
        self.managers['hotkeys'].remove_item()

    def remove_action(self):
        self.managers['actions'].remove_item()

    def remove_snippet(self):
        self.managers['snippets'].remove_item()

    def _set_file_path_on_window_selected(self,
                                          event=None):
        print("Setting file path based on selected window...")
        idx = self.win_combo.current()
        if idx < 0:
            return
        window = self.windows[idx]
        try:
            window_title = window.title.strip()
            if not window_title:
                messagebox.showwarning("Faltando", "Selecione uma janela alvo.")
                return
            filename = _get_hash_window_tittle(window_title)
            self._file_path = self.CONFIG_DIR.join(filename).join(f"{filename}.json")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao obter título da janela: {e}")
            return

    def update_rects_list(self):
        self.rects_listbox.delete(0, tk.END)
        for idx, reg in enumerate(self.config.get("regions", [])):
            self.rects_listbox.insert(tk.END, f"{idx}: {reg['name']} ({reg['region']})")

    def update_positions_list(self):
        self.pos_listbox.delete(0, tk.END)
        for idx, pos in enumerate(self.config.get("click_positions", [])):
            self.pos_listbox.insert(tk.END, f"{idx}: {pos['name']}")

    def update_hotkeys_list(self):
        self.hot_listbox.delete(0, tk.END)
        for idx, hk in enumerate(self.config.get("hotkeys", [])):
            self.hot_listbox.insert(tk.END, f"{idx}: {hk['name']}")

    def update_actions_list(self):
        self.act_listbox.delete(0, tk.END)
        for idx, act in enumerate(self.config.get("actions", [])):
            self.act_listbox.insert(tk.END, f"{idx}: {act['name']}")

    def update_snippets_list(self):
        self.snip_listbox.delete(0, tk.END)
        for idx, sn in enumerate(self.config.get("snippets", [])):
            self.snip_listbox.insert(tk.END, f"{idx}: {sn['name']}")

    def view_snippet(self):
        sel = self.snip_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        sn = self.config.get("snippets", [])[idx]
        filename = sn.get("file")
        if not filename or not os.path.isfile(filename):
            messagebox.showerror("Erro", "Arquivo de snippet não encontrado.")
            return
        top = tk.Toplevel(self)
        top.title(sn["name"])
        try:
            img = tk.PhotoImage(file=filename)
        except Exception as e:
            messagebox.showerror("Erro ao abrir imagem", str(e))
            return
        lbl = ttk.Label(top, image=img)
        lbl.image = img
        lbl.pack(padx=10, pady=10)
        top.grab_set()

    def add_snippet(self):
        idx_win = self.win_combo.current()
        if idx_win < 0:
            messagebox.showwarning("Faltando", "Selecione uma janela antes de adicionar snippet.")
            return
        window = self.windows[idx_win]
        try:
            ppm = window.capture_image_ppm()
        except Exception as e:
            messagebox.showerror("Erro ao capturar imagem", str(e))
            return
        selector = RegionSelector(self)
        region = selector.select_region_from_image(ppm, initial_rect=self.config.get("region"), crop_from_initial=True)
        if not region:
            return
        name = simpledialog.askstring("Nome do Snippet", "Digite um nome para o snippet:", parent=self)
        if not name:
            return
        raw = ppm.decode('latin1')
        img = tk.PhotoImage(data=raw)
        x1, y1, x2, y2 = region
        initial_rect = self.config.get("region", (0, 0, 0, 0))
        if initial_rect:
            x1 += initial_rect[0]
            y1 += initial_rect[1]
            x2 += initial_rect[0]
            y2 += initial_rect[1]
        snippet = tk.PhotoImage()
        snippet.tk.call(snippet, 'copy', img, '-from', x1, y1, x2, y2, '-to', 0, 0)

        try:
            assert self._file_path, "File path must be set before saving snippet."
            self._file_path.parent.mkdir(force=True)
            filename = self._file_path.parent.join(f"{name}.png").path
            snippet.write(filename, format='png')
        except Exception as e:
            messagebox.showerror("Erro ao salvar snippet", str(e))
            return
        self.config.setdefault("snippets", []).append({"name": name, "region": region, "file": filename})
        self.update_snippets_list()

    def add_action(self):
        # Dialog to create an action using selections
        dlg = tk.Toplevel(self)
        dlg.title("Adicionar Ação")
        pad = {'padx': 10, 'pady': 5}
        dlg.columnconfigure(1, weight=1)

        ttk.Label(dlg, text="Nome:").grid(row=0, column=0, **pad)
        name_entry = ttk.Entry(dlg)
        name_entry.grid(row=0, column=1, sticky='ew', **pad)

        # Frame for instructions
        instructions_frame = ttk.LabelFrame(dlg, text="Instruções")
        instructions_frame.grid(row=2, column=0, columnspan=2, sticky='ew', **pad)

        instructions_list = []
        instructions_listbox = tk.Listbox(instructions_frame, height=5)
        instructions_listbox.pack(fill='x', padx=5, pady=5)

        # Frame for instruction buttons
        btn_frame = ttk.Frame(instructions_frame)
        btn_frame.pack(fill='x')

        def add_instruction():
            instruction_dlg = tk.Toplevel(dlg)
            instruction_dlg.title("Adicionar Instrução")
            instruction_dlg.grab_set()

            types = ['move', 'click', 'hotkey', 'wait']
            ttk.Label(instruction_dlg, text="Tipo:").grid(row=0, column=0, **pad)
            type_cb = ttk.Combobox(instruction_dlg, values=types, state='readonly')
            type_cb.grid(row=0, column=1, sticky='ew', **pad)

            # Frames for different instruction types
            frame_move = ttk.Frame(instruction_dlg)
            frame_click = ttk.Frame(instruction_dlg)
            frame_hot = ttk.Frame(instruction_dlg)
            frame_wait = ttk.Frame(instruction_dlg)

            # Setup move frame
            pos_names = [p['name'] for p in self.config.get('click_positions', [])]
            ttk.Label(frame_move, text="Origem:").grid(row=0, column=0, **pad)
            ori_cb = ttk.Combobox(frame_move, values=pos_names, state='readonly')
            ori_cb.grid(row=0, column=1, **pad)
            ttk.Label(frame_move, text="Destino:").grid(row=1, column=0, **pad)
            dest_cb = ttk.Combobox(frame_move, values=pos_names, state='readonly')
            dest_cb.grid(row=1, column=1, **pad)

            # Setup click frame
            ttk.Label(frame_click, text="Posição:").grid(row=0, column=0, **pad)
            click_cb = ttk.Combobox(frame_click, values=pos_names, state='readonly')
            click_cb.grid(row=0, column=1, **pad)
            ttk.Label(frame_click, text="Botão:").grid(row=1, column=0, **pad)
            btn_cb = ttk.Combobox(frame_click, values=['left', 'right'], state='readonly')
            btn_cb.set('left')
            btn_cb.grid(row=1, column=1, **pad)

            # Setup hotkey frame
            hk_names = [h['name'] for h in self.config.get('hotkeys', [])]
            ttk.Label(frame_hot, text="Hotkey:").grid(row=0, column=0, **pad)
            hk_cb = ttk.Combobox(frame_hot, values=hk_names, state='readonly')
            hk_cb.grid(row=0, column=1, **pad)

            # Setup wait frame
            ttk.Label(frame_wait, text="Tempo (s):").grid(row=0, column=0, **pad)
            wait_entry = ttk.Entry(frame_wait)
            wait_entry.insert(0, "1.0")
            wait_entry.grid(row=0, column=1, **pad)

            current_frame = None

            def show_params(event):
                nonlocal current_frame
                if current_frame:
                    current_frame.grid_forget()

                type_val = type_cb.get()
                if type_val == 'move':
                    frame_move.grid(row=2, column=0, columnspan=2, sticky='ew', **pad)
                    current_frame = frame_move
                elif type_val == 'click':
                    frame_click.grid(row=2, column=0, columnspan=2, sticky='ew', **pad)
                    current_frame = frame_click
                elif type_val == 'hotkey':
                    frame_hot.grid(row=2, column=0, columnspan=2, sticky='ew', **pad)
                    current_frame = frame_hot
                elif type_val == 'wait':
                    frame_wait.grid(row=2, column=0, columnspan=2, sticky='ew', **pad)
                    current_frame = frame_wait

            type_cb.bind('<<ComboboxSelected>>', show_params)

            confirm_btn_frame = ttk.Frame(instruction_dlg)
            confirm_btn_frame.grid(row=3, column=0, columnspan=2, sticky='ew', **pad)

            def confirm_instruction():
                try:
                    type_val = type_cb.get()
                    param = None

                    if type_val == 'move':
                        if ori_cb.current() < 0 or dest_cb.current() < 0:
                            messagebox.showerror("Erro", "Selecione origem e destino")
                            return
                        param = (ori_cb.current(), dest_cb.current())

                    elif type_val == 'click':
                        if click_cb.current() < 0:
                            messagebox.showerror("Erro", "Selecione uma posição")
                            return
                        param = (click_cb.current(), btn_cb.get())

                    elif type_val == 'hotkey':
                        if hk_cb.current() < 0:
                            messagebox.showerror("Erro", "Selecione uma hotkey")
                            return
                        param = hk_cb.current()

                    elif type_val == 'wait':
                        try:
                            param = float(wait_entry.get())
                            if param <= 0:
                                raise ValueError()
                        except ValueError:
                            messagebox.showerror("Erro", "Tempo de espera deve ser positivo")
                            return
                    instruction = {'type': type_val, 'param': param}
                    instructions_list.append(instruction)

                    # Show in listbox with a descriptive name
                    if type_val == 'move':
                        pos_names = [p['name'] for p in self.config.get('click_positions', [])]
                        desc = f"Move: {pos_names[param[0]]} -> {pos_names[param[1]]}"
                    elif type_val == 'click':
                        pos_names = [p['name'] for p in self.config.get('click_positions', [])]
                        desc = f"Click {param[1]} em: {pos_names[param[0]]}"
                    elif type_val == 'hotkey':
                        hk_names = [h['name'] for h in self.config.get('hotkeys', [])]
                        desc = f"Hotkey: {hk_names[param]}"
                    elif type_val == 'wait':
                        desc = f"Espera: {param}s"
                    instruction_dlg.destroy()

                    instructions_listbox.insert(tk.END, desc)

                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao adicionar instrução: {str(e)}")

            ttk.Button(confirm_btn_frame, text="Confirmar", command=confirm_instruction).pack(side='left', padx=5)
            ttk.Button(confirm_btn_frame, text="Cancelar", command=instruction_dlg.destroy).pack(side='left', padx=5)

        def remove_instruction():
            sel = instructions_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            instructions_list.pop(idx)
            instructions_listbox.delete(idx)

        def move_up():
            sel = instructions_listbox.curselection()
            if not sel or sel[0] == 0:
                return
            idx = sel[0]
            instructions_list[idx], instructions_list[idx - 1] = instructions_list[idx - 1], instructions_list[idx]
            item = instructions_listbox.get(idx)
            instructions_listbox.delete(idx)
            instructions_listbox.insert(idx - 1, item)
            instructions_listbox.selection_set(idx - 1)

        def move_down():
            sel = instructions_listbox.curselection()
            if not sel or sel[0] == len(instructions_list) - 1:
                return
            idx = sel[0]
            instructions_list[idx], instructions_list[idx + 1] = instructions_list[idx + 1], instructions_list[idx]
            item = instructions_listbox.get(idx)
            instructions_listbox.delete(idx)
            instructions_listbox.insert(idx + 1, item)
            instructions_listbox.selection_set(idx + 1)

        ttk.Button(btn_frame, text="Adicionar", command=add_instruction).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Remover", command=remove_instruction).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Mover ↑", command=move_up).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Mover ↓", command=move_down).pack(side='left', padx=5)

        # Final confirmation buttons
        final_btn_frame = ttk.Frame(dlg)
        final_btn_frame.grid(row=3, column=0, columnspan=2, **pad)

        def confirm_action():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Erro", "Nome é obrigatório.")
                return
            interval = 0.5
            try:
                interval = float(interval)
                if interval <= 0:
                    raise ValueError("Intervalo deve ser positivo.")
            except ValueError as e:
                messagebox.showerror("Erro", str(e))
                return
            action = {
                'name':         name,
                'interval':     interval,
                'instructions': instructions_list,
                'enabled':      False
            }
            self.config["actions"].append(action)
            self.update_actions_list()
            dlg.destroy()

        ttk.Button(final_btn_frame, text="Confirmar", command=confirm_action).pack(side='left', padx=5)
        ttk.Button(final_btn_frame, text="Cancelar", command=dlg.destroy).pack(side='left', padx=5)
        dlg.grab_set()
        dlg.focus_force()

    def test_action(self):
        sel = self.act_listbox.curselection()
        if not sel:
            return
        act = self.config.get("actions", [])[sel[0]]
        idx = self.win_combo.current()
        if idx < 0:
            messagebox.showwarning("Faltando", "Selecione uma janela antes de testar ação.")
            return
        window = self.windows[idx]

        try:
            action = Action(**{**act, "enabled": True})
            for inst in action._instructions:
                if inst.type == 'wait':
                    time.sleep(inst.param)
                    continue
                inst.execute(window, self.config.get("click_positions", []), self.config.get("hotkeys", []))
        except Exception as e:
            messagebox.showerror("Erro ao testar ação", str(e))

    def add_hotkey(self):
        # Pergunta o nome da hotkey
        name = simpledialog.askstring("Nome da Hotkey", "Digite um nome para a hotkey:", parent=self)
        if not name:
            return
        # Janela de captura de combinação
        combo: List[str] = []
        top = tk.Toplevel(self)
        top.title(f"Capturando Hotkey: {name}")
        ttk.Label(top, text="Pressione as teclas desejadas:").pack(padx=10, pady=5)
        lbl = ttk.Label(top, text="");
        lbl.pack(padx=10, pady=(0, 5))
        # Botões Limpar e Confirmar
        btn_frame = ttk.Frame(top);
        btn_frame.pack(pady=5)

        def clear_combo():
            combo.clear()
            lbl.config(text="")

        def confirm_combo():
            top.destroy()
            combo_str = '+'.join(combo)
            if combo_str:
                self.config.setdefault("hotkeys", []).append({"name": name, "combo": combo_str})
                self.update_hotkeys_list()

        ttk.Button(btn_frame, text="Limpar", command=clear_combo).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Confirmar", command=confirm_combo).pack(side="left", padx=5)

        # Captura de teclas
        def on_key(event):
            key = event.keysym
            if key not in combo and key != 'Return':
                combo.append(key)
                lbl.config(text='+'.join(combo))

        top.bind("<Key>", on_key)
        top.grab_set()
        top.focus_force()
        self.wait_window(top)

    def test_hotkey(self):
        sel = self.hot_listbox.curselection()
        if not sel:
            return
        hk = self.config.get("hotkeys", [])[sel[0]]
        combo = hk["combo"]
        idx = self.win_combo.current()
        if idx < 0:
            messagebox.showwarning("Faltando", "Selecione uma janela antes de testar hotkey.")
            return
        window = self.windows[idx]
        try:
            window.keyboard.press_and_release(combo)
        except Exception as e:
            messagebox.showerror("Erro ao testar hotkey", str(e))

    def add_position(self):
        idx = self.win_combo.current()
        if idx < 0:
            messagebox.showwarning("Faltando", "Selecione uma janela alvo antes de adicionar posição.")
            return
        window = self.windows[idx]
        # captura imagem da janela e recorta apenas a região configurada
        ppm = window.capture_image_ppm()
        region = self.config.get("region")
        if not region:
            messagebox.showwarning("Faltando", "Defina a região antes de adicionar posição.")
            return
        selector = ImagePointSelector(self, ppm, region)
        pt = selector.select()
        pt = self._adjust_coordinates(pt[0], pt[1], window) if pt else None
        if not pt:
            return
        name = simpledialog.askstring("Nome da Posição", "Digite um nome para essa posição:", parent=self)
        if not name:
            messagebox.showwarning("Faltando", "Nome é obrigatório.")
            return
        pos_list = self.config.setdefault("click_positions", [])
        pos_list.append({"name": name, "point": pt})
        self.update_positions_list()

    def test_position(self):
        sel = self.pos_listbox.curselection()
        if not sel:
            messagebox.showwarning("Faltando", "Selecione uma posição para testar.")
            return
        pos = self.config.get("click_positions", [])[sel[0]]
        pt = pos["point"]
        window = self.windows[self.win_combo.current()]
        try:
            # show window in front
            window.bring_to_top()
            time.sleep(0.1)  # wait for window to come to front
            window.mouse.click_left(pt)
            # traz janela de configuração para frente
            self.lift()
        except Exception as e:
            messagebox.showerror("Erro ao testar clique", str(e))

    def _adjust_coordinates(self,
                            x: int,
                            y: int,
                            window: Window) -> tuple:
        """Adjust coordinates based on the game window's position."""

        target_width, target_height = window.size_window_content
        x1, y1, x2, y2 = self.config.get("region", (0, 0, 0, 0))
        origin_width = x2 - x1
        origin_height = y2 - y1
        # proportionally adjust coordinates
        adjusted_x = int(x * (target_width / origin_width))
        adjusted_y = int(y * (target_height / origin_height))
        return adjusted_x, adjusted_y

    def select_region(self):
        idx = self.win_combo.current()
        if idx < 0:
            messagebox.showwarning("Faltando", "Selecione uma janela alvo primeiro.")
            return
        window = self.windows[idx]
        try:
            ppm = window.capture_image_ppm()
        except Exception as e:
            messagebox.showerror("Erro ao capturar imagem", str(e))
            return
        region = RegionSelector(self).select_region_from_image(ppm, initial_rect=self.config.get("region"))
        if region:
            self.config.update({"window_title": window.title.strip(), "region": region})
            self.region_var.set(str(region))

    def save(self):
        if "window_title" not in self.config or "region" not in self.config:
            messagebox.showwarning("Faltando", "Configure janela e região antes de salvar.")
            return
        try:
            assert self._file_path is not None, "File path must be set before saving."
            self._file_path.parent.mkdir(force=True)
            FileIO.create(self._file_path, self.config, ensure_ascii=False, indent=True).save(
                    exist_ok=True
            )

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar configuração: {e}")
            return
        messagebox.showinfo("Salvo", "Configurações salvas com sucesso.")
        self.on_save(self.config, self._file_path)
        self.destroy()


class AutomatorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cereja Bot")
        self.geometry("600x500")
        self.config_filepath = None

        # runner ainda não existe
        self.runner: Optional[ActionRunner] = None

        self.config_data = self.load_config()
        if not self.config_data:
            ConfigDialog(self, self.config_data or {}, on_save=self.on_config_saved)
        self.deiconify()

        self.create_menu()
        self.runner = None  # Inicializa runner como None
        self.build_ui()

        # Bind WM_DELETE_WINDOW protocol to handle application closing
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Ask for confirmation before closing the application"""
        if messagebox.askokcancel("Sair", "Deseja realmente sair?\nAs automações serão interrompidas."):
            if self.runner:
                self.runner.stop()
            self.destroy()

    def load_config(self) -> Optional[Dict]:
        all_file_names = set(ConfigDialog.CONFIG_DIR.list_dir("**/*.json", only_name=True))
        config_files = []
        for window in Window.get_all_windows():
            filename = _get_hash_window_tittle(window.title.strip())
            if filename not in all_file_names:
                continue
            config_files.append(ConfigDialog.CONFIG_DIR.join(f"{filename}/{filename}.json"))
        if not config_files:
            messagebox.showwarning("Configuração não encontrada", "Nenhuma configuração válida encontrada.")
            return None
        # se existir mais de um arquivo, pergunta qual usar
        if len(config_files) >= 1:

            selected = filedialog.askopenfilename(
                    title="Selecione a configuração",
                    initialdir=str(ConfigDialog.CONFIG_DIR),
                    filetypes=[("JSON Files", "*.json")],
                    initialfile=config_files[0].name
            )
            if not selected:
                return None
            config_path = Path(selected)
        else:
            config_path = config_files[0]

        try:
            config_data = FileIO.load(config_path, ensure_ascii=False).data
            self.config_filepath = config_path
            if not isinstance(config_data, dict):
                raise ValueError("Configuração inválida. Deve ser um dicionário.")
            return config_data
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar configuração: {e}")
        return None

    def save_config(self):
        if not self.config_data:
            return
        try:
            FileIO.create(self.config_filepath, self.config_data, ensure_ascii=False, indent=True).save(
                    exist_ok=True
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar configuração: {e}")

    def create_menu(self):
        menubar = tk.Menu(self)
        settings = tk.Menu(menubar, tearoff=0)
        settings.add_command(label="Configurar...",
                             command=lambda: ConfigDialog(self, self.config_data, on_save=self.on_config_saved))
        settings.add_separator()
        settings.add_command(label="Sair", command=self.quit)
        menubar.add_cascade(label="Configurações", menu=settings)
        self.config(menu=menubar)

    def on_config_saved(self,
                        config=None,
                        filepath: Optional[Path] = None):
        self.config_data = config
        self.config_filepath = filepath
        self.build_ui()

    def build_ui(self):
        # Limpa UI
        for w in self.winfo_children():
            if not isinstance(w, tk.Menu):
                w.destroy()

        # Título e botão configurar
        frame_title = ttk.Frame(self, padding=10)
        frame_title.pack(fill="x")
        title = self.config_data.get("window_title", "Nenhuma selecionada")
        ttk.Label(frame_title, text=f"Título da Janela: {title}").pack(side="left")
        ttk.Button(frame_title, text="Configurar...",
                   command=lambda: ConfigDialog(self, self.config_data, on_save=self.on_config_saved)).pack(
                side="right")

        # Seção de ações configuradas
        action_frame = ttk.LabelFrame(self, text="Ações Configuradas", padding=10)
        action_frame.pack(fill="x", padx=10, pady=10)
        self.action_vars: List[tk.BooleanVar] = []
        for idx, act in enumerate(self.config_data.get("actions", [])):
            var = tk.BooleanVar(value=act.get("enabled", True))
            cb = ttk.Checkbutton(
                    action_frame,
                    text=f"{act['name']}",
                    variable=var,
                    command=lambda i=idx,
                                   v=var: self.toggle_action(i, v)
            )
            cb.pack(anchor="w", pady=2)
            self.action_vars.append(var)
        self.setup_runner()

    def setup_runner(self):
        # sempre chame stop antes de reiniciar
        if self.runner:
            self.runner.stop()

        # encontra a janela correspondente ao título
        window = next((
            w for w in Window.get_all_windows()
            if w.title.strip() == self.config_data["window_title"].strip()
        ), None)
        if not window:
            messagebox.showwarning("Aviso", "Janela alvo não encontrada para rodar ações.")
            return

        # cria lista de objetos Action (mesmo desabilitados)
        actions = [
            Action(**a)
            for a in self.config_data.get("actions", [])
        ]

        positions = self.config_data.get("click_positions", [])
        hotkeys = self.config_data.get("hotkeys", [])

        # instancia e inicia
        self.runner = ActionRunner(actions, window, positions, hotkeys)
        self.runner.start()

    def toggle_action(self,
                      idx: int,
                      var: tk.BooleanVar):
        enabled = var.get()
        self.config_data["actions"][idx]["enabled"] = enabled
        self.runner.actions[idx].enabled = enabled
        self.save_config()


if __name__ == "__main__":
    app = AutomatorGUI()
    app.mainloop()
