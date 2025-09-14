import os
import sys
import json
import glob
import platform
import subprocess
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

FASTFLAGS_FILE = os.path.join("Modifications", "ClientSettings", "ClientAppSettings.json")
BOOTSTRAPPER_URL = "https://setup.pekora.zip/PekoraPlayerLauncher.exe"
BOOTSTRAPPER_FILE = "PekoraPlayerLauncher.exe"

def get_system_info():
    system = platform.system().lower()
    return {
        'is_windows': system == 'windows',
        'is_linux': system == 'linux',
        'is_macos': system == 'darwin',
        'system_name': system
    }

def get_version_roots():
    sys_info = get_system_info()
    roots = []
    if sys_info['is_windows']:
        roots.extend([
            os.path.expandvars(r"%localappdata%\ProjectX\Versions"),
            os.path.expandvars(r"%localappdata%\Pekora\Versions"),
        ])
    elif sys_info['is_linux']:
        user = os.getenv('USER', 'user')
        roots.extend([
            os.path.expanduser(f"~/.wine/drive_c/users/{user}/AppData/Local/ProjectX/Versions"),
            os.path.expanduser(f"~/.wine/drive_c/users/{user}/AppData/Local/Pekora/Versions"),
            os.path.expanduser(f"~/.local/share/wineprefixes/pekora/drive_c/users/{user}/AppData/Local/Pekora/Versions"),
            os.path.expanduser(f"~/.local/share/wineprefixes/projectx/drive_c/users/{user}/AppData/Local/ProjectX/Versions"),
        ])
    elif sys_info['is_macos']:
        user = os.getenv('USER', 'user')
        roots.extend([
            os.path.expanduser(f"~/.wine/drive_c/users/{user}/AppData/Local/ProjectX/Versions"),
            os.path.expanduser(f"~/.wine/drive_c/users/{user}/AppData/Local/Pekora/Versions"),
        ])
        roots.extend(glob.glob(os.path.expanduser(f"~/Library/Application Support/CrossOver/Bottles/*/drive_c/users/{user}/AppData/Local/ProjectX/Versions")))
        roots.extend(glob.glob(os.path.expanduser(f"~/Library/Application Support/CrossOver/Bottles/*/drive_c/users/{user}/AppData/Local/Pekora/Versions")))
    return [p for p in roots if isinstance(p, str)]

def iter_version_dirs():
    for root in get_version_roots():
        if os.path.isdir(root):
            for d in sorted(glob.glob(os.path.join(root, "*"))):
                if os.path.isdir(d):
                    yield d

def get_clientsettings_targets():
    targets = []
    for ver in iter_version_dirs():
        for folder in ["2020L", "2021M"]:
            folder_path = os.path.join(ver, folder)
            if os.path.isdir(folder_path):
                client_dir = os.path.join(folder_path, "ClientSettings")
                settings_path = os.path.join(client_dir, "ClientAppSettings.json")
                targets.append((client_dir, settings_path, folder))
    return targets

def get_executable_paths(folder):
    paths = []
    for ver in iter_version_dirs():
        exe = os.path.join(ver, folder, "ProjectXPlayerBeta.exe")
        paths.append(exe)
    return paths

def auto_detect_value_type(value_str):
    value_str = value_str.strip()
    if value_str.lower() in ['true', 'false']:
        return value_str.lower() == 'true'
    try:
        if '.' not in value_str and 'e' not in value_str.lower():
            return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        pass
    return value_str

