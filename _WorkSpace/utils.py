import os
import json
import ctypes
import sys
from datetime import datetime

# 💡 [NEW] 전역 예외 파일 Prefix 설정
GLOBAL_EXCLUDE_PREFIX = "Disabled"

def set_exclude_prefix(prefix):
    global GLOBAL_EXCLUDE_PREFIX
    GLOBAL_EXCLUDE_PREFIX = prefix if prefix else "Disabled"

# 프로그램 중복 실행 방지 (Mutex)
def check_single_instance():
    if os.name == 'nt':
        mutex_name = "Global\\CSV_DesignDB_Toolkit_Mutex"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183:
            return False
        sys.prevent_gc_mutex = mutex
    return True

# Disabled 폴더/파일 감시 무시 로직 (동적 Prefix 적용)
def is_disabled_path(path):
    if not path:
        return False
    parts = path.replace('\\', '/').split('/')
    return any(p.startswith(GLOBAL_EXCLUDE_PREFIX) for p in parts)

def get_initial_dir():
    return os.getcwd()

def find_workspace_root(current_dir):
    d = os.path.abspath(current_dir)
    while True:
        try:
            files = os.listdir(d)
            for f in files:
                if f.endswith('.csvdesigndb'): return d, f
            # 💡 [FIX] .root 검색 레거시 코드 삭제
        except Exception: pass
        parent = os.path.dirname(d)
        if parent == d: break
        d = parent
    return None, None

def create_workspace_root(target_dir, proj_name):
    filename = f"{proj_name}.csvdesigndb"
    filepath = os.path.join(target_dir, filename)
    config_data = {
        "projectName": proj_name,
        "toolkitVersion": "1.1.0",
        "settings": {
            "maxSuperkeyLength": 2,
            "includeSubDirectories": True,
            "excludePrefix": "Disabled"
        },
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return target_dir, filename
    except Exception:
        return None, None
