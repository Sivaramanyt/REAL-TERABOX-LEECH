# terabox_api.py — complete file (copy/paste)

import requests
import json
import re
from urllib.parse import urlparse, urlencode

# =========================
# Shared helpers
# =========================

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

def _resolve_short(url: str, referer: str) -> str:
    try:
        with requests.Session() as s:
            s.headers.update({"User-Agent": UA, "Accept": "*/*", "Referer": referer})
            r = s.get(url, allow_redirects=True, timeout=(15, 30))
            return str(r.url)
    except Exception:
        return url

def _probe_head(url: str, referer: str) -> bool:
    try:
        with requests.Session() as s:
            s.headers.update({"User-Agent": UA, "Accept": "*/*", "Referer": referer, "Accept-Encoding": "identity"})
            r = s.head(url, allow_redirects=True, timeout=(15, 30))
            if r.status_code in (200, 206):
                cl = r.headers.get("content-length")
                disp = r.headers.get("content-disposition", "")
                return bool(cl or disp)
    except Exception:
        pass
    return False

def _humanize_size(b: int) -> str:
    try:
        b = int(b)
        if b <= 0: return "Unknown"
        units = ["B","KB","MB","GB","TB"]
        i = 0
        while b >= 1024 and i < len(units)-1:
            b /= 1024.0
            i += 1
        return f"{b:.2f} {units[i]}" if units[i] != "B" else f"{int(b)} {units[i]}"
    except Exception:
        return "Unknown"

def format_size(b: int) -> str:
    return _humanize_size(b if isinstance(b, int) else 0)

FOLDER_HINTS = ("/s/", "folder=", "list=", "filelist", "surl=")

def _is_folder_link(u: str) -> bool:
    u = u.lower()
    return any(h in u for h in FOLDER_HINTS)

def _normalize_file_item(name: str, url: str, size_bytes: int | None) -> dict:
    return {
        "name": name or "TeraboxFile",
        "download_url": url,
        "size": _humanize_size(size_bytes or 0)
    }

# =========================
# Wdzone tolerant parser
# =========================

def _parse_wdzone_payload(text: str):
    """
    Accept Wdzone responses as JSON with emoji keys or as plain text/HTML.
    Returns dict for single file or list[dict] for folders, each dict:
      {name, direct_link, sizebytes}
    """
    # Try JSON
    try:
        data = json.loads(text)
        # Folder shapes
        for k in ("files", "folder", "📁 Folder", "items"):
            if k in data and isinstance(data[k], list):
                out = []
                for it in data[k]:
                    name = it.get("name") or it.get("file_name") or "TeraboxFile"
                    direct = it.get("direct_link") or it.get("🔗 ShortLink") or it.get("shortlink") or it.get("url")
                    size = it.get("sizebytes") or it.get("size") or 0
                    if direct:
                        out.append({
                            "name": name,
                            "direct_link": direct,
                            "sizebytes": int(size) if str(size).isdigit() else 0
                        })
                return out if out else None

        # Single-file shapes (emoji and plain)
        info = data.get("Extracted Info") or data.get("📜 Extracted Info") or {}
        name = data.get("file_name") or data.get("name") or (info.get("name") if isinstance(info, dict) else None) or "TeraboxFile"
        size = data.get("sizebytes") or data.get("size") or (info.get("size") if isinstance(info, dict) else 0)
        direct = data.get("direct_link") or data.get("🔗 ShortLink") or data.get("shortlink") or data.get("url")
        if direct:
            return {"name": name, "direct_link": direct, "sizebytes": int(size) if str(size).isdigit() else 0}
    except Exception:
        pass

    # Plain text/HTML: first URL heuristic
    urls = re.findall(r'(https?://[^\s<>"\)\]]+)', text)
    if urls:
        urls.sort(key=lambda u: 0 if ("terabox" in u or "1024tera" in u or "bdstatic" in u) else 1)
        return {"name": "TeraboxFile", "direct_link": urls[0], "sizebytes": 0}
    return None

# =========================
# Terabox API class
# =========================

