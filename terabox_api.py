"""
Terabox API - Fixed Response Format Parsing (November 2025)
Handles: Udayscript (primary) + Wdzone (backup) API response formats
"""

import requests
import logging
from typing import Dict, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

class TeraboxAPI:
    
    def __init__(self):
        """Initialize with working API endpoints - Udayscript FIRST (faster)"""
        self.api_endpoints = [
            {
                'name': 'Udayscript',  # PRIMARY - Faster
                'url': 'https://terabox.udayscriptsx.workers.dev/',
                'param': 'url'
            },
            {
                'name': 'Wdzone',  # BACKUP - Reliable
                'url': 'https://wdzone-terabox-api.vercel.app/api',
                'param': 'url'
            }
        ]
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
        }
        
        self.timeout = 30
    
    def extract_data(self, url: str, video_quality: str = "HD Video") -> Dict:
        """Extract Terabox file info - Priority: Udayscript → Wdzone"""
        logger.info(f"🔍 Extracting from: {url}")
        
        for api_config in self.api_endpoints:
            try:
                api_name = api_config['name']
                logger.info(f"🔄 Trying {api_name} API...")
                
                # Build API request URL
                api_url = api_config['url']
                param_name = api_config['param']
                encoded_url = quote(url, safe='')
                full_url = f"{api_url}?{param_name}={encoded_url}"
                
                logger.info(f"📡 Request URL: {full_url}")
                
                # Make request
                response = requests.get(
                    full_url,
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                logger.info(f"📥 Response status: {response.status_code}")
                
                if response.status_code != 200:
                    logger.warning(f"⚠️ {api_name} returned {response.status_code}")
                    continue
                
                # Parse JSON response
                try:
                    data = response.json()
                except Exception as e:
                    logger.error(f"❌ {api_name} JSON parse error: {str(e)}")
                    continue
                
                logger.info(f"📦 {api_name} response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                
                # Parse based on API
                if api_name == 'Udayscript':
                    parsed_files = self._parse_udayscript(data)
                elif api_name == 'Wdzone':
                    parsed_files = self._parse_wdzone(data)
                else:
                    parsed_files = None
                
                if parsed_files and len(parsed_files) > 0:
                    logger.info(f"✅ {api_name} SUCCESS - Found {len(parsed_files)} file(s)")
                    return {
                        'success': True,
                        'files': parsed_files,
                        'api_used': api_name
                    }
                else:
                    logger.warning(f"⚠️ {api_name} returned empty files")
                    
            except requests.RequestException as e:
                logger.error(f"❌ {api_config['name']} request failed: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"❌ {api_config['name']} unexpected error: {str(e)}")
                continue
        
        # All APIs failed
        logger.error("❌ All APIs failed. Please check URL or try again later.")
        return {
            'success': False,
            'error': 'All APIs failed',
            'files': []
        }
    
    def _parse_udayscript(self, data: Dict) -> Optional[List[Dict]]:
        """Parse Udayscript API response format"""
        try:
            # Check response structure
            if not isinstance(data, dict):
                logger.warning(f"⚠️ Udayscript response not a dict: {type(data)}")
                return None
            
            # Check for response/list field
            if 'response' not in data:
                logger.warning(f"⚠️ No 'response' field in Udayscript data")
                return None
            
            file_list = data['response']
            if not isinstance(file_list, list) or len(file_list) == 0:
                logger.warning(f"⚠️ Udayscript file_list empty or invalid")
                return None
            
            files = []
            for file_info in file_list:
                # Extract filename
                filename = file_info.get('filename', file_info.get('name', 'Terabox File'))
                
                # Extract download URL
                resolutions = file_info.get('resolutions', {})
                if not isinstance(resolutions, dict):
                    logger.warning(f"⚠️ resolutions not a dict: {type(resolutions)}")
                    continue
                
                # Try to get HD or Fast Download
                download_url = (
                    resolutions.get('HD Video') or
                    resolutions.get('Fast Download') or
                    list(resolutions.values())[0] if resolutions else None
                )
                
                if not download_url:
                    logger.warning(f"⚠️ No download URL for: {filename}")
                    continue
                
                # Format size
                size = file_info.get('size', 0)
                size_formatted = self._format_size(size)
                
                parsed_file = {
                    'name': filename,
                    'size': size_formatted,
                    'download_url': download_url
                }
                
                files.append(parsed_file)
                logger.info(f"✅ Parsed Udayscript file: {filename} ({size_formatted})")
            
            return files if files else None
            
        except Exception as e:
            logger.error(f"❌ Error parsing Udayscript response: {str(e)}")
            return None
    
    def _parse_wdzone(self, data: Dict) -> Optional[List[Dict]]:
        """Parse Wdzone API response format - IMPROVED for actual response"""
        try:
            logger.info(f"🔍 Parsing Wdzone response: {data}")
            
            files = []
            
            # Try multiple response formats
            file_data = None
            
            # Format 1: Direct response with status and data
            if 'success' in data or 'status' in data:
                is_success = data.get('success') == True or data.get('status') in ['success', 'ok']
                if not is_success:
                    logger.warning(f"⚠️ Wdzone not successful: {data.get('status')}")
                    return None
                file_data = data.get('data') or data.get('result') or data
            
            # Format 2: Emoji keys (✅ Status, 📜 Extracted Info)
            elif '✅ Status' in data or 'Status' in data:
                status = data.get('✅ Status') or data.get('Status')
                if status not in ['Success', 'success', 'ok']:
                    logger.warning(f"⚠️ Wdzone status: {status}")
                    return None
                file_data = data.get('📜 Extracted Info') or data.get('Extracted Info') or data.get('data') or data
            
            # Format 3: Direct file info
            else:
                file_data = data
            
            if not isinstance(file_data, dict):
                logger.warning(f"⚠️ file_data is not dict: {type(file_data)}")
                return None
            
            # Get file list
            if 'files' in file_data:
                file_list = file_data['files']
                if not isinstance(file_list, list):
                    file_list = [file_list]
            elif any(key in file_data for key in ['file_name', 'name', 'filename', 'download_url', 'link']):
                file_list = [file_data]
            elif 'list' in file_data:
                file_list = file_data['list']
                if not isinstance(file_list, list):
                    file_list = [file_list]
            else:
                # Last resort: find file-like objects
                file_list = []
                for key, value in file_data.items():
                    if isinstance(value, dict) and any(k in value for k in ['download_url', 'link', 'url']):
                        file_list.append(value)
            
            # Parse each file
            for file_info in file_list:
                if not isinstance(file_info, dict):
                    continue
                
                # Extract filename - try all possible keys
                filename = (
                    file_info.get('file_name') or
                    file_info.get('fileName') or
                    file_info.get('name') or
                    file_info.get('filename') or
                    file_info.get('title') or
                    'Terabox File'
                )
                
                # Extract download URL - try all possible keys
                download_url = (
                    file_info.get('download_url') or
                    file_info.get('downloadUrl') or
                    file_info.get('direct_link') or
                    file_info.get('directLink') or
                    file_info.get('link') or
                    file_info.get('url') or
                    file_info.get('dlink')
                )
                
                if not download_url:
                    logger.warning(f"⚠️ No download URL in: {list(file_info.keys())}")
                    continue
                
                # Extract size
                size_str = (
                    file_info.get('size') or
                    file_info.get('fileSize') or
                    file_info.get('file_size') or
                    '0'
                )
                size_formatted = self._format_size(size_str)
                
                parsed_file = {
                    'name': filename,
                    'size': size_formatted,
                    'download_url': download_url
                }
                
                files.append(parsed_file)
                logger.info(f"✅ Parsed Wdzone file: {filename} ({size_formatted})")
            
            if not files:
                logger.warning("⚠️ No files extracted from Wdzone")
                logger.info(f"🔍 Debug - Full response: {data}")
            
            return files if files else None
            
        except Exception as e:
            logger.error(f"❌ Error parsing Wdzone: {str(e)}")
            logger.error(f"🔍 Response was: {data}")
            return None
    
    def _format_size(self, size) -> str:
        """Format file size to human readable"""
        try:
            if isinstance(size, str):
                # Already formatted
                if any(unit in size.upper() for unit in ['KB', 'MB', 'GB', 'TB']):
                    return size
                # Try to parse as number
                size = float(size)
            
            size_bytes = float(size)
            
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            
            return f"{size_bytes:.2f} PB"
        except:
            return "Unknown"
                    
