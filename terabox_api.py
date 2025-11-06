"""
Terabox API - Updated with Working APIs (November 2025)
Priority: Udayscript API (terabox.udayscriptsx.workers.dev) → Wdzone API
"""

import requests
import logging
from typing import Dict, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

class TeraboxAPI:
    def __init__(self):
        """Initialize with working API endpoints - Udayscript FIRST"""
        # Priority order: Udayscript first, Wdzone as backup
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
        """
        Extract Terabox file info using external APIs
        Priority: Udayscript → Wdzone
        
        Args:
            url: Terabox share URL
            video_quality: Preferred quality
        
        Returns:
            Dict with files list containing name, size, and download_url
        """
        logger.info(f"🔍 Extracting from: {url}")
        
        # Try each API endpoint in priority order
        for api_config in self.api_endpoints:
            try:
                api_name = api_config['name']
                api_url = api_config['url']
                param_name = api_config['param']
                
                logger.info(f"🌐 Trying {api_name} API...")
                
                # Build request URL
                full_url = f"{api_url}?{param_name}={quote(url)}"
                
                # Make request
                response = requests.get(
                    full_url,
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                logger.info(f"📡 {api_name} Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Parse response based on API
                    files = self._parse_api_response(data, api_name)
                    
                    if files:
                        logger.info(f"✅ {api_name} SUCCESS! Found {len(files)} file(s)")
                        return {"files": files, "api_used": api_name}
                    else:
                        logger.warning(f"⚠️ {api_name} returned empty files")
                        
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️ {api_name} timed out")
                continue
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ {api_name} request failed: {str(e)[:100]}")
                continue
            except Exception as e:
                logger.error(f"❌ {api_name} error: {str(e)[:100]}")
                continue
        
        # All APIs failed
        raise Exception("❌ All APIs failed. Please check URL or try again later.")

    def _parse_api_response(self, data: Dict, api_name: str) -> List[Dict]:
        """Parse API response based on source"""
        files = []
        
        try:
            # Check for error in response
            if isinstance(data, dict):
                # Check common error fields
                if 'error' in data or 'Error' in data:
                    logger.warning(f"⚠️ {api_name} returned error: {data.get('error') or data.get('Error')}")
                    return []
                
                if 'Status' in data and data['Status'] == 'Error':
                    logger.warning(f"⚠️ {api_name} returned error: {data.get('Message', 'Unknown error')}")
                    return []
                
                if '❌' in str(data) or '⚠️' in str(data):
                    logger.warning(f"⚠️ {api_name} returned error response")
                    return []
                
                # Parse based on API response format
                file_list = self._extract_file_list(data)
                
                if not file_list:
                    logger.warning(f"⚠️ {api_name}: Could not extract file list")
                    return []
                
                # Parse each file
                if isinstance(file_list, list):
                    for file_info in file_list:
                        parsed_file = self._parse_file_info(file_info)
                        if parsed_file:
                            files.append(parsed_file)
                            
        except Exception as e:
            logger.error(f"❌ Error parsing {api_name} response: {str(e)[:100]}")
            
        return files

    def _extract_file_list(self, data: Dict) -> Optional[List]:
        """Extract file list from various response formats"""
        # Try multiple field names for file list
        possible_fields = ['files', 'list', 'data', 'results', 'items']
        
        for field in possible_fields:
            if field in data:
                value = data[field]
                if isinstance(value, list):
                    return value
                elif isinstance(value, dict) and 'files' in value:
                    return value['files']
                elif isinstance(value, dict):
                    return [value]
        
        # If single file object (has download_url or similar)
        if 'download_url' in data or 'downloadUrl' in data or 'dlink' in data or 'url' in data:
            return [data]
        
        logger.warning(f"⚠️ Available fields: {list(data.keys())}")
        return None

    def _parse_file_info(self, file_info: Dict) -> Optional[Dict]:
        """Parse individual file information"""
        try:
            # Extract download URL (try multiple field names)
            download_url = (
                file_info.get('download_url') or 
                file_info.get('downloadUrl') or 
                file_info.get('dlink') or
                file_info.get('url') or
                file_info.get('link') or
                file_info.get('direct_link')
            )
            
            if not download_url:
                logger.warning("⚠️ No download URL found in file info")
                return None
            
            # Extract filename
            filename = (
                file_info.get('name') or
                file_info.get('filename') or
                file_info.get('server_filename') or
                file_info.get('title') or
                'Terabox File'
            )
            
            # Extract file size
            size = file_info.get('size') or file_info.get('filesize') or 0
            if isinstance(size, (int, float)):
                size_formatted = self._format_size(size)
            else:
                size_formatted = str(size)
            
            return {
                'name': filename,
                'size': size_formatted,
                'download_url': download_url
            }
            
        except Exception as e:
            logger.error(f"❌ Error parsing file info: {str(e)[:100]}")
            return None

    def _format_size(self, size_bytes) -> str:
        """Format bytes to human readable size"""
        try:
            size_bytes = int(size_bytes)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f} PB"
        except:
            return "Unknown"


# ===== BACKWARD COMPATIBILITY FUNCTIONS =====

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
                
