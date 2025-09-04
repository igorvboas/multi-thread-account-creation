import csv
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Dict, Any, List
import undetected_chromedriver as uc

CSV_PATH = Path("./src/data/accounts_created.csv")

def read_csv_rows(csv_path: Path) -> List[Dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV não encontrado em {csv_path.resolve()}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]

def build_label(row: Dict[str, Any]) -> str:
    parts = []
    for key in ("username", "email", "full_name"):
        v = (row.get(key) or "").strip()
        if v:
            parts.append(v)
    ph, pp = (row.get("proxy_host") or "").strip(), (row.get("proxy_port") or "").strip()
    if ph and pp:
        parts.append(f"proxy: {ph}:{pp}")
    ua = (row.get("user_agent") or "").strip()
    if ua:
        short = ua[:45] + ("..." if len(ua) > 45 else "")
        parts.append(f"UA: {short}")
    return " — ".join(parts) if parts else "Linha sem identificadores"

def make_chrome_options(row: Dict[str, Any]) -> uc.ChromeOptions:
    opts = uc.ChromeOptions()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    lang = (row.get("lang") or "").strip()
    if lang:
        opts.add_argument(f"--lang={lang}")
    ws = (row.get("window_size") or "").strip()
    if ws and "," in ws:
        opts.add_argument(f"--window-size={ws}")
    ua = (row.get("user_agent") or "").strip()
    if ua:
        opts.add_argument(f"--user-agent={ua}")
    ext_dir = (row.get("extension_dir") or "").strip()
    if ext_dir:
        for ext in [p.strip() for p in ext_dir.split(",") if p.strip()]:
            if Path(ext).exists():
                opts.add_argument(f"--load-extension={ext}")
    user_data_dir = (row.get("user_data_dir") or "").strip()
    profile_name = (row.get("profile_name") or "").strip()
    if user_data_dir:
        udd = Path(user_data_dir); udd.mkdir(parents=True, exist_ok=True)
        opts.add_argument(f"--user-data-dir={str(udd.resolve())}")
        if profile_name:
            opts.add_argument(f"--profile-directory={profile_name}")
    ph, pp = (row.get("proxy_host") or "").strip(), (row.get("proxy_port") or "").strip()
    pu, pw = (row.get("proxy_user") or "").strip(), (row.get("proxy_pass") or "").strip()
    if ph and pp:
        if pu and pw:
            opts.add_argument(f"--proxy-server=http://{pu}:{pw}@{ph}:{pp}")
        else:
            opts.add_argument(f"--proxy-server=http://{ph}:{pp}")
    return opts

def open_browser(row: Dict[str, Any]) -> None:
    try:
        options = make_chrome_options(row)
        driver = uc.Chrome(options=options, headless=False, use_subprocess=True)
        driver.set_page_load_timeout(120)
        driver.get("https://www.google.com/")
        global _drivers; _drivers.append(driver)
    except Exception as e:
        messagebox.showerror("Erro ao abrir navegador", str(e))

