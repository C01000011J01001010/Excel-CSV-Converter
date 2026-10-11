import tkinter as tk
from tkinter import ttk
import re
import os
import json
import csv

def parse_raw_header(header_str):
    name = str(header_str).strip()
    # 💡 [치명적 버그 수정] UTF-8 파일 맨 앞에 숨어있는 BOM(\ufeff) 문자를 완벽 제거
    name = name.lstrip('\ufeff') 
    
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1].strip()
        
    c_type = "string"
    if name.startswith('{') and name.endswith('}'):
        parts = [p.strip() for p in name[1:-1].split('/')]
        name = parts[0]
        if len(parts) > 1: c_type = parts[1].strip().lower()
    return name, c_type

def parse_constraint_string(c_str):
    c_str = c_str.strip()
    c_upper = c_str.upper()
    if c_upper == 'UNIQUE': return 'UNIQUE', None
    if c_upper == 'NOT NULL': return 'NOT NULL', None
    
    if c_upper.startswith('DEFAULT') and '(' in c_str:
        val = c_str[c_str.find('(')+1 : c_str.rfind(')')].strip()
        return 'DEFAULT', {'value': val}
        
    if c_upper.startswith('CHECK IN') and '(' in c_str:
        inner = c_str[c_str.find('(')+1 : c_str.rfind(')')]
        vals = [v.strip() for v in inner.split('|') if v.strip()]
        return 'CHECK IN', {'values': vals}
        
    if c_upper.startswith('CHECK NOT IN') and '(' in c_str:
        inner = c_str[c_str.find('(')+1 : c_str.rfind(')')]
        vals = [v.strip() for v in inner.split('|') if v.strip()]
        return 'CHECK NOT IN', {'values': vals}
        
    if c_upper.startswith('CHECK') and '(' in c_str:
        inner = c_str[c_str.find('(')+1 : c_str.rfind(')')].strip()
        tokens = re.split(r'\s+(AND|OR|XOR)\s+', inner, flags=re.IGNORECASE)
        conditions = []
        try:
            logic = ""
            for i in range(0, len(tokens), 2):
                expr = tokens[i].strip()
                if i > 0: logic = tokens[i-1].strip().upper()
                
                match = re.match(r'VALUE\s*(==|!=|>=|<=|>|<)\s*(.+)', expr, re.IGNORECASE)
                if match:
                    comp = match.group(1)
                    val = match.group(2).strip()
                    conditions.append({'logic': logic, 'comp': comp, 'val': val})
                else:
                    raise Exception("Parse fail")
            return 'CHECK', {'conditions': conditions}
        except: pass
    
    return 'RAW', {'value': c_str}