def load_fastflags_local():
    if not os.path.exists(FASTFLAGS_FILE):
        os.makedirs(os.path.dirname(FASTFLAGS_FILE), exist_ok=True)
        with open(FASTFLAGS_FILE, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(FASTFLAGS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_fastflags_local(fastflags):
    try:
        os.makedirs(os.path.dirname(FASTFLAGS_FILE), exist_ok=True)
        with open(FASTFLAGS_FILE, "w") as f:
            json.dump(fastflags, f, indent=2)
        return True
    except Exception:
        return False

def apply_fastflags_to_clients(fastflags):
    applied = []
    failed = []
    for client_dir, settings_path, folder in get_clientsettings_targets():
        try:
            os.makedirs(client_dir, exist_ok=True)
            if os.path.exists(settings_path):
                try:
                    os.replace(settings_path, settings_path + ".bak")
                except Exception:
                    pass
            with open(settings_path, "w") as f:
                json.dump(fastflags, f, indent=2)
            applied.append(settings_path)
        except Exception:
            failed.append((settings_path, folder))
    return applied, failed

def launch_executable(path):
    sys_info = get_system_info()
    try:
        if sys_info['is_windows']:
            subprocess.Popen([path, "--app"])
        else:
            env = os.environ.copy()
            if sys_info['is_linux']:
                env.update({
                    "__NV_PRIME_RENDER_OFFLOAD": "1",
                    "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                })
            wine_cmd = "wine64"
            try:
                subprocess.check_output([wine_cmd, "--version"], stderr=subprocess.DEVNULL)
            except Exception:
                wine_cmd = "wine"
            subprocess.Popen([wine_cmd, path, "--app"], env=env)
        return True, None
    except Exception as e:
        return False, str(e)

class Projexstrap(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Projexstrap")
        self.geometry("920x640")
        self.minsize(880, 560)
        self.bg = "#151515"     # main background
        self.panel = "#252525"  # panels
        self.card = "#252525"   # card surfaces
        self.fg = "#e6eef8"     # text
        self.sub = "#9aa9ba"    # secondary text
        self.accent = "#606060" # accent
        self.warn = "#f0b429"
        self.error = "#f97373"
        self.configure(bg=self.bg)
        self.style = ttk.Style(self)
        self._setup_style()
        self.fastflags = load_fastflags_local()
        self.create_layout()
        self.refresh_version_list()
        self.refresh_fastflags_view()
        self.refresh_debug_info()

    def _setup_style(self):
        self.style.theme_use('clam')
        self.style.configure("TFrame", background=self.panel)
        self.style.configure("Card.TFrame", background=self.card, relief="flat")
        self.style.configure("TLabel", background=self.panel, foreground=self.fg, font=("Segoe UI", 10))
        self.style.configure("Heading.TLabel", font=("Segoe UI Semibold", 14), foreground=self.fg)
        self.style.configure("Sub.TLabel", foreground=self.sub, font=("Segoe UI", 9))
        self.style.configure("TButton", background=self.accent, foreground=self.bg, font=("Segoe UI Semibold", 10))
        self.style.map("TButton", background=[('active', '#404040')])
        self.style.configure("Accent.TButton", background=self.accent, foreground=self.bg, font=("Segoe UI Semibold", 10))
        self.style.configure("Danger.TButton", background=self.error, foreground=self.bg)
        self.style.configure("TEntry", fieldbackground=self.card, background=self.card, foreground=self.fg)
        self.style.configure("Treeview", background=self.card, fieldbackground=self.card, foreground=self.fg, rowheight=24)
        self.style.map("Treeview", background=[("selected", "#404040")], foreground=[("selected", self.fg)])
        self.style.configure("Vertical.TScrollbar", background=self.card, troughcolor=self.panel, arrowcolor=self.accent)

    def create_layout(self):
        top = ttk.Frame(self, style="TFrame")
        top.pack(fill="x", padx=18, pady=14)

        ttk.Label(top, text="Projexstrap", style="Heading.TLabel").pack(side="left")
        ttk.Label(top, text="• Projexstrap - Dark", style="Sub.TLabel").pack(side="left", padx=(8,0))

        container = ttk.Frame(self, style="TFrame")
        container.pack(fill="both", expand=True, padx=18, pady=(0,18))

        left = ttk.Frame(container, width=260, style="Card.TFrame")
        left.pack(side="left", fill="y", padx=(0,12), pady=2)
        left.pack_propagate(False)

        right = ttk.Frame(container, style="TFrame")
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Quick Actions", style="Sub.TLabel").pack(anchor="w", padx=14, pady=(8,4))
        pad = {"padx": 12, "pady": 6, "ipadx": 6, "ipady": 6}
        ttk.Button(left, text="Launch 2020 (2020L)", style="Accent.TButton", command=lambda: self.launch_version_ui("2020L")).pack(fill="x", **pad)
        ttk.Button(left, text="Launch 2021 (2021M)", style="Accent.TButton", command=lambda: self.launch_version_ui("2021M")).pack(fill="x", **pad)
        ttk.Button(left, text="Set FastFlags", command=self.open_fastflags_editor).pack(fill="x", **pad)
        btn_dl = ttk.Button(left, text="Download/Update Bootstrapper (MAINTENANCE)", state="disabled")
        btn_dl.pack(fill="x", **pad)

        ttk.Button(left, text="Debug Info", command=self.open_debug_window).pack(fill="x", **pad)
        ttk.Separator(left).pack(fill="x", padx=12, pady=(6,12))
        bb = ttk.Frame(left, style="Card.TFrame")
        bb.pack(fill="x", padx=12, pady=(0,12))
        ttk.Label(bb, text="Bootstrapper", style="Sub.TLabel").pack(anchor="w", padx=8, pady=(8,0))
        self.bs_status = ttk.Label(bb, text="Checking...", style="TLabel")
        self.bs_status.pack(anchor="w", padx=8, pady=(2,10))

        tabs = ttk.Notebook(right)
        tabs.pack(fill="both", expand=True)

        frame_versions = ttk.Frame(tabs, style="TFrame")
        tabs.add(frame_versions, text="Versions")

        ttk.Label(frame_versions, text="Detected Installations", style="Sub.TLabel").pack(anchor="w", padx=14, pady=(12,6))
        self.versions_tree = ttk.Treeview(frame_versions, columns=("path",), show="headings", selectmode="browse", height=10)
        self.versions_tree.heading("path", text="Installation path")
        self.versions_tree.column("path", anchor="w", width=640)
        self.versions_tree.pack(fill="both", padx=14, pady=(0,8), expand=True)
        vbtnframe = ttk.Frame(frame_versions, style="TFrame")
        vbtnframe.pack(fill="x", padx=14, pady=(0,12))
        ttk.Button(vbtnframe, text="Refresh", command=self.refresh_version_list).pack(side="left")
        ttk.Button(vbtnframe, text="Open in Explorer", command=self.open_selected_path).pack(side="left", padx=6)
        ttk.Button(vbtnframe, text="Launch selected Client", command=self.launch_selected).pack(side="left", padx=6)

        frame_flags = ttk.Frame(tabs, style="TFrame")
        tabs.add(frame_flags, text="FastFlags")

        topbar = ttk.Frame(frame_flags, style="TFrame")
        topbar.pack(fill="x", padx=14, pady=(12,8))
        ttk.Button(topbar, text="Open Editor", command=self.open_fastflags_editor).pack(side="left")
        ttk.Button(topbar, text="Apply to Clients", command=self.apply_fastflags_ui).pack(side="left", padx=6)
        ttk.Button(topbar, text="Import JSON...", command=self.import_fastflags_from_file).pack(side="left", padx=6)

        self.flags_preview = tk.Text(frame_flags, height=16, wrap="none", bg=self.card, fg=self.fg, bd=0, padx=10, pady=8)
        self.flags_preview.pack(fill="both", expand=True, padx=14, pady=(0,12))

        frame_debug = ttk.Frame(tabs, style="TFrame")
        tabs.add(frame_debug, text="Debug")

        ttk.Label(frame_debug, text="Quick Debug", style="Sub.TLabel").pack(anchor="w", padx=14, pady=(12,6))
        self.debug_text = tk.Text(frame_debug, height=20, bg=self.card, fg=self.fg, bd=0, padx=10, pady=8)
        self.debug_text.pack(fill="both", expand=True, padx=14, pady=(0,12))

    def refresh_version_list(self):
        for i in self.versions_tree.get_children():
            self.versions_tree.delete(i)
        inserted = 0
        for ver in iter_version_dirs():
            self.versions_tree.insert("", "end", values=(ver,))
            inserted += 1
        if inserted == 0:
            self.versions_tree.insert("", "end", values=("No installations found",))
        self.refresh_bs_status()
        self.refresh_fastflags_view()

    def open_selected_path(self):
        sel = self.versions_tree.selection()
        if not sel:
            messagebox.showinfo("Open", "No path selected")
            return
        path = self.versions_tree.item(sel[0])['values'][0]
        if path and os.path.isdir(path):
            if get_system_info()['is_windows']:
                subprocess.Popen(["explorer", os.path.normpath(path)])
            else:
                try:
                    subprocess.Popen(["xdg-open", path])
                except Exception:
                    messagebox.showinfo("Open", f"Can't open folder on your platform: {path}")
        else:
            messagebox.showinfo("Open", f"Path not found: {path}")

    def launch_selected(self):
        sel = self.versions_tree.selection()
        if not sel:
            messagebox.showinfo("Launch", "No installation selected")
            return
        path = self.versions_tree.item(sel[0])['values'][0]
        found = False
        for folder in ("2020L", "2021M"):
            exe = os.path.join(path, folder, "ProjectXPlayerBeta.exe")
            if os.path.isfile(exe):
                ok, err = launch_executable(exe)
                if ok:
                    messagebox.showinfo("Launch", f"Launched: {os.path.basename(exe)}")
                else:
                    messagebox.showerror("Launch failed", err or "Unknown error")
                found = True
                break
        if not found:
            messagebox.showinfo("Launch", "No executable found inside selected installation.")

    def launch_version_ui(self, folder):
        paths = get_executable_paths(folder)
        exe_path = None
        for p in paths:
            if os.path.isfile(p):
                exe_path = p
                break
        if exe_path:
            ok, err = launch_executable(exe_path)
            if ok:
                messagebox.showinfo("Launch", f"Launched {folder}")
            else:
                messagebox.showerror("Launch failed", err or "Unknown error")
        else:
            messagebox.showwarning("Not Found", f"No executable found for {folder}. Searched {len(paths)} places.")
            if messagebox.askyesno("Troubleshoot", "Open debug window to view searched paths?"):
                self.open_debug_window()

    def refresh_fastflags_view(self):
        self.fastflags = load_fastflags_local()
        pretty = json.dumps(self.fastflags, indent=2)
        self.flags_preview.delete("1.0", tk.END)
        self.flags_preview.insert(tk.END, pretty)

    def open_fastflags_editor(self):
        FastFlagsEditor(self, self.fastflags, on_save=self.on_fastflags_saved)

    def on_fastflags_saved(self, new_flags):
        self.fastflags = new_flags
        save_fastflags_local(self.fastflags)
        self.refresh_fastflags_view()
        messagebox.showinfo("Saved", "FastFlags saved locally.")

    def apply_fastflags_ui(self):
        self.fastflags = load_fastflags_local()
        if not self.fastflags:
            messagebox.showwarning("No Flags", "No FastFlags to apply.")
            return
        applied, failed = apply_fastflags_to_clients(self.fastflags)
        msg = f"Applied to {len(applied)} path(s).\n"
        if failed:
            msg += f"\nFailed for {len(failed)} path(s)."
            messagebox.showwarning("Apply complete", msg)
        else:
            messagebox.showinfo("Apply complete", msg)
        self.refresh_debug_info()

    def import_fastflags_from_file(self):
        fn = filedialog.askopenfilename(title="Import FastFlags JSON", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not fn:
            return
        try:
            with open(fn, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                messagebox.showerror("Invalid", "JSON must be an object/dictionary")
                return
            current = load_fastflags_local()
            current.update(data)
            save_fastflags_local(current)
            self.refresh_fastflags_view()
            messagebox.showinfo("Imported", f"Imported {len(data)} flag(s).")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import: {e}")

    def refresh_bs_status(self):
        if os.path.exists(BOOTSTRAPPER_FILE):
            size_mb = os.path.getsize(BOOTSTRAPPER_FILE) / (1024 * 1024)
            self.bs_status.config(text=f"Found: {BOOTSTRAPPER_FILE} ({size_mb:.1f} MB)", foreground=self.fg)
        else:
            self.bs_status.config(text=f"Not found: {BOOTSTRAPPER_FILE}", foreground=self.warn)

    def refresh_debug_info(self):
        self.debug_text.delete("1.0", tk.END)
        sys_info = get_system_info()
        self.debug_text.insert(tk.END, f"OS: {platform.system()} {platform.release()}\n")
        self.debug_text.insert(tk.END, f"Arch: {platform.machine()}\n")
        self.debug_text.insert(tk.END, f"Python: {sys.version.split()[0]}\n\n")
        self.debug_text.insert(tk.END, "Installation roots checked:\n")
        for r in get_version_roots():
            self.debug_text.insert(tk.END, f" - {r}\n")
        self.debug_text.insert(tk.END, "\nClientSettings Targets:\n")
        targets = get_clientsettings_targets()
        if not targets:
            self.debug_text.insert(tk.END, "  None found\n")
        else:
            for client_dir, settings_path, folder in targets:
                exists = os.path.exists(settings_path)
                marker = "✓" if exists else "✗"
                self.debug_text.insert(tk.END, f" {marker} {folder}: {settings_path}\n")
        self.refresh_bs_status()

    def open_debug_window(self):
        DebugWindow(self)

class FastFlagsEditor(tk.Toplevel):
    def __init__(self, parent, flags, on_save=None):
        super().__init__(parent)
        self.title("FastFlags Editor")
        self.geometry("720x520")
        self.configure(bg=parent.bg)
        self.parent = parent
        self.on_save = on_save
        self.flags = dict(flags or {})
        self._build_ui()

    def _build_ui(self):
        padx = 12
        pady = 10
        frame = ttk.Frame(self, style="Card.TFrame")
        frame.pack(fill="both", expand=True, padx=16, pady=16)
        left = ttk.Frame(frame, style="Card.TFrame")
        left.pack(side="left", fill="y", padx=(8,12), pady=8)
        ttk.Label(left, text="Flags", style="Sub.TLabel").pack(anchor="w", padx=8, pady=(6,6))
        self.listbox = tk.Listbox(left, width=38, height=20, bg=self.parent.card, fg=self.parent.fg, bd=0, highlightthickness=0)
        self.listbox.pack(padx=6, pady=(0,6))
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        right = ttk.Frame(frame, style="Card.TFrame")
        right.pack(side="left", fill="both", expand=True, padx=(0,8), pady=8)

        ttk.Label(right, text="Key", style="Sub.TLabel").pack(anchor="w", padx=8, pady=(6,0))
        self.entry_key = ttk.Entry(right)
        self.entry_key.pack(fill="x", padx=8, pady=(0,8))

        ttk.Label(right, text="Value", style="Sub.TLabel").pack(anchor="w", padx=8, pady=(6,0))
        self.entry_value = ttk.Entry(right)
        self.entry_value.pack(fill="x", padx=8, pady=(0,8))

        btnf = ttk.Frame(right, style="TFrame")
        btnf.pack(anchor="e", pady=8, padx=8)
        ttk.Button(btnf, text="Add / Update", command=self.add_or_update).pack(side="left", padx=6)
        ttk.Button(btnf, text="Remove", command=self.remove_selected).pack(side="left", padx=6)
        ttk.Button(btnf, text="Import JSON", command=self.import_json).pack(side="left", padx=6)

        bottom = ttk.Frame(right, style="TFrame")
        bottom.pack(fill="x", padx=8, pady=(12,8))
        ttk.Button(bottom, text="Save & Close", command=self.save_and_close).pack(side="right")

        self.populate_list()

    def populate_list(self):
        self.listbox.delete(0, tk.END)
        keys = sorted(self.flags.keys())
        for k in keys:
            v = self.flags[k]
            self.listbox.insert(tk.END, f"{k} = {v}")

    def on_select(self, evt=None):
        sel = self.listbox.curselection()
        if not sel: return
        idx = sel[0]
        text = self.listbox.get(idx)
        if " = " in text:
            k, v = text.split(" = ", 1)
            self.entry_key.delete(0, tk.END)
            self.entry_key.insert(0, k)
            self.entry_value.delete(0, tk.END)
            self.entry_value.insert(0, str(v))

    def add_or_update(self):
        k = self.entry_key.get().strip()
        v_raw = self.entry_value.get().strip()
        if not k:
            messagebox.showerror("Error", "Key cannot be empty")
            return
        val = auto_detect_value_type(v_raw)
        self.flags[k] = val
        self.populate_list()

    def remove_selected(self):
        k = self.entry_key.get().strip()
        if not k:
            messagebox.showwarning("Remove", "No key provided")
            return
        if k in self.flags:
            del self.flags[k]
            self.populate_list()
            self.entry_key.delete(0, tk.END)
            self.entry_value.delete(0, tk.END)
        else:
            messagebox.showinfo("Remove", "Key not found")

    def import_json(self):
        fn = filedialog.askopenfilename(title="Import FastFlags JSON", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not fn:
            return
        try:
            with open(fn, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                messagebox.showerror("Invalid", "JSON must be an object/dictionary")
                return
            self.flags.update(data)
            self.populate_list()
            messagebox.showinfo("Imported", f"Imported {len(data)} flag(s).")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import: {e}")

    def save_and_close(self):
        if self.on_save:
            self.on_save(self.flags)
        self.destroy()

class DebugWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Debug Information")
        self.geometry("820x520")
        self.configure(bg=parent.bg)
        txt = tk.Text(self, bg=parent.card, fg=parent.fg, bd=0, padx=10, pady=8)
        txt.pack(fill="both", expand=True, padx=16, pady=16)
        sys_info = get_system_info()
        lines = []
        lines.append(f"OS: {platform.system()} {platform.release()}")
        lines.append(f"Arch: {platform.machine()}")
        lines.append(f"Python: {sys.version.split()[0]}")
        lines.append("")
        lines.append("Installation roots checked:")
        for r in get_version_roots():
            lines.append(f" - {r}")
        lines.append("")
        lines.append("ClientSettings Targets:")
        targets = get_clientsettings_targets()
        if not targets:
            lines.append("  None found")
        else:
            for client_dir, settings_path, folder in targets:
                exists = os.path.exists(settings_path)
                mark = "✓" if exists else "✗"
                lines.append(f" {mark} {folder}: {settings_path}")
        lines.append("")
        lines.append("Local FastFlags file:")
        lines.append(f" - {FASTFLAGS_FILE} (exists: {os.path.exists(FASTFLAGS_FILE)})")
        lines.append("")
        lines.append("Bootstrapper:")
        lines.append(f" - {BOOTSTRAPPER_FILE} (exists: {os.path.exists(BOOTSTRAPPER_FILE)})")
        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")

if __name__ == "__main__":
    app = Projexstrap()
    app.mainloop()