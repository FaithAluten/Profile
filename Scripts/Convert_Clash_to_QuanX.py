#!/usr/bin/env python3
# scripts/convert_clash_to_qx.py
# 将 Clash 规则集转换为 QuantumultX 格式
# 支持通过环境变量 CLASH_DIR / QX_DIR 覆盖路径（相对或绝对）

import os
import re
import sys
from pathlib import Path

def convert_line(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    # 只处理以 "-" 开头的 Clash 规则行（yaml 中常见）
    if not re.match(r'^\s*-\s*', line):
        return None

    # 去掉开头的 "- " 或 "  - "
    line = re.sub(r'^\s*-\s*', '', line)

    # 移除行内注释
    line = re.sub(r'\s+#.*$', '', line).strip()
    if not line:
        return None

    parts = line.split(',', 1)
    if len(parts) < 2:
        return None

    clash_type = parts[0].strip().upper()
    value = parts[1].strip()

    # Clash -> QX 类型映射
    mapping = {
        'DOMAIN': 'host',
        'DOMAIN-SUFFIX': 'host-suffix',
        'DOMAIN-KEYWORD': 'host-keyword',
        'IP-CIDR': 'ip-cidr',
        'GEOIP': 'geoip',
    }

    qx_type = mapping.get(clash_type)
    if not qx_type:
        # 未知类型则跳过
        return None

    # 对 value 做最基础的清理
    value = value.strip().strip('"').strip("'")
    return f"{qx_type},{value}"

def convert_file(input_file: Path, output_file: Path):
    with input_file.open('r', encoding='utf-8') as f:
        lines = f.readlines()

    qx_rules = [convert_line(line) for line in lines]
    qx_rules = [rule for rule in qx_rules if rule]

    # 如果没有规则就不写（避免覆盖）
    if not qx_rules:
        return False

    # 写入到临时字符串，比较是否变更
    new_content = '\n'.join(qx_rules) + '\n'

    if output_file.exists():
        old_content = output_file.read_text(encoding='utf-8')
        if old_content == new_content:
            return False

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(new_content, encoding='utf-8')
    return True

def main():
    repo_root = Path(os.environ.get('GITHUB_WORKSPACE', '.')).resolve()

    default_clash = repo_root / 'Profile' / 'Clash' / 'Rule'
    default_qx = repo_root / 'Profile' / 'QuantumultX' / 'Rule'

    clash_dir = Path(os.environ.get('CLASH_DIR', default_clash)).resolve()
    qx_dir = Path(os.environ.get('QX_DIR', default_qx)).resolve()

    if not clash_dir.exists():
        print(f"[WARN] Clash 目录不存在：{clash_dir}", file=sys.stderr)
        return 1

    changed_files = []

    for path in clash_dir.iterdir():
        if path.is_file() and path.suffix.lower() in ('.yaml', '.yml'):
            output_name = path.stem + '.list'
            output_path = qx_dir / output_name
            print(f"Converting {path} -> {output_path}")
            try:
                changed = convert_file(path, output_path)
                if changed:
                    changed_files.append(str(output_path.relative_to(repo_root)))
            except Exception as e:
                print(f"[ERROR] 转换 {path} 时出错: {e}", file=sys.stderr)

    if changed_files:
        print("Changed files:")
        for f in changed_files:
            print("  -", f)
    else:
        print("No changes produced.")

    return 0

if __name__ == '__main__':
    sys.exit(main())
