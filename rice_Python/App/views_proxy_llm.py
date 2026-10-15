# file: App/views_proxy_llm.py  (新建一个文件，也可以直接写在已有的 app 里)
import os
import requests
from flask import Blueprint, request, Response

bp_llm = Blueprint("bp_llm", __name__)
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11501")

def _proxied_url(path_suffix: str) -> str:
    # 把 /llm/<path:subpath> 拼到 ollama 基地址后面
    if path_suffix.startswith("http"):
        return path_suffix
    return f"{OLLAMA_BASE}/{path_suffix.lstrip('/')}"

@bp_llm.route("/llm/<path:subpath>", methods=["GET","POST","PUT","DELETE","OPTIONS"])
def proxy_llm(subpath):
    url = _proxied_url(subpath)
    # 透传方法、headers、body
    headers = {k: v for k, v in request.headers if k.lower() != "host"}
    method = request.method.lower()
    data = request.get_data() if method in ("post","put","delete") else None
    params = request.args

    with requests.request(method, url, headers=headers, params=params, data=data, stream=True, timeout=600) as r:
        # 流式转发（适配流式生成）
        def generate():
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        excluded = ["content-encoding", "transfer-encoding", "connection"]
        resp_headers = [(k,v) for k,v in r.headers.items() if k.lower() not in excluded]
        return Response(generate(), status=r.status_code, headers=resp_headers)