class ConstraintWidget(tk.Frame):
    def __init__(self, parent, c_type, init_data=None):
        super().__init__(parent, bg="#333333", bd=1, relief="solid")
        self.c_type = c_type
        
        top = tk.Frame(self, bg="#333333")
        top.pack(fill="x", padx=5, pady=2)
        tk.Label(top, text=c_type, bg="#333333", fg="#FFD700", font=("Consolas", 10, "bold")).pack(side="left")
        tk.Button(top, text="🗑️", bg="#DC3545", fg="white", bd=0, padx=5, pady=0, font=("맑은 고딕", 8), command=self.destroy).pack(side="right")
        
        self.content = tk.Frame(self, bg="#333333")
        self.content.pack(fill="x", padx=10, pady=(0,5))
        
        self.entries = []
        self.conditions = []
        
        if c_type == 'DEFAULT':
            e = tk.Entry(self.content, width=20, font=("Consolas", 10))
            e.pack(anchor="w")
            if init_data: e.insert(0, init_data.get('value', ''))
            self.entries.append(e)
            
        elif c_type in ['CHECK IN', 'CHECK NOT IN']:
            btn = tk.Button(self.content, text="+ 값 추가", bg="#555555", fg="white", bd=0, command=lambda: self.add_entry())
            btn.pack(anchor="w", pady=2)
            if init_data and init_data.get('values'):
                for v in init_data.get('values', []): self.add_entry(v)
            else:
                self.add_entry()
                
        elif c_type == 'CHECK':
            btn = tk.Button(self.content, text="+ 조건식 추가", bg="#555555", fg="white", bd=0, command=lambda: self.add_condition())
            btn.pack(anchor="w", pady=2)
            if init_data and init_data.get('conditions'):
                for c in init_data.get('conditions', []): self.add_condition(c)
            else:
                self.add_condition()
                
        elif c_type == 'RAW':
            e = tk.Entry(self.content, width=40, font=("Consolas", 10))
            e.pack(anchor="w")
            if init_data: e.insert(0, init_data.get('value', ''))
            self.entries.append(e)

    def add_entry(self, val=""):
        row = tk.Frame(self.content, bg="#333333")
        row.pack(fill="x", pady=2)
        e = tk.Entry(row, width=15, font=("Consolas", 10))
        e.insert(0, val)
        e.pack(side="left")
        tk.Button(row, text="X", bg="#DC3545", fg="white", bd=0, width=2, command=lambda r=row, ent=e: self.remove_entry(r, ent)).pack(side="left", padx=5)
        self.entries.append(e)
        
    def remove_entry(self, row, e):
        if e in self.entries: self.entries.remove(e)
        row.destroy()
        
    def add_condition(self, data=None):
        row = tk.Frame(self.content, bg="#333333")
        row.pack(fill="x", pady=2)
        
        is_first = len(self.conditions) == 0
        logic_cb = ttk.Combobox(row, values=["AND", "OR", "XOR"], state="readonly", width=5)
        logic_cb.set(data.get('logic', 'AND') if data and not is_first else "AND")
        if not is_first: logic_cb.pack(side="left", padx=(0, 5))
        
        tk.Label(row, text="VALUE", bg="#333333", fg="#00FF66", font=("Consolas", 10, "bold")).pack(side="left")
        comp_cb = ttk.Combobox(row, values=["==", "!=", ">", ">=", "<", "<="], state="readonly", width=4)
        comp_cb.set(data.get('comp', '==') if data else "==")
        comp_cb.pack(side="left", padx=5)
        
        val_e = tk.Entry(row, width=10, font=("Consolas", 10))
        if data: val_e.insert(0, data.get('val', ''))
        val_e.pack(side="left", padx=5)
        
        tk.Button(row, text="X", bg="#DC3545", fg="white", bd=0, width=2, command=lambda r=row, cond=(logic_cb, comp_cb, val_e): self.remove_condition(r, cond)).pack(side="left")
        self.conditions.append((logic_cb, comp_cb, val_e))
        
    def remove_condition(self, row, cond):
        if cond in self.conditions: self.conditions.remove(cond)
        row.destroy()
        
    def get_value(self):
        if self.c_type in ['UNIQUE', 'NOT NULL']: return self.c_type
        elif self.c_type == 'DEFAULT': return f"DEFAULT({self.entries[0].get()})"
        elif self.c_type in ['CHECK IN', 'CHECK NOT IN']:
            vals = [e.get() for e in self.entries if e.get().strip()]
            if not vals: return None
            return f"{self.c_type}({'|'.join(vals)})"
        elif self.c_type == 'CHECK':
            conds = []
            for i, (l, c, v) in enumerate(self.conditions):
                val = v.get().strip()
                if not val: continue
                if i == 0: conds.append(f"VALUE {c.get()} {val}")
                else: conds.append(f" {l.get()} VALUE {c.get()} {val}")
            if not conds: return None
            return f"CHECK({''.join(conds)})"
        elif self.c_type == 'RAW':
            val = self.entries[0].get().upper()
            if 'PK' in val or 'REF' in val or 'PRIMARYKEY' in val or 'REFERENCE' in val: return None 
            return self.entries[0].get()

