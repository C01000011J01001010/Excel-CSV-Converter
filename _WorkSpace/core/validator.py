import os
import json
import pandas as pd
import numpy as np
import re

def parse_header(raw_str):
    name = str(raw_str).strip()
    c_type = ""
    constraints = []
    is_schema = False
    if name.startswith('{') and name.endswith('}'):
        is_schema = True
        parts = [p.strip() for p in name[1:-1].split('/')]
        name = parts[0]
        if len(parts) > 1: c_type = parts[1].strip()
        if len(parts) > 2: constraints = [p.strip() for p in parts[2:]]
    return name, c_type, constraints, is_schema

def check_type(data_series, c_type_base):
    data_str = data_series.astype(str).str.strip()
    if c_type_base in ['int', 'assetid']: return data_str.str.match(r'^-?\d+$')
    elif c_type_base == 'float': return data_str.str.match(r'^-?\d+(\.\d+)?$')
    elif c_type_base == 'bool': return data_str.str.lower().isin(['true', 'false', '0', '1', '0.0', '1.0'])
    elif c_type_base in ['string', 'enum']: return pd.Series([True]*len(data_series), index=data_series.index)
    return pd.Series([False]*len(data_series), index=data_series.index)

def evaluate_check_expr(val, expr):
    try:
        val_str = str(val).strip()
        try:
            numeric_val = float(val_str)
            py_expr = expr.upper().replace("VALUE", str(numeric_val)).replace("AND", " and ").replace("OR", " or ")
        except ValueError:
            py_expr = expr.upper().replace("VALUE", f"'{val_str}'").replace("AND", " and ").replace("OR", " or ")
        if any(unsafe in py_expr.lower() for unsafe in ['import', 'exec', 'eval', 'os', 'sys']): return False
        return bool(eval(py_expr))
    except: return False

def format_errors(invalid_series, limit=3):
    total = len(invalid_series)
    items = []
    for idx, val in invalid_series.head(limit).items():
        row_num = idx + 2 
        items.append(f"{{행{row_num}: '{val}'}}")
    res = "[" + ", ".join(items) + "]"
    if total > limit: res += f" (외 {total - limit}건)"
    return res

