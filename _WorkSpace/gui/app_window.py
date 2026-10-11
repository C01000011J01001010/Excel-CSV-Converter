import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from utils import get_initial_dir, find_workspace_root, create_workspace_root, set_exclude_prefix
from core.converter import convert_xlsx_file, convert_ansi_csv_to_utf8
from core.superkey_finder import find_super_keys
from core.validator import run_global_validation
from core.watcher import PipelineWatcher

from gui.left_panel import LeftPanel
from gui.right_panel import RightPanel

class AppGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSV DesignDB Toolkit")
        
        self.base_width = 1600
        self.base_height = 900
        self.geometry(f"{self.base_width}x{self.base_height}")
        self.minsize(800, 600)
        self.configure(bg="#1E1E1E")
        
        try:
            self.state('zoomed')
        except: pass

        self.target_dir = get_initial_dir()
        self.workspace_root = None
        self.workspace_file = None
        self._is_loading_config = False
        
        self.include_subdirs = tk.BooleanVar(value=True)
        self.max_combo_var = tk.IntVar(value=2)
        self.exclude_prefix_var = tk.StringVar(value="Disabled")
        self.progress_var = tk.DoubleVar()

        self.setup_ui()
        self.watcher = PipelineWatcher(self.right_panel.log)
        
        self._init_workspace()
        
        self.include_subdirs.trace_add("write", lambda *a: self.save_workspace_config())
        self.max_combo_var.trace_add("write", lambda *a: self.save_workspace_config())
        self.exclude_prefix_var.trace_add("write", lambda *a: self._on_exclude_prefix_changed())
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _on_exclude_prefix_changed(self):
        val = self.exclude_prefix_var.get().strip()
        set_exclude_prefix(val if val else "Disabled")
        self.save_workspace_config()

    def load_workspace_config(self):
        if not self.workspace_root or not self.workspace_file: return
        filepath = os.path.join(self.workspace_root, self.workspace_file)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                settings = data.get("settings", {})
                if "maxSuperkeyLength" in settings: self.max_combo_var.set(settings["maxSuperkeyLength"])
                if "includeSubDirectories" in settings: self.include_subdirs.set(settings["includeSubDirectories"])
                if "excludePrefix" in settings:
                    self.exclude_prefix_var.set(settings["excludePrefix"])
                    set_exclude_prefix(settings["excludePrefix"])
        except Exception as e:
            self.right_panel.log(f"⚠️ 설정 로드 실패: {e}")

    def save_workspace_config(self):
        if self._is_loading_config: return
        if not self.workspace_root or not self.workspace_file or not self.workspace_file.endswith('.csvdesigndb'): return
        filepath = os.path.join(self.workspace_root, self.workspace_file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
        except:
            data = {"projectName": self.workspace_file.replace('.csvdesigndb', ''), "settings": {}}
            
        data["settings"] = {
            "maxSuperkeyLength": self.max_combo_var.get(),
            "includeSubDirectories": self.include_subdirs.get(),
            "excludePrefix": self.exclude_prefix_var.get().strip() or "Disabled"
        }
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except: pass

    def _init_workspace(self):
        w_root, w_file = find_workspace_root(self.target_dir)
        if w_root:
            self.workspace_root = w_root
            self.workspace_file = w_file
            self._is_loading_config = True
            self.load_workspace_config()
            self._is_loading_config = False
            self.lbl_workspace.config(text=f"📂 워크스페이스: {self.workspace_root}")
            self.right_panel.log(f"✅ 워크스페이스 로드 성공: {self.workspace_file}")
            if not os.path.abspath(self.target_dir).startswith(os.path.abspath(self.workspace_root)):
                self.target_dir = self.workspace_root
                self.path_entry_var.set(self.target_dir)
        else:
            self.lbl_workspace.config(text="⚠️ 워크스페이스 미설정 (기능 제한)")

    def _restart_watcher_if_needed(self):
        if self.watcher.is_watching and self.workspace_root:
            self.watcher.stop()
            self.watcher.start(self.workspace_root, True)
            self.right_panel.log("🔄 워크스페이스 감시기 재시작 완료.")

    def change_workspace_manual(self):
        selected_dir = filedialog.askdirectory(title="워크스페이스 변경", initialdir=self.target_dir)
        if not selected_dir: return
        w_root, w_file = find_workspace_root(selected_dir)
        if w_root:
            self.workspace_root = w_root
            self.workspace_file = w_file
            self._is_loading_config = True
            self.load_workspace_config()
            self._is_loading_config = False
            self.lbl_workspace.config(text=f"📂 워크스페이스: {self.workspace_root}")
            self.change_dir_force(w_root)
            self._restart_watcher_if_needed()
        else:
            # 💡 [FIX] 경고 메시지 대신 생성 의사를 묻고 바로 생성 흐름으로 넘깁니다.
            ans = messagebox.askyesno("안내", "선택하신 경로나 상위 경로에 워크스페이스(.csvdesigndb)가 없습니다.\n\n해당 경로에 새 워크스페이스를 생성하시겠습니까?")
            if ans:
                self.create_workspace_manual(predefined_dir=selected_dir)

    # 💡 [FIX] 미리 선택된 경로(predefined_dir)를 받을 수 있도록 파라미터 추가
    def create_workspace_manual(self, predefined_dir=None):
        if predefined_dir:
            selected_dir = predefined_dir
        else:
            selected_dir = filedialog.askdirectory(title="새 워크스페이스 생성", initialdir=self.target_dir)
            
        if not selected_dir: return
        
        # 현재 경로에 이미 워크스페이스 파일이 존재하는지 검사
        existing = [f for f in os.listdir(selected_dir) if f.endswith('.csvdesigndb')]
        if existing:
            ans = messagebox.askyesno("확인", f"선택한 경로에 이미 워크스페이스({existing[0]})가 존재합니다.\n\n무시하고 새 워크스페이스를 덮어쓰시겠습니까?")
            if not ans: return
            
        proj_name = simpledialog.askstring("새 워크스페이스 생성", "새 프로젝트(세부 작업공간) 명 입력:")
        if proj_name:
            w_root, w_file = create_workspace_root(selected_dir, proj_name)
            if w_root:
                self.workspace_root = w_root
                self.workspace_file = w_file
                self._is_loading_config = True
                self.load_workspace_config()
                self._is_loading_config = False
                self.lbl_workspace.config(text=f"📂 워크스페이스: {self.workspace_root}")
                self.change_dir_force(w_root)
                self._restart_watcher_if_needed()

    def setup_ui(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure("TNotebook", background="#1E1E1E", borderwidth=0)
        style.configure("TNotebook.Tab", background="#2D2D2D", foreground="white", padding=[15, 5], font=("맑은 고딕", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#007ACC")])

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.global_canvas = tk.Canvas(self, bg="#1E1E1E", highlightthickness=0)
        self.global_scroll_y = ttk.Scrollbar(self, orient="vertical", command=self.global_canvas.yview)
        self.global_scroll_x = ttk.Scrollbar(self, orient="horizontal", command=self.global_canvas.xview)
        self.main_container = tk.Frame(self.global_canvas, bg="#1E1E1E")
        self.main_container.bind("<Configure>", lambda e: self.global_canvas.configure(scrollregion=self.global_canvas.bbox("all")))
        self.canvas_window = self.global_canvas.create_window((0, 0), window=self.main_container, anchor="nw")
        self.global_canvas.bind('<Configure>', self._on_global_canvas_configure)
        self.global_canvas.configure(yscrollcommand=self.global_scroll_y.set, xscrollcommand=self.global_scroll_x.set)
        
        self.global_canvas.grid(row=0, column=0, sticky="nsew")
        self.global_scroll_y.grid(row=0, column=1, sticky="ns")
        self.global_scroll_x.grid(row=1, column=0, sticky="ew")

        self.bind('<Configure>', self._on_root_configure)

        header_frame = tk.Frame(self.main_container, bg="#2D2D2D", pady=10)
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="⚙️ CSV DesignDB Toolkit", font=("Segoe UI", 16, "bold"), fg="#FFFFFF", bg="#2D2D2D").pack()
        
        workspace_frame = tk.Frame(self.main_container, bg="#1E1E1E", pady=10)
        workspace_frame.pack(fill="x")
        self.lbl_workspace = tk.Label(workspace_frame, text="📂 워크스페이스 로드 중...", font=("맑은 고딕", 11, "bold"), fg="#00FF66", bg="#1E1E1E")
        self.lbl_workspace.pack(side="left", padx=20)
        
        tk.Button(workspace_frame, text="➕ 새 워크스페이스 생성", font=("맑은 고딕", 9, "bold"), bg="#28A745", fg="white", bd=0, command=self.create_workspace_manual).pack(side="right", padx=(5, 20))
        tk.Button(workspace_frame, text="🔄 워크스페이스 변경", font=("맑은 고딕", 9, "bold"), bg="#007ACC", fg="white", bd=0, command=self.change_workspace_manual).pack(side="right", padx=5)

        nav_frame = tk.Frame(self.main_container, bg="#1E1E1E", pady=10, padx=20)
        nav_frame.pack(fill="x")
        tk.Label(nav_frame, text="작업 경로:", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        self.path_entry_var = tk.StringVar(value=self.target_dir)
        self.path_entry = tk.Entry(nav_frame, textvariable=self.path_entry_var, font=("Consolas", 10), bg="#2D2D2D", fg="white", insertbackground="white", bd=1, relief="solid")
        self.path_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.path_entry.bind('<Return>', lambda event: self.apply_manual_path())
        tk.Button(nav_frame, text="이동", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.apply_manual_path).pack(side="left", padx=2)
        tk.Button(nav_frame, text="⬆ 상위", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.go_up_dir).pack(side="left", padx=2)
        tk.Button(nav_frame, text="🔍 탐색", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.browse_dir).pack(side="left", padx=2)

        opt_frame = tk.Frame(self.main_container, bg="#1E1E1E", padx=20)
        opt_frame.pack(fill="x", pady=(0, 10))
        tk.Checkbutton(opt_frame, text="현재 경로의 하위 폴더 포함 (DFS)", variable=self.include_subdirs, font=("맑은 고딕", 10, "bold"),
                       bg="#1E1E1E", fg="#FFD700", selectcolor="#2D2D2D", activebackground="#1E1E1E", activeforeground="white").pack(side="left")
        
        tk.Label(opt_frame, text="예외 파일 Prefix (무시할 폴더/파일명):", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left", padx=(30, 5))
        tk.Entry(opt_frame, textvariable=self.exclude_prefix_var, width=15, font=("Consolas", 10), bg="#2D2D2D", fg="white", insertbackground="white").pack(side="left", padx=5)

        content_frame = tk.Frame(self.main_container, bg="#1E1E1E")
        content_frame.pack(fill="both", expand=True, padx=20, pady=5)
        content_frame.grid_columnconfigure(0, weight=1, uniform="half")
        content_frame.grid_columnconfigure(1, weight=1, uniform="half")
        content_frame.grid_rowconfigure(0, weight=1)

        self.left_panel = LeftPanel(content_frame, app=self)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.right_panel = RightPanel(content_frame)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    def _on_root_configure(self, event):
        if event.widget == self:
            is_fullscreen = False
            try:
                if self.state() == 'zoomed': is_fullscreen = True
            except: pass
            if is_fullscreen:
                self.global_scroll_y.grid_remove()
                self.global_scroll_x.grid_remove()
            else:
                self.global_scroll_y.grid()
                self.global_scroll_x.grid()

    def _on_global_canvas_configure(self, event):
        w = max(event.width, self.base_width)
        h = max(event.height, self.base_height)
        self.global_canvas.itemconfig(self.canvas_window, width=w, height=h)

    def set_buttons_state(self, state):
        flag = tk.NORMAL if state else tk.DISABLED
        if hasattr(self.left_panel.app, 'btn1'): self.left_panel.app.btn1.config(state=flag)
        if hasattr(self.left_panel.app, 'btn2'): self.left_panel.app.btn2.config(state=flag)
        if hasattr(self.left_panel.app, 'btn4'): self.left_panel.app.btn4.config(state=flag)
        if hasattr(self.left_panel.app, 'btn_validate'): self.left_panel.app.btn_validate.config(state=flag)

    def set_progress(self, value):
        self.after(0, lambda: self.progress_var.set(value))

    def apply_manual_path(self):
        new_path = self.path_entry_var.get().strip()
        if os.path.isdir(new_path): self.change_dir(new_path)
        else:
            messagebox.showerror("오류", "유효하지 않은 경로입니다.")
            self.path_entry_var.set(self.target_dir)

    def go_up_dir(self):
        parent_dir = os.path.dirname(self.target_dir)
        if os.path.isdir(parent_dir): self.change_dir(parent_dir)

    def browse_dir(self):
        selected_dir = filedialog.askdirectory(initialdir=self.target_dir, title="작업 폴더 선택")
        if selected_dir: self.change_dir(os.path.normpath(selected_dir))

    def change_dir_force(self, new_dir):
        self.target_dir = new_dir
        self.path_entry_var.set(self.target_dir)
        self.right_panel.log(f"\n📂 작업 경로(포커스) 변경됨: {self.target_dir}")
        if hasattr(self.left_panel, '_t1_refresh_files'): self.left_panel._t1_refresh_files()

    def change_dir(self, new_dir):
        if self.target_dir == new_dir: return
        abs_new = os.path.abspath(new_dir)
        if self.workspace_root:
            abs_ws = os.path.abspath(self.workspace_root)
            if abs_new.startswith(abs_ws):
                self.change_dir_force(new_dir)
                return
            w_root, w_file = find_workspace_root(new_dir)
            if w_root and os.path.abspath(w_root) != abs_ws:
                ans = messagebox.askyesno("워크스페이스 변경", f"새 워크스페이스로 전환하시겠습니까?\n{w_root}")
                if ans:
                    self.workspace_root = w_root
                    self.workspace_file = w_file
                    self._is_loading_config = True
                    self.load_workspace_config()
                    self._is_loading_config = False
                    self.lbl_workspace.config(text=f"📂 워크스페이스: {self.workspace_root}")
                    self.change_dir_force(new_dir)
                    self._restart_watcher_if_needed()
                else: self.path_entry_var.set(self.target_dir) 
                return
            else:
                messagebox.showwarning("이동 제한", "경로가 워크스페이스 외부에 있습니다.")
                self.path_entry_var.set(self.target_dir) 
                return
        self.change_dir_force(new_dir)

    def run_xlsx_to_csv_all(self):
        if not self.workspace_root: return
        def task():
            self.set_buttons_state(False)
            self.right_panel.log("\n🚀 [작업 시작] 엑셀 ➔ CSV 변환")
            count = 0
            prefix = self.exclude_prefix_var.get().strip() or "Disabled"
            for root, dirs, files in os.walk(self.target_dir):
                if any(p.startswith(prefix) for p in root.replace('\\', '/').split('/')): continue
                if not self.include_subdirs.get(): dirs.clear()
                for file in files:
                    if file.startswith('~$') or file.startswith(prefix): continue
                    if file.endswith('.xlsx'):
                        filepath = os.path.join(root, file)
                        success, _ = convert_xlsx_file(filepath)
                        if success: count += 1
            self.right_panel.log(f"✨ 총 {count}개 변환 완료!")
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def run_ansi_to_utf8_all(self):
        if not self.workspace_root: return
        def task():
            self.set_buttons_state(False)
            self.right_panel.log("\n🚀 [작업 시작] CSV 인코딩(UTF-8) 변환")
            count = 0
            prefix = self.exclude_prefix_var.get().strip() or "Disabled"
            for root, dirs, files in os.walk(self.target_dir):
                if any(p.startswith(prefix) for p in root.replace('\\', '/').split('/')): continue
                if not self.include_subdirs.get(): dirs.clear()
                for file in files:
                    if file.startswith(prefix): continue
                    if file.endswith('.csv'):
                        filepath = os.path.join(root, file)
                        success, _ = convert_ansi_csv_to_utf8(filepath)
                        if success: count += 1
            self.right_panel.log(f"✨ 총 {count}개 완료!")
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def toggle_watch_mode(self):
        if not self.workspace_root: return
        if not self.watcher.is_watching:
            self.watcher.start(self.workspace_root, True)
            if hasattr(self.left_panel.app, 'btn3'): self.left_panel.app.btn3.config(text="백그라운드 감시 중지 (실행 중...)", bg="#DC3545")
            self.right_panel.log(f"\n🕵️‍♂️ [자동 변환 감시 시작]")
        else:
            self.watcher.stop()
            if hasattr(self.left_panel.app, 'btn3'): self.left_panel.app.btn3.config(text="백그라운드 자동 변환 감시 모드 시작", bg="#6C757D")
            self.right_panel.log("\n🛑 [감시 중지]")

    def run_super_key_finder(self):
        if not self.workspace_root: return
        def task():
            self.set_buttons_state(False)
            self.set_progress(0)
            prefix = self.exclude_prefix_var.get().strip() or "Disabled"
            self.right_panel.log("\n🚀 [작업 시작] 메타데이터 슈퍼키(.csvmeta) 추출 (Fast-Track 포함)")
            find_super_keys(self.target_dir, self.max_combo_var.get(), self.include_subdirs.get(), self.right_panel.log, self.set_progress, prefix)
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def run_global_validation(self):
        if not self.workspace_root: return
        def task():
            self.set_buttons_state(False)
            self.set_progress(0)
            prefix = self.exclude_prefix_var.get().strip() or "Disabled"
            self.right_panel.log("\n🚀 [작업 시작] 워크스페이스 전체 무결성 글로벌 검증")
            run_global_validation(self.workspace_root, self.right_panel.log, self.set_progress, prefix)
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def on_close(self):
        self.watcher.stop()
        self.destroy()