class TeraboxAPI:
    def __init__(self,
                 primary_endpoint: str | None = None,
                 wdzone_endpoint: str | None = None):
        # Provide defaults if not passed; replace with your real endpoints
        self.primary_endpoint = primary_endpoint or "https://udayscript.example/api/terabox"
        self.wdzone_endpoint = wdzone_endpoint or "https://wdzone.example/api/terabox"

    # ---------- Primary extractor: Udayscript (kept first) ----------
    def extract_with_primary_api(self, url: str) -> list[dict]:
        """
        Udayscript/primary API for single files.
        Expected JSON:
          { "file_name": "...", "direct_link": "https://...", "sizebytes": 123456 }
        Returns list[dict] with keys: name, download_url, size
        """
        try:
            payload = {"link": url}
            headers = {
                "User-Agent": UA,
                "Accept": "application/json",
                "Referer": url,
                "Origin": f"{urlparse(url).scheme}://{urlparse(url).hostname}"
            }
            resp = requests.post(self.primary_endpoint, data=payload, headers=headers, timeout=(20, 40))
            resp.raise_for_status()
        except Exception as e:
            raise Exception(f"Primary API request failed: {e}")

        try:
            data = resp.json()
        except Exception as e:
            raise Exception(f"Primary API invalid JSON: {e}")

        # Typical keys
        name = data.get("file_name") or data.get("name")
        direct = data.get("direct_link") or data.get("url")
        size = data.get("sizebytes") or data.get("size") or 0
        if not direct:
            raise Exception("Primary API: direct_link missing")

        final_url = _resolve_short(direct, referer=url)
        _probe_head(final_url, referer=url)
        return [_normalize_file_item(name, final_url, int(size) if str(size).isdigit() else 0)]

    # ---------- Secondary extractor: Wdzone (improved) ----------
    def extract_with_wdzone(self, url: str) -> list[dict]:
        """
        File or folder extractor:
          returns [{ name, download_url, size }, ...]
        """
        try:
            resp = requests.post(
                self.wdzone_endpoint,
                data={"link": url},
                headers={
                    "User-Agent": UA,
                    "Accept": "*/*",
                    "Referer": url,
                    "Origin": f"{urlparse(url).scheme}://{urlparse(url).hostname}"
                },
                timeout=(20, 40)
            )
            resp.raise_for_status()
        except Exception as e:
            raise Exception(f"Wdzone request failed: {e}")

        parsed = _parse_wdzone_payload(resp.text)
        if not parsed:
            raise Exception("Wdzone: empty/unparseable response")

        items: list[dict] = []
        if isinstance(parsed, list):
            # Folder case
            for it in parsed:
                final_url = _resolve_short(it["direct_link"], referer=url)
                _probe_head(final_url, referer=url)
                items.append(_normalize_file_item(it["name"], final_url, it.get("sizebytes", 0)))
            if not items:
                raise Exception("Wdzone: no files in folder")
            return items

        # Single file
        final_url = _resolve_short(parsed["direct_link"], referer=url)
        _probe_head(final_url, referer=url)
        items.append(_normalize_file_item(parsed["name"], final_url, parsed.get("sizebytes", 0)))
        return items

    # ---------- Router with your preferred order ----------
    def extract_terabox_data(self, url: str) -> dict:
        """
        - If folder: use Wdzone directly (folder supported).
        - Else: try Udayscript first, then Wdzone fallback.
        Returns {'files': [ {name, download_url, size}, ... ]}
        """
        if _is_folder_link(url):
            files = self.extract_with_wdzone(url)
            return {"files": files}

        # Non-folder: Udayscript first
        try:
            files = self.extract_with_primary_api(url)
            if files:
                return {"files": files}
        except Exception:
            pass

        # Fallback to Wdzone
        files = self.extract_with_wdzone(url)
        return {"files": files}

# ---------- Module-level convenience ----------
def extract_terabox_data(url: str) -> dict:
    api = TeraboxAPI()
    return api.extract_terabox_data(url)
        