def run_global_validation(workspace_root, on_log, on_progress, exclude_prefix="Disabled"):
    csv_files = []
    for root, dirs, files in os.walk(workspace_root):
        if any(p.startswith(exclude_prefix) for p in root.replace('\\', '/').split('/')): continue
        for file in files:
            if file.startswith(exclude_prefix): continue
            if file.endswith('.csv'):
                csv_files.append(os.path.join(root, file))

    if not csv_files:
        on_log("❌ 워크스페이스 내에 검증할 CSV 파일이 없습니다.")
        return

    on_log("🔍 1단계: 메타데이터(.csvmeta) 및 기본키(PK) 설정 여부 확인 중...")
    missing_meta = []
    missing_pk = []
    meta_dict = {}
    df_dict = {}

    for csv_file in csv_files:
        json_file = os.path.splitext(csv_file)[0] + ".csvmeta"
        base_name = os.path.basename(csv_file)
        
        if not os.path.exists(json_file):
            missing_meta.append(base_name)
            continue
            
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                if not meta.get('primaryKey'): missing_pk.append(base_name)
                else: meta_dict[base_name] = meta
        except Exception:
            missing_meta.append(base_name)

    if missing_meta or missing_pk:
        on_log("\n🚨 [검증 중단] 유효한 메타데이터가 없는 테이블이 발견되었습니다.")
        on_log("다음 파일들은 [3. 추출] 및 [4. 메타 관리] 탭에서 기본키(PK)를 먼저 설정해야 무결성 검사가 가능합니다.\n")
        for f in missing_meta: on_log(f" ❌ {f} (.csvmeta 메타파일 누락 또는 파싱 실패)")
        for f in missing_pk: on_log(f" ❌ {f} (기본키 미설정)")
        return

    on_log("✅ 모든 테이블의 메타데이터 확인 완료. 데이터 로드 시작...\n")
    on_progress(20)
    
    file_errors = {}
    
    for csv_file in csv_files:
        base_name = os.path.basename(csv_file)
        if base_name not in meta_dict: continue
        file_errors[base_name] = [] 
        
        try:
            # 💡 [핵심 버그 수정] dtype=str 을 통해 Pandas가 멋대로 .0 을 붙이는 현상 완벽 방어!
            try: df = pd.read_csv(csv_file, encoding='utf-8-sig', dtype=str)
            except UnicodeDecodeError: df = pd.read_csv(csv_file, encoding='cp949', dtype=str)
            
            rename_map = {}
            col_info = {}
            for c in df.columns:
                c_name, c_type, constraints, is_schema = parse_header(c)
                rename_map[c] = c_name
                col_info[c_name] = {'type': c_type, 'constraints': constraints, 'raw': c, 'is_schema': is_schema}
            
            df = df.rename(columns=rename_map)
            df_dict[base_name] = {'df': df, 'info': col_info, 'meta': meta_dict[base_name]}
        except Exception as e:
            on_log(f"❌ {base_name} 데이터 로드 실패: {e}")
            return

    on_progress(40)
    total_errors = 0
    on_log("🔍 2단계: 개체, 고유, Null, 도메인, 참조 무결성 통합 검사 가동 중...")
    
    for t_name, t_data in df_dict.items():
        df = t_data['df']
        info = t_data['info']
        meta = t_data['meta']
        
        pk_cols = meta['primaryKey']
        missing_in_df = [p for p in pk_cols if p not in df.columns]
        if missing_in_df:
            file_errors[t_name].append(f"[개체 무결성] PK 컬럼 {missing_in_df} 데이터 누락")
            total_errors += 1
        else:
            pk_null_mask = df[pk_cols].isna().any(axis=1)
            if pk_null_mask.any():
                invalid_series = pd.Series(["NULL"] * pk_null_mask.sum(), index=df[pk_null_mask].index)
                file_errors[t_name].append(f"[개체 무결성] 기본키({pk_cols}) 빈 칸(NULL) 존재 ➔ {format_errors(invalid_series)}")
                total_errors += 1
                
            pk_dup_mask = df.duplicated(subset=pk_cols, keep=False)
            if pk_dup_mask.any():
                invalid_df = df[pk_dup_mask][pk_cols]
                invalid_series = pd.Series([", ".join(x.astype(str)) for x in invalid_df.to_numpy()], index=invalid_df.index)
                file_errors[t_name].append(f"[개체 무결성] 기본키({pk_cols}) 중복 ➔ {format_errors(invalid_series)}")
                total_errors += 1

        for c_name, c_dict in info.items():
            if c_name not in df.columns: continue
            if not c_dict.get('is_schema', False): continue

            c_data = df[c_name]
            constraints = c_dict['constraints']
            c_type_full = c_dict['type']
            
            if not c_type_full:
                file_errors[t_name].append(f"[도메인 무결성] '{c_name}' 컬럼 타입 미지정")
                total_errors += 1
                continue
                
            c_type_base = c_type_full.replace('[]', '').lower()
            is_array = '[]' in c_type_full
            valid_types = ['int', 'float', 'string', 'bool', 'enum', 'assetid']
            
            if c_type_base not in valid_types:
                file_errors[t_name].append(f"[도메인 무결성] '{c_name}' 알 수 없는 타입('{c_type_full}')")
                total_errors += 1
                continue

            non_nulls = c_data.dropna()
            
            if not non_nulls.empty:
                if is_array:
                    exploded = non_nulls.astype(str).str.split('|').explode().str.strip()
                    exploded = exploded[exploded != ""]
                    valid_mask = check_type(exploded, c_type_base)
                    if not valid_mask.all():
                        invalid_series = exploded[~valid_mask]
                        file_errors[t_name].append(f"[도메인 무결성] '{c_name}' 배열 형식 위반 ➔ {format_errors(invalid_series)}")
                        total_errors += 1
                else:
                    valid_mask = check_type(non_nulls, c_type_base)
                    if not valid_mask.all():
                        invalid_series = non_nulls[~valid_mask]
                        file_errors[t_name].append(f"[도메인 무결성] '{c_name}' '{c_type_base}' 형식 위반 ➔ {format_errors(invalid_series)}")
                        total_errors += 1

            if 'NOT NULL' in constraints:
                if c_data.isna().any():
                    invalid_series = pd.Series(["NULL"] * c_data.isna().sum(), index=c_data[c_data.isna()].index)
                    file_errors[t_name].append(f"[Null 무결성] '{c_name}' 빈 칸 존재 ➔ {format_errors(invalid_series)}")
                    total_errors += 1
                    
            if 'UNIQUE' in constraints:
                dup_mask = non_nulls.duplicated(keep=False)
                if dup_mask.any():
                    invalid_series = non_nulls[dup_mask]
                    file_errors[t_name].append(f"[고유 무결성] '{c_name}' 중복 존재 ➔ {format_errors(invalid_series)}")
                    total_errors += 1
                    
            if not non_nulls.empty:
                for const in constraints:
                    const_u = const.upper()
                    if const_u.startswith("CHECK IN(") and const.endswith(")"):
                        vals_str = const[len("CHECK IN("):-1]
                        allowed = [v.strip() for v in vals_str.split('|')]
                        items_to_check = non_nulls.astype(str).str.split('|').explode().str.strip() if is_array else non_nulls.astype(str).str.strip()
                        invalid_mask = ~items_to_check.isin(allowed)
                        if invalid_mask.any():
                            invalid_series = items_to_check[invalid_mask]
                            file_errors[t_name].append(f"[도메인 무결성] '{c_name}' CHECK IN({vals_str}) 위반 ➔ {format_errors(invalid_series)}")
                            total_errors += 1
                    elif const_u.startswith("CHECK NOT IN(") and const.endswith(")"):
                        vals_str = const[len("CHECK NOT IN("):-1]
                        disallowed = [v.strip() for v in vals_str.split('|')]
                        items_to_check = non_nulls.astype(str).str.split('|').explode().str.strip() if is_array else non_nulls.astype(str).str.strip()
                        invalid_mask = items_to_check.isin(disallowed)
                        if invalid_mask.any():
                            invalid_series = items_to_check[invalid_mask]
                            file_errors[t_name].append(f"[도메인 무결성] '{c_name}' CHECK NOT IN 위반 ➔ 금지된 값: {format_errors(invalid_series)}")
                            total_errors += 1
                    elif const_u.startswith("CHECK(") and const.endswith(")"):
                        expr = const[len("CHECK("):-1]
                        items_to_check = non_nulls.astype(str).str.split('|').explode().str.strip() if is_array else non_nulls
                        failed_idx, failed_vals = [], []
                        for idx, val in items_to_check.items():
                            if not evaluate_check_expr(val, expr):
                                failed_idx.append(idx)
                                failed_vals.append(str(val))
                        if failed_vals:
                            invalid_series = pd.Series(failed_vals, index=failed_idx)
                            file_errors[t_name].append(f"[도메인 무결성] '{c_name}' CHECK({expr}) 위반 ➔ {format_errors(invalid_series)}")
                            total_errors += 1
                            
    on_progress(70)
                    
    for t_name, t_data in df_dict.items():
        df = t_data['df']
        fks = t_data['meta'].get('foreignKeys', {})
        for fk_name, fk_info in fks.items():
            local_cols = fk_info['columns']
            target_table = fk_info['targetTable']
            target_basename = os.path.basename(target_table)
            
            if target_basename not in df_dict:
                file_errors[t_name].append(f"[참조 무결성] '{fk_name}' 타겟 테이블 '{target_basename}' 없음")
                total_errors += 1
                continue
                
            target_data = df_dict[target_basename]
            target_df = target_data['df']
            target_pk = target_data['meta']['primaryKey']
            
            if len(local_cols) != len(target_pk):
                file_errors[t_name].append(f"[참조 무결성] '{fk_name}' 매핑 개수 불일치 (로컬 {len(local_cols)}개 vs 타겟 PK {len(target_pk)}개)")
                total_errors += 1
                continue
            
            missing_locals = [c for c in local_cols if c not in df.columns]
            if missing_locals:
                file_errors[t_name].append(f"[참조 무결성] 로컬 매핑 컬럼 {missing_locals} 존재하지 않음")
                total_errors += 1
                continue

            local_subset = df[local_cols].dropna()
            if local_subset.empty: continue
            
            target_tuples = set([tuple(x) for x in target_df[target_pk].dropna().to_numpy()])
            invalid_mask = ~local_subset.apply(tuple, axis=1).isin(target_tuples)
            
            if invalid_mask.any():
                invalid_df = local_subset[invalid_mask]
                invalid_series = pd.Series([", ".join(x.astype(str)) for x in invalid_df.to_numpy()], index=invalid_df.index)
                file_errors[t_name].append(f"[참조 무결성] '{fk_name}' 유령 참조 값(없는 타겟) 발견 ➔ {format_errors(invalid_series)}")
                total_errors += 1

    on_progress(90)
    on_log("\n🔍 3단계: 검증 결과 리포트 생성 중...")
    
    if total_errors > 0:
        for t_name, err_list in file_errors.items():
            if err_list:
                on_log("\n\n\n" + "━"*60) 
                on_log(f"📁 대상 파일: {t_name} (총 {len(err_list)}건 위반)")
                on_log("-" * 60)
                for err in err_list:
                    on_log(f"  ❌ {err}")
                
    on_progress(100)
    on_log("\n\n" + "="*60)
    if total_errors == 0:
        on_log("🎉 [검증 완료] 5대 무결성 위반 사항이 없습니다. 엔진 삽입이 준비되었습니다!")
    else:
        on_log(f"⚠️ [검증 실패] 전체 워크스페이스에서 총 {total_errors}건의 위반 사항이 발견되었습니다. 데이터를 수정해주세요.")
    on_log("="*60)
