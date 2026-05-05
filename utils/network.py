# Copyright (C) 2025
# Network Classes for AnkiConnect
#
# This module handles HTTP server and client functionality.

import select
import socket
import os
import time
from unicodedata import normalize
from .helpers import makeBytes, makeStr, getMimeType

# Cap on handler invocations per tick. Drain I/O fully each tick, but bound
# how many parsed requests we dispatch back-to-back so the Qt UI thread keeps
# yielding under bursts (handlers run on the main thread; mw.col is not
# thread-safe).
MAX_HANDLERS_PER_TICK = int(os.getenv('ANKICONNECT_MAX_HANDLERS_PER_TICK', '4'))


class AjaxRequest:
    """Represents an HTTP request"""
    def __init__(self, headers, body, method='POST', path='/'):
        self.headers = headers
        self.body = body
        self.method = method
        self.path = path


class AjaxClient:
    """Handles individual client connections"""
    def __init__(self, sock, handler):
        self.sock = sock
        self.handler = handler
        self.readBuff = bytes()
        self.writeBuff = bytes()
        self.lastActivity = time.time()
        self.closeAfterSend = False

    def advance(self, recvSize=65536):
        if self.sock is None:
            return False

        if time.time() - self.lastActivity > 30:
            self.close()
            return False

        # Drain everything currently readable. Bounded by what's in the kernel
        # recv buffer; select(timeout=0) breaks us out as soon as it's empty.
        while True:
            rlist, _, _ = select.select([self.sock], [], [], 0)
            if not rlist:
                break
            msg = self.sock.recv(recvSize)
            if not msg:
                self.close()
                return False
            self.lastActivity = time.time()
            self.readBuff += msg

        # Dispatch up to MAX_HANDLERS_PER_TICK fully-parsed requests this tick.
        # Anything left in readBuff is processed on subsequent ticks.
        handled = 0
        while handled < MAX_HANDLERS_PER_TICK:
            req, length = self.parseRequest(self.readBuff)
            if req is None:
                break
            self.readBuff = self.readBuff[length:]
            connHeader = req.headers.get(makeBytes('connection'), b'')
            if makeStr(connHeader).lower().strip() == 'close':
                self.closeAfterSend = True
            self.writeBuff += self.handler(req)
            handled += 1

        # Drain whatever the kernel send buffer accepts.
        while self.writeBuff:
            _, wlist, _ = select.select([], [self.sock], [], 0)
            if not wlist:
                break
            sent = self.sock.send(self.writeBuff)
            if sent <= 0:
                break
            self.writeBuff = self.writeBuff[sent:]
            self.lastActivity = time.time()

        if not self.writeBuff and self.closeAfterSend:
            self.close()
            return False

        return True

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

        self.readBuff = bytes()
        self.writeBuff = bytes()

    def parseRequest(self, data):
        parts = data.split(makeBytes('\r\n\r\n'), 1)
        if len(parts) == 1:
            return None, 0

        # Parse request line to extract method and path
        request_lines = parts[0].split(makeBytes('\r\n'))
        if len(request_lines) > 0:
            request_line = makeStr(request_lines[0])
            request_parts = request_line.split(' ')
            method = request_parts[0] if len(request_parts) > 0 else 'POST'
            path = request_parts[1] if len(request_parts) > 1 else '/'
        else:
            method = 'POST'
            path = '/'

        headers = {}
        for line in request_lines[1:]:  # Skip the request line
            pair = line.split(makeBytes(': '))
            headers[pair[0].lower()] = pair[1] if len(pair) > 1 else None

        headerLength = len(parts[0]) + 4
        bodyLength = int(headers.get(makeBytes('content-length'), 0))
        totalLength = headerLength + bodyLength

        if totalLength > len(data):
            return None, 0

        body = data[headerLength : totalLength]
        return AjaxRequest(headers, body, method, path), totalLength


