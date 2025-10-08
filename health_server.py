"""
Health server for Koyeb deployment
"""

import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

logger = logging.getLogger(__name__)

class HealthHandler(BaseHTTPRequestHandler):
    """Health check handler"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path in ['/', '/health']:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                "status": "healthy",
                "service": "terabox-leech-bot",
                "version": "1.0",
                "message": "Bot is running!",
                "timestamp": int(time.time())
            }
            
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default log messages"""
        pass

def start_health_server():
    """Start health server on port 8000"""
    try:
        server = HTTPServer(('0.0.0.0', 8000), HealthHandler)
        logger.info("Health server started on port 8000")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health server error: {e}")

def run_health_server():
    """Run health server in separate thread"""
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    logger.info("Health server thread started")
