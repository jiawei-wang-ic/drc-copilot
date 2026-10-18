"""Minimal Zhipu GLM chat client (standard library only).

The API key is read from the environment or from ./.env and is never printed or logged.
"""
import json
import os
import ssl
import urllib.request

ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


DOTENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def _load_dotenv(path=DOTENV):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class GLMUnavailable(RuntimeError):
    pass


def chat(messages, model=None, temperature=0.2, timeout=120, retries=1):
    """One retry on any failure (timeouts are the usual cause); raises GLMUnavailable if all attempts fail."""
    last = None
    for _ in range(retries + 1):
        try:
            return _chat_once(messages, model, temperature, timeout)
        except GLMUnavailable as e:
            last = e
            if "not set" in str(e):
                break
    raise last


def _chat_once(messages, model, temperature, timeout):
    _load_dotenv()
    key = os.environ.get("ZHIPUAI_API_KEY", "").strip()
    if not key:
        raise GLMUnavailable("ZHIPUAI_API_KEY is not set (put it in .env)")
    body = json.dumps({
        "model": model or os.environ.get("GLM_MODEL", "glm-5.3-flash"),
        "messages": messages,
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # network, HTTP or JSON errors all mean "model path failed"
        raise GLMUnavailable(f"GLM request failed: {type(e).__name__}") from None
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise GLMUnavailable("GLM returned an unexpected payload") from None
