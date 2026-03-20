#!/usr/bin/env python3

"""
简单的HTTP服务器，用于测试网络服务功能
"""

import http.server
import socketserver
import os

PORT = 5000

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'LLM Case System Backend')
            return
        super().do_GET()

if __name__ == '__main__':
    print(f"Starting simple HTTP server on port {PORT}...")
    print("Server will be available at http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    
    with socketserver.TCPServer(("0.0.0.0", PORT), MyHTTPRequestHandler) as httpd:
        httpd.serve_forever()
