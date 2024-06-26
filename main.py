import os
import sys
from pathlib import Path
import socket
import threading
import gzip

HOST = os.getenv("HOST", "localhost")
PORT = os.getenv("PORT", 4221)

CRLF = "\r\n"

# I know I can import that from from http import HTTPStatus, but I don't wan to use any other packages expect os,sys,socket,threading,gzip
HTTP_REASON_PHRASE = {
    100: "Continue",
    101: "Switching Protocols",
    102: "Processing",
    103: "Early Hints",
    200: "OK",
    201: "Created",
    202: "Accepted",
    203: "Non-Authoritative Information",
    204: "No Content",
    205: "Reset Content",
    206: "Partial Content",
    207: "Multi-Status",
    208: "Already Reported",
    226: "IM Used",
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    305: "Use Proxy",
    306: "(Unused)",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    412: "Precondition Failed",
    413: "Payload Too Large",
    414: "URI Too Long",
    415: "Unsupported Media Type",
    416: "Range Not Satisfiable",
    417: "Expectation Failed",
    418: "I'm a teapot",
    421: "Misdirected Request",
    422: "Unprocessable Entity",
    423: "Locked",
    424: "Failed Dependency",
    425: "Too Early",
    426: "Upgrade Required",
    428: "Precondition Required",
    429: "Too Many Requests",
    431: "Request Header Fields Too Large",
    451: "Unavailable For Legal Reasons",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
    505: "HTTP Version Not Supported",
    506: "Variant Also Negotiates",
    507: "Insufficient Storage",
    508: "Loop Detected",
    510: "Not Extended",
    511: "Network Authentication Required"
}

SUPPORTED_ENCODING = [
    'gzip'
]


def create_socket_server():
    if os.name == 'nt':
        return socket.create_server((HOST, PORT))

    return socket.create_server((HOST, PORT), reuse_port=True)


def parse_request(data_str: str):
    data = data_str.split('\r\n')
    http_method, path, http_version = data[0].split(' ')

    headers = {}
    for header in data[1:]:
        if not header:
            break
        key, value = header.split(':', 1)
        headers[key.strip()] = value.strip()

    body = data[-1]
    return {
        "http_method": http_method,
        "path": path,
        "http_version": http_version,
        "headers": headers,
        "body": body,
    }


def build_response(status_code, headers=None, body=None) -> str:
    if not headers:
        headers = {}

    if body:
        if not headers.get('Content-Type'):
            headers['Content-Type'] = 'text/plain'

        if not headers.get('Content-Length'):
            headers['Content-Length'] = str(len(body))

    headers_str = ''
    for key, value in headers.items():
        headers_str += f'{key.lower()}: {value}{CRLF}'

    return f"HTTP/1.1 {status_code} {HTTP_REASON_PHRASE[status_code]}{CRLF}{headers_str}{CRLF}{body or ''}"


def get_content_encoding(accept_encoding: str):
    accept_encoding = accept_encoding.split(", ")
    response_content_encoding = []
    for req_encoding in accept_encoding:
        if req_encoding in SUPPORTED_ENCODING:
            response_content_encoding.append(req_encoding)

    return ", ".join(response_content_encoding) if response_content_encoding else None


def routes(path: str, method='GET', headers=None, body=None) -> str:
    segments = path.split('/')[1:]
    if not segments[0]:
        return build_response(200)

    if segments[0] == 'echo':
        body = segments[1]
        response_header = None
        if headers.get('Accept-Encoding'):
            content_encoding = get_content_encoding(headers['Accept-Encoding'])
            if content_encoding:
                response_header = {
                    "Content-Encoding": content_encoding,
                    "Content-Length": str(len(body)),
                }

                body = gzip.compress(body.encode('utf-8'))
        return build_response(200, headers=response_header, body=body)

    if segments[0] == 'user-agent':
        body = headers['User-Agent']

        return build_response(200, body=body)

    if segments[0] == 'files' and method == 'GET':
        directory = sys.argv[2]
        file_name = segments[1]
        file_path = Path(f"/{directory}/{file_name}")
        if file_path.exists():
            response_header = {
                'Content-Type': 'application/octet-stream'
            }
            body = file_path.read_text()
            return build_response(200, headers=response_header, body=body)
        else:
            return build_response(404)

    if segments[0] == 'files' and method == 'POST':
        directory = sys.argv[2]
        file_name = segments[1]
        file_path = Path(f"/{directory}/{file_name}")
        with open(file_path, 'w') as f:
            f.write(body)
        return build_response(201)

    return build_response(404)


def handle_request(user_socket):
    request = parse_request(user_socket.recv(1024).decode())
    response = routes(request['path'], request['http_method'], headers=request['headers'], body=request['body'])
    user_socket.send(response.encode())


def main():
    server_socket = create_socket_server()
    while True:
        user_socket, user_address = server_socket.accept()
        thread = threading.Thread(target=handle_request, args=[user_socket])
        thread.start()


if __name__ == "__main__":
    main()