_drivers: List[Any] = []

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Launcher de Contas - Modo Discreto (uc)")
        self.geometry("900x500")
        self.rows: List[Dict[str, Any]] = []
        self.labels: List[str] = []
        self._build_ui()
        self._load_csv_async()
        # atualiza detalhes quando usuário muda a seleção
        self.combo.bind('<<ComboboxSelected>>', lambda e: self._render_details())

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12); frm.pack(fill=tk.BOTH, expand=True)
        top = ttk.Frame(frm); top.pack(fill=tk.X, pady=(0,8))
        self.csv_label_var = tk.StringVar(value=f"CSV: {CSV_PATH}")
        ttk.Label(top, textvariable=self.csv_label_var).pack(side=tk.LEFT)
        ttk.Button(top, text="Recarregar CSV", command=self._load_csv_async).pack(side=tk.RIGHT)
        mid = ttk.Frame(frm); mid.pack(fill=tk.X, pady=8)
        ttk.Label(mid, text="Selecione a conta/configuração:").pack(anchor="w")
        self.combo_var = tk.StringVar(value="(carregando...)")
        self.combo = ttk.Combobox(mid, textvariable=self.combo_var, state="readonly", width=110)
        self.combo.pack(fill=tk.X, pady=4)
        actions = ttk.Frame(frm); actions.pack(fill=tk.X, pady=(8,0))
        self.btn_open = ttk.Button(actions, text="Abrir Navegador", command=self._on_open_clicked, state=tk.DISABLED)
        self.btn_open.pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Status: pronto")
        ttk.Label(frm, textvariable=self.status_var).pack(anchor="w", pady=(12,0))
        # Text widget for details
        ttk.Label(frm, text="Detalhes do item selecionado:").pack(anchor="w", pady=(8,0))
        self.text_details = tk.Text(frm, height=12, wrap="word")
        self.text_details.pack(fill=tk.BOTH, expand=True, pady=(4,0))

    def _load_csv_async(self):
        def work():
            try:
                rows = read_csv_rows(CSV_PATH)
                labels = [build_label(r) for r in rows]
                if not labels:
                    raise ValueError("Nenhuma linha válida encontrada no CSV.")
                self.rows, self.labels = rows, labels
                self.after(0, self._on_csv_loaded_success)
            except Exception as e:
                self.after(0, lambda: self._on_csv_loaded_error(e))
        threading.Thread(target=work, daemon=True).start()


    def _render_details(self):
        idx = self.combo.current()
        if idx < 0 or idx >= len(self.rows):
            self.details.configure(state='normal')
            self.details.delete('1.0', tk.END)
            self.details.insert(tk.END, '(nenhum item selecionado)')
            self.details.configure(state='disabled')
            self.btn_copy.config(state=tk.DISABLED)
            return
        row = self.rows[idx]
        # Montar texto com todas as chaves ordenadas
        lines = []
        for k in sorted(row.keys()):
            v = str(row.get(k, '') or '')
            lines.append(f"{k}: {v}")
        text = "\n".join(lines)
        # Atualiza Text
        self.details.configure(state='normal')
        self.details.delete('1.0', tk.END)
        self.details.insert(tk.END, text)
        self.details.configure(state='normal')  # deixamos editável para facilitar selecionar/copiar
        self.btn_copy.config(state=tk.NORMAL)

    def _copy_details(self):
        try:
            content = self.details.get('1.0', tk.END).strip()
            self.clipboard_clear()
            self.clipboard_append(content)
            self.status_var.set('Dados copiados para a área de transferência.')
        except Exception as e:
            messagebox.showerror('Erro ao copiar', str(e))

    def _on_csv_loaded_success(self):
        self.combo['values'] = self.labels
        if self.labels:
            self.combo.current(0)
            self.btn_open.config(state=tk.NORMAL)
            self._update_details(0)
        self.combo.bind("<<ComboboxSelected>>", self._on_selection_changed)
        self.status_var.set(f"Status: {len(self.labels)} itens carregados do CSV.")

    def _on_csv_loaded_error(self, e: Exception):
        self.combo['values'] = ["(erro ao carregar CSV)"]
        self.combo.current(0)
        self.btn_open.config(state=tk.DISABLED)
        self.status_var.set(f"Erro: {e}")
        messagebox.showerror("Erro no CSV", str(e))

    def _on_selection_changed(self, event=None):
        idx = self.combo.current()
        if 0 <= idx < len(self.rows):
            self._update_details(idx)

    def _update_details(self, idx: int):
        row = self.rows[idx]
        text = "\n".join([f"{k}: {v}" for k,v in row.items()])
        self.text_details.delete("1.0", tk.END)
        self.text_details.insert(tk.END, text)

    def _on_open_clicked(self):
        idx = self.combo.current()
        if idx < 0 or idx >= len(self.rows):
            messagebox.showwarning("Seleção inválida", "Selecione um item válido do dropdown.")
            return
        row = self.rows[idx]
        def work():
            self.status_var.set("Abrindo navegador...")
            try:
                open_browser(row)
                self.status_var.set("Navegador aberto com sucesso.")
            except Exception as e:
                self.status_var.set("Falha ao abrir navegador.")
                messagebox.showerror("Erro", str(e))
        threading.Thread(target=work, daemon=True).start()

if __name__ == "__main__":
    App().mainloop()
