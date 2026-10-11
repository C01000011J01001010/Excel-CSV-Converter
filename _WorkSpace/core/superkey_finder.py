import os
import json
import pandas as pd
from itertools import combinations

def parse_header(raw_str):
    name = str(raw_str).strip()
    c_type = ""
    constraints = []
    if name.startswith('{') and name.endswith('}'):
        parts = [p.strip() for p in name[1:-1].split('/')]
        name = parts[0]
        if len(parts) > 1: c_type = parts[1].strip()
        if len(parts) > 2: constraints = [p.strip() for p in parts[2:]]
    return name, c_type, constraints

def find_super_keys(target_dir, max_combo, include_subdirs, on_log, on_progress, exclude_prefix="Disabled"):
    csv_files = []
    for root, dirs, files in os.walk(target_dir):
        if any(p.startswith(exclude_prefix) for p in root.replace('\\', '/').split('/')): continue
        if not include_subdirs and root != target_dir: continue
        for file in files:
            if file.startswith(exclude_prefix): continue
            if file.endswith('.csv'):
                csv_files.append(os.path.join(root, file))

    if not csv_files:
        on_log("❌ 작업 경로 내에 스캔할 CSV 파일이 없습니다.")
        return

    total_files = len(csv_files)
    for i, csv_file in enumerate(csv_files):
        rel_path = os.path.relpath(csv_file, target_dir)
        # 💡 [FIX] .json -> .csvmeta 확장자로 완벽 변경
        json_file = os.path.splitext(csv_file)[0] + ".csvmeta"
        
        try:
            try: df = pd.read_csv(csv_file, encoding='utf-8')
            except UnicodeDecodeError: df = pd.read_csv(csv_file, encoding='cp949')
        except Exception as e:
            on_log(f"⚠️ {rel_path} 읽기 실패: {e}")
            continue

        rename_map = {}
        col_types = {}
        col_constraints = {}
        for c in df.columns:
            c_name, c_type, constraints = parse_header(c)
            rename_map[c] = c_name
            col_types[c_name] = c_type.lower()
            col_constraints[c_name] = [x.upper() for x in constraints]
        df = df.rename(columns=rename_map)

        eligible_cols = []
        fast_track_cols = set()

        for c_name in df.columns:
            c_type = col_types.get(c_name, "")
            if '[]' in c_type or 'float' in c_type: continue
            if c_type not in ['int', 'string', 'bool', 'enum', 'assetid']: continue
            if df[c_name].isna().any(): continue
            eligible_cols.append(c_name)
            
            if 'UNIQUE' in col_constraints.get(c_name, []) and 'NOT NULL' in col_constraints.get(c_name, []):
                fast_track_cols.add(c_name)

        super_keys = []
        for r in range(1, min(max_combo, len(eligible_cols)) + 1):
            for combo in combinations(eligible_cols, r):
                combo = list(combo)
                if fast_track_cols.intersection(set(combo)):
                    super_keys.append(combo)
                    continue
                if not df.duplicated(subset=combo).any():
                    super_keys.append(combo)

        super_keys.sort(key=len)

        meta_data = {}
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    meta_data = json.load(f)
            except: pass
            
        if 'candidateKeys' in meta_data: del meta_data['candidateKeys']
            
        meta_data['superKeys'] = super_keys
        if 'primaryKey' not in meta_data: meta_data['primaryKey'] = []
        if 'foreignKeys' not in meta_data: meta_data['foreignKeys'] = {}
        
        pk = meta_data.get('primaryKey', [])
        pk_valid = False
        if pk:
            for sk in super_keys:
                if set(pk) == set(sk):
                    pk_valid = True
                    break
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
            
        log_msg = f"✅ {rel_path} ➔ 슈퍼키 {len(super_keys)}개 추출 완료"
        if fast_track_cols: log_msg += f" (Fast-Track: {len(fast_track_cols)}개 컬럼 적용)"
        if pk and not pk_valid: log_msg += f" (⚠️ 기존 PK {pk}가 더 이상 유효한 조합이 아님!)"
        on_log(log_msg)
        on_progress(int((i + 1) / total_files * 100))

    on_log("\n🎉 모든 메타데이터 슈퍼키(.csvmeta) 추출 및 갱신이 완료되었습니다!")
