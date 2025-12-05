import socket
import os
import threading

HOST = "127.0.0.1"   
PORT = 9000          
FILES_DIR = "./files"


def handle_client(conn, addr):
    print(f"[FILE SERVER] Connected from {addr}")
    with conn:
        while True:
            data = conn.recv(1024)
            if not data:
                # client closed connection
                print(f"[FILE SERVER] {addr} disconnected")
                break

            line = data.decode().strip()
            if not line:
                continue

            print(f"[FILE SERVER] Command from {addr}: {line}")
            parts = line.split()
            cmd = parts[0].upper()

            if cmd == "LIST":
                send_list(conn)

            elif cmd == "DOWNLOAD" and len(parts) == 2:
                filename = parts[1]
                send_file(conn, filename)

            else:
                msg = "ERROR InvalidCommand\n"
                conn.sendall(msg.encode())


def send_list(conn):
    try:
        files = os.listdir(FILES_DIR)
    except FileNotFoundError:
        files = []

    files = [f for f in files if os.path.isfile(os.path.join(FILES_DIR, f))]

    lines = ["OK", str(len(files))]
    lines.extend(files)
    lines.append("END")
    response = "\n".join(lines) + "\n"
    conn.sendall(response.encode())
    print("[FILE SERVER] Sent file list")


def send_file(conn, filename):
    path = os.path.join(FILES_DIR, filename)
    if not os.path.isfile(path):
        msg = "ERROR FileNotFound\n"
        conn.sendall(msg.encode())
        print(f"[FILE SERVER] File not found: {filename}")
        return

    size = os.path.getsize(path)
    header = f"OK\n{size}\n"
    conn.sendall(header.encode())

    print(f"[FILE SERVER] Sending file {filename} ({size} bytes)")
    with open(path, "rb") as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            conn.sendall(chunk)
    print(f"[FILE SERVER] Finished sending {filename}")


def main():
    os.makedirs(FILES_DIR, exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"[FILE SERVER] Listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()


if __name__ == "__main__":
    main()