class ColumnConstraintBuilder(tk.Frame):
    def __init__(self, parent, col_name, col_type, constraints_list):
        super().__init__(parent, bg="#252526", bd=1, relief="solid")
        self.col_name = col_name
        self.col_type = col_type
        
        header = tk.Frame(self, bg="#252526")
        header.pack(fill="x", padx=10, pady=5)
        tk.Label(header, text=f"■ {col_name}", bg="#252526", fg="#00FF66", font=("맑은 고딕", 11, "bold")).pack(side="left")
        if col_type:
            tk.Label(header, text=f"({col_type})", bg="#252526", fg="#CCCCCC", font=("Consolas", 10)).pack(side="left", padx=5)
        
        add_frame = tk.Frame(header, bg="#252526")
        add_frame.pack(side="right")
        self.lbl_error = tk.Label(add_frame, text="", bg="#252526", fg="#FF5555", font=("맑은 고딕", 9, "bold"))
        self.lbl_error.pack(side="left", padx=10)
        
        self.cb_type = ttk.Combobox(add_frame, values=["UNIQUE", "NOT NULL", "DEFAULT", "CHECK", "CHECK IN", "CHECK NOT IN"], state="readonly", width=12)
        self.cb_type.set("UNIQUE")
        self.cb_type.pack(side="left", padx=5)
        tk.Button(add_frame, text="+ 제약조건 추가", bg="#007ACC", fg="white", bd=0, font=("맑은 고딕", 9), command=self.add_new).pack(side="left")
        
        self.c_container = tk.Frame(self, bg="#252526")
        self.c_container.pack(fill="x", padx=10, pady=(0, 10))
        
        for c_str in constraints_list:
            ctype, cdata = parse_constraint_string(c_str)
            if ctype in ['PK', 'REF']: continue
            self.add_widget(ctype, cdata)
            
    def show_error(self, msg):
        self.lbl_error.config(text=f"❌ {msg}")
        self.after(3000, lambda: self.lbl_error.config(text=""))
            
    def add_new(self):
        new_type = self.cb_type.get()
        current_types = [child.c_type for child in self.c_container.winfo_children() if isinstance(child, ConstraintWidget)]
        
        if new_type in current_types:
            self.show_error("동일 제약조건 존재")
            return
        if new_type == "UNIQUE" and "DEFAULT" in current_types:
            self.show_error("UNIQUE와 DEFAULT 공존불가")
            return
        if new_type == "DEFAULT" and "UNIQUE" in current_types:
            self.show_error("UNIQUE와 DEFAULT 공존불가")
            return
            
        self.lbl_error.config(text="")
        self.add_widget(new_type, None)
        
    def add_widget(self, ctype, cdata):
        cw = ConstraintWidget(self.c_container, ctype, cdata)
        cw.pack(side="top", fill="x", pady=2)
        
    def get_constraints(self):
        current_types = [c.c_type for c in self.c_container.winfo_children() if isinstance(c, ConstraintWidget)]
        if "UNIQUE" in current_types and "DEFAULT" in current_types:
            self.show_error("저장 불가: UNIQUE & DEFAULT")
            return None
        if len(current_types) != len(set(current_types)):
            self.show_error("저장 불가: 중복 제약조건")
            return None

        res = []
        for child in self.c_container.winfo_children():
            if isinstance(child, ConstraintWidget):
                val = child.get_value()
                if val: res.append(val)
        return res

