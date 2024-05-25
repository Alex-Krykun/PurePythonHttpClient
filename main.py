import os
import sys
from pathlib import Path
import socket
import threading

HOST = os.getenv("HOST", "localhost")
PORT = os.getenv("PORT", 4221)

CRLF = "\r\n"

HTTP_REASON_PHRASE = {
    200: "OK",
    201: "Created",
    404: "Not Found"
}


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

        headers['Content-Length'] = str(len(body))

    headers_str = ''
    for key, value in headers.items():
        headers_str += f'{key}: {value}{CRLF}'

    return f"HTTP/1.1 {status_code} {HTTP_REASON_PHRASE[status_code]}{CRLF}{headers_str}{CRLF}{body or ''}"


def routes(path: str, method='GET', headers=None, body=None) -> str:
    segments = path.split('/')[1:]
    if not segments[0]:
        return build_response(200)

    if segments[0] == 'echo':
        body = segments[1]
        return build_response(200, body=body)

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
    response = routes(request['path'], request['method'], headers=request['headers'], body=request['body'])
    user_socket.send(response.encode())


def main():
    server_socket = create_socket_server()
    while True:
        user_socket, user_address = server_socket.accept()
        thread = threading.Thread(target=handle_request, args=[user_socket])
        thread.start()


if __name__ == "__main__":
    main()
