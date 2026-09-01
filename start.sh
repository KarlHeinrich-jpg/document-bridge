#!/usr/bin/env bash
set -euo pipefail

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
  python_cmd=python3
elif command -v python >/dev/null 2>&1; then
  python_cmd=python
else
  echo "未找到 Python。请先安装 Python 3.10 或更高版本。" >&2
  exit 1
fi

venv_dir="$project_dir/.venv"
if [ ! -x "$venv_dir/bin/python" ]; then
  echo "首次启动：正在创建本地运行环境…"
  "$python_cmd" -m venv "$venv_dir"
fi

if ! "$venv_dir/bin/python" -c "import fastapi, multipart, pypandoc, uvicorn" >/dev/null 2>&1; then
  echo "首次启动：正在安装转换引擎与网页依赖…"
  "$venv_dir/bin/python" -m pip install -r "$project_dir/requirements.txt"
fi

cd "$project_dir"
exec "$venv_dir/bin/python" -m app.launcher "$@"

