"""
Terabox API - Testing Multiple Known Working Endpoints
"""

import requests
import logging
import re
from typing import Dict, List
import time

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """Try working APIs discovered from successful bots"""
        
        pattern = r"/s/(\w+)|surl=(\w+)|terabox|1024tera"
        if not re.search(pattern, url, re.IGNORECASE):
            raise Exception("ERROR: Invalid terabox URL")
        
        logger.info(f"🔍 Extracting from: {url}")
        
        # Working APIs October 2025 (from successful bots)
        apis = [
            {
                "name": "NRBots_API_1",
                "url": f"https://terabox-dl.qtcloud.workers.dev/api/get-info",
                "method": "POST",
                "payload": {"url": url}
            },
            {
                "name": "NRBots_API_2",
                "url": f"https://teraboxapp.wdshot.workers.dev/?url={url}",
                "method": "GET"
            },
            {
                "name": "Your_Cloudflare_API",
                "url": f"https://terabox-api.pages.dev/api?url={url}",
                "method": "GET"
            },
            {
                "name": "UdayScriptsX",
                "url": f"https://terabox.udayscriptsx.workers.dev/?url={url}",
                "method": "GET"
            }
        ]
        
        for api in apis:
            try:
                logger.info(f"🌐 Trying {api['name']}...")
                
                if api["method"] == "POST":
                    response = requests.post(
                        api["url"],
                        json=api.get("payload"),
                        headers=self.headers,
                        timeout=30
                    )
                else:
                    response = requests.get(api["url"], headers=self.headers, timeout=30)
                
                logger.info(f"📊 {api['name']}: HTTP {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    files = self._parse_response(data)
                    
                    if files:
                        logger.info(f"✅ SUCCESS with {api['name']}!")
                        return {"files": files}
                
                time.sleep(0.5)
                        
            except Exception as e:
                logger.warning(f"❌ {api['name']}: {e}")
                continue
        
        raise Exception("⚠️ All APIs failed currently.")
    
    def _parse_response(self, data: Dict) -> List[Dict]:
        """Universal parser for all response formats"""
        files = []
        
        try:
            # Format 1: {success/ok: true, ...}
            if data.get("success") or data.get("ok"):
                download_url = None
                file_list = data.get("list", [data])
                
                for item in file_list:
                    download_url = (item.get("direct_link") or 
                                   item.get("dlink") or 
                                   item.get("downloadLink") or 
                                   item.get("download_link") or
                                   item.get("link"))
                    
                    if download_url:
                        files.append({
                            "name": (item.get("file_name") or 
                                    item.get("filename") or 
                                    item.get("server_filename") or "Terabox File"),
                            "size": format_size(item.get("size", 0)) if isinstance(item.get("size"), int) else item.get("size", "Unknown"),
                            "download_url": download_url.replace('\\/', '/')
                        })
            
            # Format 2: Direct fields
            else:
                download_url = (data.get("direct_link") or 
                               data.get("dlink") or 
                               data.get("downloadLink") or
                               data.get("link"))
                
                if download_url:
                    files.append({
                        "name": (data.get("file_name") or 
                                data.get("filename") or "Terabox File"),
                        "size": data.get("size", "Unknown"),
                        "download_url": download_url.replace('\\/', '/')
                    })
        
        except Exception as e:
            logger.error(f"Parse error: {e}")
        
        return files


def extract_terabox_data(url: str) -> Dict:
    api = TeraboxAPI()
    return api.extract_data(url)

def format_size(size_input) -> str:
    try:
        if isinstance(size_input, str):
            if any(unit in size_input.upper() for unit in ['B', 'KB', 'MB', 'GB', 'TB']):
                return size_input
            try:
                size_input = int(size_input)
            except:
                return str(size_input)
        
        size_bytes = int(size_input)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    except:
        return str(size_input)
                                