class ForeignKeyBuilder(tk.Frame):
    def __init__(self, parent, app, current_file, fk_name="", columns=None, target_table=""):
        super().__init__(parent, bg="#252526", bd=1, relief="solid")
        self.app = app
        self.current_file = current_file
        self.mapped_cols = columns if columns else []
        self.target_pk_info = []
        self.local_col_combos = []
        
        r1 = tk.Frame(self, bg="#252526")
        r1.pack(fill="x", padx=10, pady=10)
        
        tk.Label(r1, text="객체명(Name):", bg="#252526", fg="#CCCCCC", font=("맑은 고딕", 9)).pack(side="left")
        self.ent_name = tk.Entry(r1, width=20, font=("Consolas", 10), bg="#1E1E1E", fg="white", insertbackground="white")
        self.ent_name.insert(0, fk_name)
        self.ent_name.pack(side="left", padx=5)
        
        tk.Label(r1, text="타겟 테이블 (Workspace 內):", bg="#252526", fg="#CCCCCC", font=("맑은 고딕", 9)).pack(side="left", padx=(15, 5))
        self.cb_target = ttk.Combobox(r1, state="readonly", width=30, font=("Consolas", 10))
        self.cb_target.pack(side="left")
        
        btn_del = tk.Button(r1, text="🗑️ 삭제", bg="#DC3545", fg="white", bd=0, padx=8, command=self.destroy)
        btn_del.pack(side="right", padx=5)
        
        self.r2 = tk.Frame(self, bg="#252526")
        self.r2.pack(fill="x", padx=10, pady=(0, 10))
        
        tk.Label(self.r2, text="로컬 매핑 컬럼:", bg="#252526", fg="#CCCCCC", font=("맑은 고딕", 9)).pack(side="left", anchor="n")
        self.mapping_frame = tk.Frame(self.r2, bg="#252526")
        self.mapping_frame.pack(side="left", fill="x", expand=True, padx=10)
        
        self.cb_target.bind('<Button-1>', self._refresh_target_list)
        self.cb_target.bind('<<ComboboxSelected>>', self._on_target_selected)
        
        self._refresh_target_list(None)
        if target_table:
            self.cb_target.set(target_table)
            self._load_target_mapping(target_table, self.mapped_cols)
            
    def _refresh_target_list(self, event):
        if not self.app.workspace_root: return
        csv_files = []
        prefix = self.app.exclude_prefix_var.get().strip() or "Disabled"
        for root, dirs, files in os.walk(self.app.target_dir):
            if any(p.startswith(prefix) for p in root.replace('\\', '/').split('/')): continue
            for file in files:
                if file.startswith(prefix): continue
                if file.endswith('.csv'):
                    rel_path = os.path.relpath(os.path.join(root, file), self.app.target_dir).replace('\\', '/')
                    csv_files.append(rel_path)
        self.cb_target['values'] = csv_files

    def _on_target_selected(self, event):
        target_file = self.cb_target.get()
        self._load_target_mapping(target_file, [])
        
    def _load_target_mapping(self, target_file, pre_mapped_cols):
        for w in self.mapping_frame.winfo_children(): w.destroy()
        self.local_col_combos.clear()
        
        if not target_file: return
        
        target_csv_path = os.path.join(self.app.target_dir, target_file)
        target_meta_path = os.path.splitext(target_csv_path)[0] + ".csvmeta"
        
        target_pks = []
        if os.path.exists(target_meta_path):
            try:
                with open(target_meta_path, 'r', encoding='utf-8') as f:
                    jdata = json.load(f)
                    target_pks = jdata.get('primaryKey', [])
            except: pass
            
        if not target_pks:
            tk.Label(self.mapping_frame, text="⚠️ 타겟 테이블에 설정된 기본키(PK)가 없습니다.", bg="#252526", fg="#FF5555", font=("맑은 고딕", 9)).pack(anchor="w", pady=2)
            return
            
        pk_types = {}
        if os.path.exists(target_csv_path):
            try:
                # 💡 [치명적 버그 수정] csv 모듈과 utf-8-sig를 사용하여 CSV 구조와 BOM을 완벽히 파싱
                with open(target_csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    headers = next(reader)
                    for h in headers:
                        cname, ctype = parse_raw_header(h)
                        if cname in target_pks: pk_types[cname] = ctype
            except: pass
            
        local_col_types = {}
        current_csv_path = os.path.join(self.app.target_dir, self.current_file)
        if os.path.exists(current_csv_path):
            try:
                # 💡 [치명적 버그 수정] csv 모듈과 utf-8-sig를 사용하여 CSV 구조와 BOM을 완벽히 파싱
                with open(current_csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    headers = next(reader)
                    for h in headers:
                        cname, ctype = parse_raw_header(h)
                        local_col_types[cname] = ctype
            except: pass
            
        for i, pk_col in enumerate(target_pks):
            ptype = pk_types.get(pk_col, "string")
            
            matched_local_cols = [c for c, t in local_col_types.items() if t == ptype]
            
            row = tk.Frame(self.mapping_frame, bg="#252526")
            row.pack(fill="x", pady=2)
            
            tk.Label(row, text=f"참조 대상: '{pk_col}' ({ptype})   ➔   내 컬럼:", bg="#252526", fg="#FFD700", font=("Consolas", 10)).pack(side="left")
            
            cb = ttk.Combobox(row, values=matched_local_cols, state="readonly", width=25, font=("Consolas", 10))
            cb.pack(side="left", padx=10)
            
            if i < len(pre_mapped_cols) and pre_mapped_cols[i] in matched_local_cols:
                cb.set(pre_mapped_cols[i])
            elif pk_col in matched_local_cols:
                cb.set(pk_col)
                
            self.local_col_combos.append(cb)
            
    def get_data(self):
        name = self.ent_name.get().strip()
        target = self.cb_target.get().strip()
        if not name or not target: return None
        
        cols = []
        for cb in self.local_col_combos:
            val = cb.get()
            if not val: return None
            cols.append(val)
            
        if not cols: return None
        
        return {
            "name": name,
            "columns": cols,
            "targetTable": target
        }
