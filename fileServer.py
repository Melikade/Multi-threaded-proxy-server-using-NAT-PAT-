import socket
import os
import threading

HOST = "127.0.0.1"   
PORT = 9000          
FILES_DIR = "./files"


def handle_client(connection, addr):
    print(f"server Connected from {addr}")
    with connection:
        while True:
            data = connection.recv(1024)
            if not data:
                # client closed connection
                print(f"server {addr} disconnected")
                break

            line = data.decode().strip()
            if not line:
                continue

            print(f"server Command from {addr}: {line}")
            parts = line.split()
            command = parts[0].upper()

            if command == "LIST":
                send_list(connection)

            elif command == "DOWNLOAD" and len(parts) == 2:
                filename = parts[1]
                send_file(connection, filename)

            else:
                msg = "ERROR InvalidCommand\n"
                connection.sendall(msg.encode())


def send_list(connection):
    try:
        files = os.listdir(FILES_DIR)
    except FileNotFoundError:
        files = []

    files = [f for f in files if os.path.isfile(os.path.join(FILES_DIR, f))]

    lines = ["OK", str(len(files))]
    lines.extend(files)
    lines.append("END")
    response = "\n".join(lines) + "\n"
    connection.sendall(response.encode())
    print("server Sent file list")


def send_file(connection, filename):
    path = os.path.join(FILES_DIR, filename)
    if not os.path.isfile(path):
        msg = "ERROR FileNotFound\n"
        connection.sendall(msg.encode())
        print(f"server File not found: {filename}")
        return

    size = os.path.getsize(path)
    header = f"OK\n{size}\n"
    connection.sendall(header.encode())

    print(f"server Sending file {filename} ({size} bytes)")
    with open(path, "rb") as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            connection.sendall(chunk)
    print(f"server Finished sending {filename}")


def main():
    os.makedirs(FILES_DIR, exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"server Listening on {HOST}:{PORT}")
        while True:
            connection, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(connection, addr), daemon=True)
            t.start()


if __name__ == "__main__":
    main()