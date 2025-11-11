"""
Terabox API - Fixed Response Format Parsing (November 2025)
Handles: Udayscript + Wdzone API response formats
"""

import requests
import logging
from typing import Dict, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with working API endpoints - Udayscript FIRST"""
        self.api_endpoints = [
            {
                'name': 'Udayscript',
                'url': 'https://terabox.udayscriptsx.workers.dev/',
                'param': 'url'
            },
            {
                'name': 'Wdzone',
                'url': 'https://wdzone-terabox-api.vercel.app/api',
                'param': 'url'
            }
        ]
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
        }
        
        self.timeout = 30

    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """Extract Terabox file info - Priority: Udayscript → Wdzone"""
        logger.info(f"🔍 Extracting from: {url}")
        
        for api_config in self.api_endpoints:
            try:
                api_name = api_config['name']
                api_url = api_config['url']
                param_name = api_config['param']
                
                logger.info(f"🌐 Trying {api_name} API...")
                
                full_url = f"{api_url}?{param_name}={quote(url)}"
                response = requests.get(full_url, headers=self.headers, timeout=self.timeout)
                
                logger.info(f"📡 {api_name} Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"📊 {api_name} Response Fields: {list(data.keys())}")
                    
                    # Parse based on API name
                    files = None
                    if api_name == 'Udayscript':
                        files = self._parse_udayscript(data)
                    elif api_name == 'Wdzone':
                        files = self._parse_wdzone(data)
                    
                    if files:
                        logger.info(f"✅ {api_name} SUCCESS! Found {len(files)} file(s)")
                        return {"files": files, "api_used": api_name}
                    else:
                        logger.warning(f"⚠️ {api_name} returned empty/unparseable data")
                        
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ {api_name} timed out")
                continue
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ {api_name} request failed: {str(e)[:100]}")
                continue
            except Exception as e:
                logger.error(f"❌ {api_name} error: {str(e)[:100]}")
                continue
        
        raise Exception("❌ All APIs failed. Please check URL or try again later.")

    def _parse_udayscript(self, data: Dict) -> Optional[List[Dict]]:
        """Parse Udayscript API response format"""
        try:
            # Udayscript returns single file object with: file_name, link/direct_link, size, etc
            if not isinstance(data, dict):
                return None
            
            # Check for error
            if 'error' in data or data.get('status') == 'error':
                logger.warning(f"⚠️ Udayscript error: {data.get('error', data.get('message'))}")
                return None
            
            # Extract file info from Udayscript response
            filename = data.get('file_name') or data.get('filename') or 'Terabox File'
            
            # Try multiple download URL fields
            download_url = (
                data.get('direct_link') or 
                data.get('link') or
                data.get('download_url') or
                data.get('url')
            )
            
            if not download_url:
                logger.warning("⚠️ No download URL in Udayscript response")
                return None
            
            # Extract size
            size_str = data.get('size') or str(data.get('sizebytes', 0))
            size_formatted = self._format_size(data.get('sizebytes') or size_str)
            
            parsed_file = {
                'name': filename,
                'size': size_formatted,
                'download_url': download_url
            }
            
            logger.info(f"✅ Parsed Udayscript file: {filename}")
            return [parsed_file]
            
        except Exception as e:
            logger.error(f"❌ Error parsing Udayscript response: {str(e)[:100]}")
            return None

    def _parse_wdzone(self, data: Dict) -> Optional[List[Dict]]:
        """Parse Wdzone API response format"""
        try:
            # Wdzone uses emoji keys: '✅ Status', '📜 Extracted Info', '🔗 ShortLink'
            
            # Check status
            status = data.get('✅ Status') or data.get('Status')
            if status != 'Success' and status != 'success':
                logger.warning(f"⚠️ Wdzone status not success: {status}")
                return None
            
            # Extract info object
            info = data.get('📜 Extracted Info') or data.get('Extracted Info') or data
            
            if not info or not isinstance(info, dict):
                logger.warning("⚠️ No extracted info in Wdzone response")
                return None
            
            files = []
            
            # Handle both single file and multiple files
            if 'files' in info:
                file_list = info['files']
                if not isinstance(file_list, list):
                    file_list = [file_list]
            elif 'file_name' in info or 'name' in info:
                file_list = [info]
            else:
                # Try to extract from list
                file_list = []
                for key, value in info.items():
                    if isinstance(value, dict) and ('download_url' in value or 'link' in value):
                        file_list.append(value)
            
            # Parse each file
            for file_info in file_list:
                if not isinstance(file_info, dict):
                    continue
                
                filename = (
                    file_info.get('file_name') or 
                    file_info.get('name') or
                    file_info.get('filename') or
                    'Terabox File'
                )
                
                download_url = (
                    file_info.get('download_url') or
                    file_info.get('direct_link') or
                    file_info.get('link') or
                    file_info.get('url')
                )
                
                if not download_url:
                    continue
                
                size_str = file_info.get('size') or '0'
                size_formatted = self._format_size(size_str)
                
                parsed_file = {
                    'name': filename,
                    'size': size_formatted,
                    'download_url': download_url
                }
                
                files.append(parsed_file)
                logger.info(f"✅ Parsed Wdzone file: {filename}")
            
            return files if files else None
            
        except Exception as e:
            logger.error(f"❌ Error parsing Wdzone response: {str(e)[:100]}")
            return None

    def _format_size(self, size_input) -> str:
        """Format bytes to human readable size"""
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


def extract_terabox_data(url: str) -> Dict:
    """Backward compatibility wrapper"""
    api = TeraboxAPI()
    return api.extract_data(url)


def format_size(size_input) -> str:
    """Format bytes to human readable size"""
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
                    
