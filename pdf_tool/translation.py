"""LibreTranslate 兼容翻译服务客户端。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .core import PdfToolError


def translate_text(
    text: str,
    target: str,
    endpoint: str,
    *,
    source: str = "auto",
    api_key: str = "",
    timeout: float = 45,
) -> str:
    """调用 LibreTranslate 兼容的 ``/translate`` JSON API。"""

    value = text.strip()
    if not value:
        raise PdfToolError("没有可翻译的文本。")
    if len(value) > 50_000:
        raise PdfToolError("单次翻译不能超过 50,000 个字符。")
    target = target.strip().lower()
    if not target:
        raise PdfToolError("请选择目标语言。")

    endpoint = endpoint.strip()
    if not endpoint:
        raise PdfToolError("请填写 LibreTranslate 兼容服务地址。")
    parsed = urllib.parse.urlparse(endpoint)
    is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme not in {"http", "https"} or (parsed.scheme != "https" and not is_local):
        raise PdfToolError("翻译服务必须使用 HTTPS；本机 localhost 服务可使用 HTTP。")
    if parsed.path in {"", "/"}:
        endpoint = urllib.parse.urlunparse(parsed._replace(path="/translate"))

    payload: dict[str, str] = {
        "q": value,
        "source": source or "auto",
        "target": target,
        "format": "text",
    }
    if api_key.strip():
        payload["api_key"] = api_key.strip()
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detail = ""
        raise PdfToolError(f"翻译服务返回 HTTP {exc.code}：{detail or exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PdfToolError(f"无法连接翻译服务：{exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PdfToolError("翻译服务返回了无法识别的数据。") from exc

    translated = result.get("translatedText") if isinstance(result, dict) else None
    if not isinstance(translated, str) or not translated.strip():
        detail = result.get("error") if isinstance(result, dict) else None
        raise PdfToolError(f"翻译失败：{detail or '服务未返回译文。'}")
    return translated.strip()
