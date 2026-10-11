import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
from gui.widgets import ScrollableFrame
from gui.constraint_builder import ColumnConstraintBuilder
from gui.meta_editor import MetaEditorTab
from core.excel_editor import get_excel_files, read_headers, write_headers

class LeftPanel(tk.Frame):
    def __init__(self, parent, app, *args, **kwargs):
        super().__init__(parent, bg="#1E1E1E", *args, **kwargs)
        self.app = app
        self.parsed_headers = []

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tab2 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab2, text="1. CSV 변환")
        self._build_tab2()

        self.tab1 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab1, text="2. 스키마/제약조건")
        self._build_tab1()
        
        self.tab3 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab3, text="3. 메타(슈퍼키) 추출")
        self._build_tab3()

        self.tab4 = MetaEditorTab(self.notebook, self.app)
        self.notebook.add(self.tab4, text="4. 메타 관리(PK/FK)")

        self.tab5 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab5, text="5. 전체 무결성 검증")
        self._build_tab5()

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        current_idx = self.notebook.index("current")
        if current_idx > 0:
            if not self.app.watcher.is_watching:
                messagebox.showwarning("안내", "DB 설계 및 검증 기능을 사용하려면\n먼저 [1. CSV 변환] 탭에서 '백그라운드 자동 변환 모드'를 켜주세요.")
                self.notebook.select(0)

    def _parse_raw_header(self, header_str):
        name = header_str
        c_type = ""
        constraints = []
        if header_str.startswith('{') and header_str.endswith('}'):
            parts = [p.strip() for p in header_str[1:-1].split('/')]
            name = parts[0]
            if len(parts) > 1: c_type = parts[1]
            if len(parts) > 2: constraints = parts[2:]
        return name, c_type, constraints

    def _build_tab1(self):
        top_frame = tk.Frame(self.tab1, bg="#1E1E1E")
        top_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(top_frame, text="대상 엑셀 파일 선택:", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        self.t1_combo_files = ttk.Combobox(top_frame, state="readonly", width=60)
        self.t1_combo_files.pack(side="left", padx=10, fill="x", expand=True)
        
        btn_refresh = tk.Button(top_frame, text="새로고침", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self._t1_refresh_files)
        btn_refresh.pack(side="left", padx=2)
        btn_load = tk.Button(top_frame, text="헤더 로드", font=("맑은 고딕", 9, "bold"), bg="#007ACC", fg="white", bd=0, command=self._t1_load_headers)
        btn_load.pack(side="left", padx=2)

        # 💡 [NEW] 스키마 범위 안내 툴팁 추가
        guide_frame = tk.Frame(self.tab1, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(0, 5))
        guide_text = "📌 [안내] `{}` 기호가 포함된 최초의 행/열부터 마지막 `{}` 열까지만 스키마와 데이터로 인식합니다. (바깥 여백 및 메모 무시)"
        tk.Label(guide_frame, text=guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=5).pack(fill="x")

        self.sub_notebook = ttk.Notebook(self.tab1)
        self.sub_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.sub_tab1 = tk.Frame(self.sub_notebook, bg="#1E1E1E")
        self.sub_notebook.add(self.sub_tab1, text="1.1 타입 설정")
        self._build_sub_tab1()
        
        self.sub_tab2 = tk.Frame(self.sub_notebook, bg="#1E1E1E")
        self.sub_notebook.add(self.sub_tab2, text="1.2 제약조건 설정")
        self._build_sub_tab2()

    def _build_sub_tab1(self):
        sf = ScrollableFrame(self.sub_tab1)
        sf.pack(fill="both", expand=True)
        self.t1_1_inner = sf.inner_frame
        
        self.t1_1_rows_frame = tk.Frame(self.t1_1_inner, bg="#252526", bd=1, relief="solid")
        self.t1_1_rows_frame.pack(fill="x", padx=10, pady=10)
        self.t1_1_row_widgets = []
        
        btn_frame = tk.Frame(self.t1_1_inner, bg="#1E1E1E")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(btn_frame, text="+ 새 컬럼 추가", font=("맑은 고딕", 10), bg="#444444", fg="white", bd=0, command=self._t1_1_add_row).pack(side="left")
        tk.Button(btn_frame, text="✅ 엑셀에 스키마(타입) 저장", font=("맑은 고딕", 10, "bold"), bg="#28A745", fg="white", bd=0, command=self._t1_1_save_headers).pack(side="right")

    def _build_sub_tab2(self):
        sf = ScrollableFrame(self.sub_tab2)
        sf.pack(fill="both", expand=True)
        self.t1_2_inner = sf.inner_frame
        
        self.t1_2_rows_frame = tk.Frame(self.t1_2_inner, bg="#1E1E1E")
        self.t1_2_rows_frame.pack(fill="x", padx=10, pady=10)
        self.t1_2_row_widgets = []
        
        btn_frame = tk.Frame(self.t1_2_inner, bg="#1E1E1E")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(btn_frame, text="✅ 엑셀에 제약조건 적용 및 저장", font=("맑은 고딕", 10, "bold"), bg="#E67E22", fg="white", bd=0, command=self._t1_2_save_headers).pack(side="right")

    def _t1_refresh_files(self):
        if not self.app.workspace_root:
            self.app.right_panel.log("⚠️ 워크스페이스가 설정되지 않았습니다.")
            return
        
        prefix = self.app.exclude_prefix_var.get().strip() or "Disabled"
        files = get_excel_files(self.app.target_dir, self.app.include_subdirs.get(), prefix)
        if files:
            self.t1_combo_files['values'] = files
            self.t1_combo_files.current(0)
            self.app.right_panel.log(f"작업 경로 내 엑셀 파일 {len(files)}개 스캔 완료.")
        else:
            self.t1_combo_files['values'] = []
            self.t1_combo_files.set('')
            self.app.right_panel.log("작업 경로 내에 발견된 엑셀 파일이 없습니다.")

    def _t1_load_headers(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path or not self.app.workspace_root: return
        filepath = os.path.join(self.app.target_dir, rel_path)
        
        success, data = read_headers(filepath)
        if not success:
            self.app.right_panel.log(f"❌ 헤더 로드 실패: {data}")
            return
            
        self.parsed_headers = []
        for h in data:
            if not h: continue
            c_name, c_type, constraints = self._parse_raw_header(h)
            constraints = [c for c in constraints if c.upper() not in ['PK', 'PRIMARYKEY', 'REF', 'REFERENCE']]
            self.parsed_headers.append({'name': c_name, 'type': c_type, 'constraints': constraints})
            
        self._render_tab1_1()
        self._render_tab1_2()
        self.app.right_panel.log(f"▶ {rel_path} 스키마 로드 완료")

    def _render_tab1_1(self):
        for w in self.t1_1_rows_frame.winfo_children(): w.destroy()
        self.t1_1_row_widgets.clear()
        tk.Label(self.t1_1_rows_frame, text="컬럼명", width=20, bg="#252526", fg="#00FF66", font=("맑은 고딕", 9, "bold")).grid(row=0, column=0, pady=5)
        tk.Label(self.t1_1_rows_frame, text="타입 선택", width=20, bg="#252526", fg="#00FF66", font=("맑은 고딕", 9, "bold")).grid(row=0, column=1, pady=5)
        for d in self.parsed_headers:
            self._t1_1_create_row(d['name'], d['type'])

    def _t1_1_create_row(self, name="", ctype=""):
        row_idx = len(self.t1_1_row_widgets) + 1
        ent_name = tk.Entry(self.t1_1_rows_frame, font=("Consolas", 10), bg="#1E1E1E", fg="white", insertbackground="white", width=25)
        ent_name.insert(0, name)
        ent_name.grid(row=row_idx, column=0, padx=5, pady=2)
        
        combo_type = ttk.Combobox(self.t1_1_rows_frame, state="readonly", width=20, 
                                  values=["int", "int[]", "float", "float[]", "string", "string[]", "bool", "bool[]", "enum", "enum[]", "AssetID", "AssetID[]"])
        if ctype: 
            if ctype.lower() == "assetid": ctype = "AssetID"
            elif ctype.lower() == "assetid[]": ctype = "AssetID[]"
            combo_type.set(ctype)
            
        combo_type.grid(row=row_idx, column=1, padx=5, pady=2)
        self.t1_1_row_widgets.append((ent_name, combo_type))

    def _t1_1_add_row(self):
        self._t1_1_create_row()
        
    def _t1_1_save_headers(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path or not self.app.workspace_root: return
        filepath = os.path.join(self.app.target_dir, rel_path)
        
        new_headers = []
        for i, (ent_name, combo_type) in enumerate(self.t1_1_row_widgets):
            name = ent_name.get().strip()
            ctype = combo_type.get().strip()
            if not name: continue
            
            existing_constraints = []
            if i < len(self.parsed_headers):
                existing_constraints = self.parsed_headers[i]['constraints']
                
            if ctype and existing_constraints:
                new_headers.append(f"{{{name}/{ctype}/{'/'.join(existing_constraints)}}}")
            elif ctype:
                new_headers.append(f"{{{name}/{ctype}}}")
            else:
                new_headers.append(f"{{{name}}}")
                
        success, msg = write_headers(filepath, new_headers)
        if success:
            self.app.right_panel.log(f"✅ 스키마 반영 완료.")
            self._t1_load_headers()
        else:
            self.app.right_panel.log(f"❌ 저장 실패: {msg}")

    def _render_tab1_2(self):
        for w in self.t1_2_rows_frame.winfo_children(): w.destroy()
        self.t1_2_row_widgets.clear()
        
        for d in self.parsed_headers:
            builder = ColumnConstraintBuilder(self.t1_2_rows_frame, d['name'], d['type'], d['constraints'])
            builder.pack(fill="x", pady=5)
            self.t1_2_row_widgets.append(builder)

    def _t1_2_save_headers(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path or not self.app.workspace_root: return
        filepath = os.path.join(self.app.target_dir, rel_path)
        
        new_headers = []
        for i, builder in enumerate(self.t1_2_row_widgets):
            name = builder.col_name
            ctype = builder.col_type
            constraints = builder.get_constraints()
            
            if constraints is None:
                self.app.right_panel.log(f"❌ '{name}' 제약조건 모순. 저장 취소.")
                return
            
            parts = [name]
            if ctype: parts.append(ctype)
            parts.extend(constraints)
            new_headers.append("{" + "/".join(parts) + "}")
            
        success, msg = write_headers(filepath, new_headers)
        if success:
            self.app.right_panel.log(f"✅ 제약조건 반영 완료.")
            self._t1_load_headers()

    def _build_tab2(self):
        scroll_frame = ScrollableFrame(self.tab2)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner_frame
        
        # 💡 [NEW] CSV 변환 탭 변환 범위 안내 툴팁
        guide_frame = tk.Frame(inner, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(15, 10))
        guide_text = "📌 [파싱 범위 안내]\n\n엑셀 문서에서 `{}` 기호가 처음 시작되는 행과 열부터 마지막 `{}` 열 사이의 데이터만\n유효한 스키마(바운딩 박스) 영역으로 자동 크롭(Crop)되어 CSV로 변환됩니다."
        tk.Label(guide_frame, text=guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=10).pack(fill="x")
        
        self.app.btn1 = tk.Button(inner, text="엑셀 ➔ CSV 전체 변환 (현재 작업 경로 내)", font=("맑은 고딕", 11, "bold"), bg="#007ACC", fg="white", bd=0, height=2, command=self.app.run_xlsx_to_csv_all)
        self.app.btn1.pack(fill="x", padx=10, pady=10)
        
        self.app.btn2 = tk.Button(inner, text="CSV ➔ UTF-8 변환 (현재 작업 경로 내)", font=("맑은 고딕", 11, "bold"), bg="#28A745", fg="white", bd=0, height=2, command=self.app.run_ansi_to_utf8_all)
        self.app.btn2.pack(fill="x", padx=10, pady=5)
        
        self.app.btn3 = tk.Button(inner, text="백그라운드 자동 변환 모드 시작", font=("맑은 고딕", 11, "bold"), bg="#6C757D", fg="white", bd=0, height=2, command=self.app.toggle_watch_mode)
        self.app.btn3.pack(fill="x", padx=10, pady=5)

    def _build_tab3(self):
        scroll_frame = ScrollableFrame(self.tab3)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner_frame

        guide_frame = tk.Frame(inner, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(15, 10))
        
        # 💡 [FIX] 3번 탭 툴팁 및 확장자, 설명 수정
        guide_text = "📌 [메타데이터 (슈퍼키) 추출]\n\n배열([])과 float 타입을 배제하고 고유하게 식별 가능한 모든 슈퍼키 조합을 추출하여 JSON 포맷의 .csvmeta 파일로 저장합니다.\n\n※ 엑셀 스키마에 제약조건 \"UNIQUE\"와 \"NOT NULL\"이 동시에 적용된 컬럼을 포함하고 있는 키조합은 내부 유일성 검사 목록에서 제외됩니다.\n    (즉시 슈퍼키로 확정 - Fast Track)"
        tk.Label(guide_frame, text=guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=10).pack(fill="x")

        opt_frame2 = tk.Frame(inner, bg="#1E1E1E")
        opt_frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(opt_frame2, text="최대 슈퍼키 조합 길이 (연산량 조절용):", font=("맑은 고딕", 10), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        tk.Spinbox(opt_frame2, from_=1, to=10, textvariable=self.app.max_combo_var, width=5, font=("Consolas", 10)).pack(side="left", padx=10)

        # 💡 [FIX] 버튼 텍스트 수정 (.csvmeta 명시)
        self.app.btn4 = tk.Button(inner, text="메타데이터(슈퍼키) 자동 추출 및 .csvmeta 갱신 (현재 경로)", font=("맑은 고딕", 11, "bold"), bg="#9C27B0", fg="white", bd=0, height=3, command=self.app.run_super_key_finder)
        self.app.btn4.pack(fill="x", padx=10, pady=10)

        self.app.progress_bar = ttk.Progressbar(inner, variable=self.app.progress_var, maximum=100)
        self.app.progress_bar.pack(fill="x", padx=10, pady=(0, 10))

    def _build_tab5(self):
        scroll_frame = ScrollableFrame(self.tab5)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner_frame

        guide_frame = tk.Frame(inner, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(15, 10))
        
        guide_text = (
            "🛡️ [전체 데이터베이스 무결성 검증]\n\n"
            "워크스페이스(Root) 전체를 대상으로 RDBMS 수준의 5대 무결성을 교차 검증합니다.\n\n"
            "1. 개체 무결성 : 기본키(PK)의 중복 및 빈 칸(Null) 존재 여부\n"
            "2. 참조 무결성 : 외래키(FK)가 가리키는 대상이 실제로 존재하는지 교차 확인\n"
            "3. 도메인 무결성: 데이터 타입의 형식 일치 여부\n"
            "4. 고유 무결성 : UNIQUE 제약조건 위반 여부\n"
            "5. Null 무결성 : NOT NULL 제약조건 위반 여부\n\n"
            "※ 검증 전, 모든 파일의 [메타 추출] 및 [PK 설정]이 완료되어야 합니다."
        )
        tk.Label(guide_frame, text=guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=10).pack(fill="x")

        self.app.btn_validate = tk.Button(inner, text="데이터베이스 전체 무결성 글로벌 검증 시작", font=("맑은 고딕", 12, "bold"), bg="#DC3545", fg="white", bd=0, height=3, command=self.app.run_global_validation)
        self.app.btn_validate.pack(fill="x", padx=10, pady=10)
