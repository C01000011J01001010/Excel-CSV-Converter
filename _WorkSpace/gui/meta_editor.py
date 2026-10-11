import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
from gui.widgets import ScrollableFrame
from gui.constraint_builder import ForeignKeyBuilder

class MetaEditorTab(tk.Frame):
    def __init__(self, parent, app, *args, **kwargs):
        super().__init__(parent, bg="#1E1E1E", *args, **kwargs)
        self.app = app
        self.meta_data = {}
        self.fk_builders = []
        self._build_ui()

    def _build_ui(self):
        top_frame = tk.Frame(self, bg="#1E1E1E")
        top_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(top_frame, text="대상 .csvmeta 메타 파일:", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        self.combo_files = ttk.Combobox(top_frame, state="readonly", width=60)
        self.combo_files.pack(side="left", padx=10, fill="x", expand=True)

        btn_refresh = tk.Button(top_frame, text="새로고침", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self._refresh_files)
        btn_refresh.pack(side="left", padx=2)
        btn_load = tk.Button(top_frame, text="메타 로드", font=("맑은 고딕", 9, "bold"), bg="#007ACC", fg="white", bd=0, command=self._load_meta)
        btn_load.pack(side="left", padx=2)

        self.main_area = tk.Frame(self, bg="#1E1E1E")
        self.main_area.pack(fill="both", expand=True, padx=10, pady=5)
        self._build_pk_area()
        self._build_fk_area()

        bottom_frame = tk.Frame(self, bg="#1E1E1E")
        bottom_frame.pack(fill="x", padx=10, pady=10)
        tk.Button(bottom_frame, text="✅ 메타(PK/FK) 설정 저장", font=("맑은 고딕", 11, "bold"), bg="#28A745", fg="white", bd=0, height=2, command=self._save_meta).pack(fill="x")

    def _build_pk_area(self):
        pk_frame = tk.LabelFrame(self.main_area, text=" 기본키(PK) 설정 ", font=("맑은 고딕", 10, "bold"), bg="#1E1E1E", fg="#FFD700")
        pk_frame.pack(fill="x", pady=10, padx=5, ipady=10)

        inner = tk.Frame(pk_frame, bg="#1E1E1E")
        inner.pack(anchor="w", padx=10)
        
        tk.Label(inner, text="기본키(PK)로 사용할 슈퍼키 조합 선택:", font=("맑은 고딕", 9), bg="#1E1E1E", fg="white").pack(side="left")
        self.combo_pk = ttk.Combobox(inner, state="readonly", width=50)
        self.combo_pk.pack(side="left", padx=10)

    def _build_fk_area(self):
        fk_frame = tk.LabelFrame(self.main_area, text=" 🔗 Foreign Keys (외래키) 객체 매핑 ", font=("맑은 고딕", 10, "bold"), bg="#1E1E1E", fg="#00FF66")
        fk_frame.pack(fill="both", expand=True, pady=5, padx=5)

        sf = ScrollableFrame(fk_frame)
        sf.pack(fill="both", expand=True)
        self.fk_inner = sf.inner_frame

        btn_frame = tk.Frame(fk_frame, bg="#1E1E1E")
        btn_frame.pack(fill="x", pady=5, padx=5)
        tk.Button(btn_frame, text="+ FK 객체 추가", font=("맑은 고딕", 9, "bold"), bg="#28A745", fg="white", bd=0, command=self._add_fk_builder).pack(side="left")

    def _refresh_files(self):
        if not self.app.workspace_root:
            self.app.right_panel.log("⚠️ 워크스페이스가 설정되지 않았습니다.")
            return
            
        json_files = []
        prefix = self.app.exclude_prefix_var.get().strip() or "Disabled"
        for root, dirs, files in os.walk(self.app.target_dir):
            # 💡 [핵심 버그 픽스] target_dir을 기준으로 상대 경로에서만 Prefix 필터링 적용!
            rel_root = os.path.relpath(root, self.app.target_dir)
            if rel_root != '.' and any(p.startswith(prefix) for p in rel_root.replace('\\', '/').split('/')):
                continue
                
            if not self.app.include_subdirs.get() and root != self.app.target_dir:
                continue
                
            for file in files:
                if file.startswith(prefix):
                    continue
                if file.endswith('.csvmeta'):
                    rel_path = os.path.relpath(os.path.join(root, file), self.app.target_dir).replace('\\', '/')
                    json_files.append(rel_path)

        if json_files:
            self.combo_files['values'] = json_files
            self.combo_files.current(0)
            self.app.right_panel.log(f"작업 경로 내 메타 파일(.csvmeta) {len(json_files)}개 스캔 완료.")
        else:
            self.combo_files['values'] = []
            self.combo_files.set('')
            self.app.right_panel.log("작업 경로 내에 메타 파일(.csvmeta)이 없습니다.")

    def _load_meta(self):
        rel_path = self.combo_files.get()
        if not rel_path or not self.app.workspace_root: return
        filepath = os.path.join(self.app.target_dir, rel_path)

        if not os.path.exists(filepath):
            self.app.right_panel.log(f"❌ 파일을 찾을 수 없습니다: {filepath}")
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.meta_data = json.load(f)
        except Exception as e:
            self.app.right_panel.log(f"❌ 메타데이터 파싱 실패: {e}")
            return

        self._render_pk()
        self._render_fk()
        self.app.right_panel.log(f"▶ {rel_path} 메타 로드 완료")

    def _render_pk(self):
        s_keys = self.meta_data.get('superKeys', [])
        pk = self.meta_data.get('primaryKey', [])

        combo_vals = ["(없음)"] + [" + ".join(sk) for sk in s_keys]
        self.combo_pk['values'] = combo_vals

        if pk:
            pk_str = " + ".join(pk)
            if pk_str in combo_vals:
                self.combo_pk.set(pk_str)
            else:
                self.combo_pk.set("(없음)")
                self.app.right_panel.log("⚠️ 기존 PK가 현재 슈퍼키 목록에 없어 초기화되었습니다.")
        else:
            self.combo_pk.set("(없음)")

    def _render_fk(self):
        for w in self.fk_inner.winfo_children(): w.destroy()
        self.fk_builders.clear()

        fks = self.meta_data.get('foreignKeys', {})
        current_csv = self.combo_files.get().replace('.csvmeta', '.csv')

        for fk_name, fk_info in fks.items():
            b = ForeignKeyBuilder(self.fk_inner, self.app, current_csv, fk_name, fk_info.get('columns', []), fk_info.get('targetTable', ''))
            b.pack(fill="x", pady=5)
            self.fk_builders.append(b)

    def _add_fk_builder(self):
        current_csv = self.combo_files.get().replace('.csvmeta', '.csv')
        b = ForeignKeyBuilder(self.fk_inner, self.app, current_csv)
        b.pack(fill="x", pady=5)
        self.fk_builders.append(b)

    def _save_meta(self):
        rel_path = self.combo_files.get()
        if not rel_path or not self.app.workspace_root: return
        filepath = os.path.join(self.app.target_dir, rel_path)

        pk_val = self.combo_pk.get()
        if pk_val == "(없음)" or not pk_val:
            self.meta_data['primaryKey'] = []
        else:
            self.meta_data['primaryKey'] = [c.strip() for c in pk_val.split("+")]

        new_fks = {}
        active_builders = []
        
        for b in self.fk_builders:
            if not b.winfo_exists():
                continue
                
            active_builders.append(b)
            data = b.get_data()
            if not data:
                self.app.right_panel.log("⚠️ 매핑이 완료되지 않은 외래키 설정이 있어 무시되었습니다.")
                continue
            new_fks[data['name']] = {
                "columns": data['columns'],
                "targetTable": data['targetTable']
            }
            
        self.fk_builders = active_builders 
        self.meta_data['foreignKeys'] = new_fks

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.meta_data, f, ensure_ascii=False, indent=2)
            self.app.right_panel.log("✅ 메타데이터(PK/FK)가 성공적으로 갱신되었습니다!")
        except Exception as e:
            self.app.right_panel.log(f"❌ 저장 실패: {e}")