class AjaxServer:
    """HTTP server for AnkiConnect API"""
    def __init__(self, handler):
        self.handler = handler
        self.clients = []
        self.sock = None
        self.resetHeaders()

    def setHeader(self, name, value):
        self.extraHeaders[name] = value

    def resetHeaders(self):
        self.headers = [
            ['HTTP/1.1 200 OK', None],
            ['Content-Type', 'text/json'],
            ['Access-Control-Allow-Origin', '*'],
            ['Connection', 'keep-alive'],
            ['Keep-Alive', 'timeout=30']
        ]
        self.extraHeaders = {}

    def getHeaders(self):
        headers = self.headers[:]
        for name in self.extraHeaders:
            headers.append([name, self.extraHeaders[name]])
        return headers

    def advance(self):
        if self.sock is not None:
            self.acceptClients()
            self.advanceClients()

    def acceptClients(self):
        rlist = select.select([self.sock], [], [], 0)[0]
        if not rlist:
            return

        clientSock = self.sock.accept()[0]
        if clientSock is not None:
            clientSock.setblocking(False)
            self.clients.append(AjaxClient(clientSock, self.handlerWrapper))

    def advanceClients(self):
        self.clients = list(filter(lambda c: c.advance(), self.clients))

    def listen(self, address='127.0.0.1', port=8765, backlog=5):
        self.close()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.sock.setblocking(False)
        self.sock.bind((address, port))
        self.sock.listen(backlog)

    def handlerWrapper(self, req):
        # Check if this is a GET request for media files
        if req.method == 'GET' and req.path.startswith('/media/'):
            return self.serveMediaFile(req)
        
        # Normal API request handling
        if len(req.body) == 0:
            body = makeBytes('AnkiConnect v.5')
        else:
            try:
                import json
                params = json.loads(makeStr(req.body))
                body = makeBytes(json.dumps(self.handler(params)))
            except ValueError:
                body = makeBytes(json.dumps(None))

        resp = bytes()

        self.setHeader('Content-Length', str(len(body)))
        headers = self.getHeaders()

        for key, value in headers:
            if value is None:
                resp += makeBytes('{}\r\n'.format(key))
            else:
                resp += makeBytes('{}: {}\r\n'.format(key, value))

        resp += makeBytes('\r\n')
        resp += body

        return resp

    def serveMediaFile(self, req):
        """Serve media files directly via HTTP"""
        try:
            # Extract filename from path (e.g., /media/audio_123.mp3 -> audio_123.mp3)
            filename = req.path[7:]  # Remove '/media/' prefix
            if not filename:
                return self.createErrorResponse(400, 'Bad Request: No filename provided')
            
            # Security: prevent directory traversal
            filename = os.path.basename(filename)
            filename = normalize("NFC", filename)
            
            # Get media directory from Anki
            from aqt import mw
            if mw is None or mw.col is None or mw.col.media is None:
                return self.createErrorResponse(503, 'Service Unavailable: Anki not ready')
            
            media_dir = mw.col.media.dir()
            filepath = os.path.join(media_dir, filename)
            
            # Check if file exists
            if not os.path.exists(filepath):
                return self.createErrorResponse(404, 'Not Found: Media file does not exist')
            
            # Read file content
            with open(filepath, 'rb') as f:
                file_content = f.read()
            
            # Determine MIME type
            mime_type = getMimeType(filename)
            
            # Build response
            resp = bytes()
            resp += makeBytes('HTTP/1.1 200 OK\r\n')
            resp += makeBytes('Content-Type: {}\r\n'.format(mime_type))
            resp += makeBytes('Content-Length: {}\r\n'.format(len(file_content)))
            resp += makeBytes('Access-Control-Allow-Origin: *\r\n')
            resp += makeBytes('Cache-Control: public, max-age=31536000\r\n')  # Cache for 1 year
            resp += makeBytes('Connection: keep-alive\r\n')
            resp += makeBytes('Keep-Alive: timeout=30\r\n')
            resp += makeBytes('\r\n')
            resp += file_content
            
            return resp
            
        except Exception as e:
            return self.createErrorResponse(500, 'Internal Server Error: {}'.format(str(e)))
    
    def createErrorResponse(self, status_code, message):
        """Create an HTTP error response"""
        status_messages = {
            400: 'Bad Request',
            404: 'Not Found',
            500: 'Internal Server Error',
            503: 'Service Unavailable'
        }
        status_text = status_messages.get(status_code, 'Error')
        
        body = makeBytes(message)
        resp = bytes()
        resp += makeBytes('HTTP/1.1 {} {}\r\n'.format(status_code, status_text))
        resp += makeBytes('Content-Type: text/plain\r\n')
        resp += makeBytes('Content-Length: {}\r\n'.format(len(body)))
        resp += makeBytes('Access-Control-Allow-Origin: *\r\n')
        resp += makeBytes('Connection: keep-alive\r\n')
        resp += makeBytes('Keep-Alive: timeout=30\r\n')
        resp += makeBytes('\r\n')
        resp += body

        return resp

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

        for client in self.clients:
            client.close()

        self.clients = []
