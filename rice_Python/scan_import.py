import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 一个比较常见的标准库名单，先排掉，免得全装一遍
STD_LIB = {
    "os", "sys", "re", "json", "subprocess", "datetime", "time", "typing",
    "pathlib", "logging", "functools", "itertools", "collections", "dataclasses",
    "typing_extensions", "math", "random", "shutil", "tempfile", "argparse",
    "unittest", "http", "urllib", "enum", "traceback", "importlib",
}

imports = set()

for root, _, files in os.walk(PROJECT_ROOT):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                text = fp.read()

            # 匹配 import xxx, import xxx as yyy
            for m in re.findall(r"^\s*import\s+([a-zA-Z0-9_\.]+)", text, re.MULTILINE):
                top = m.split(".")[0]
                imports.add(top)

            # 匹配 from xxx import yyy
            for m in re.findall(r"^\s*from\s+([a-zA-Z0-9_\.]+)\s+import\s+", text, re.MULTILINE):
                top = m.split(".")[0]
                imports.add(top)

# 去掉标准库python scan_imports.py
third_party = sorted(i for i in imports if i not in STD_LIB)

print("=== possible third-party imports ===")
for name in third_party:
    print(name)