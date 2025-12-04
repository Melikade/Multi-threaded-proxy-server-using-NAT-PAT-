import socket
import os

# For now, connect directly to the file server on port 9000
HOST = "127.0.0.1"
PORT = 9000   # later this will be the proxy port

DOWNLOAD_DIR = "./downloads"


def handle_list(sock_file):
    """
    Send LIST command and print the filenames returned by the server.
    Protocol (from server):
        OK
        n
        filename1
        filename2
        ...
        END
    or:
        ERROR <reason>
    """
    # send command
    sock_file.write(b"LIST\n")
    sock_file.flush()

    # read first line (status)
    status_line = sock_file.readline().decode().strip()
    if status_line.startswith("ERROR"):
        print("Server error on LIST:", status_line)
        return
    if status_line != "OK":
        print("Unexpected response on LIST:", status_line)
        return

    # read number of files
    n_line = sock_file.readline().decode().strip()
    try:
        n = int(n_line)
    except ValueError:
        print("Invalid number of files:", n_line)
        return

    print(f"Server reports {n} file(s):")
    for _ in range(n):
        name = sock_file.readline().decode().strip()
        print(" -", name)

    end_line = sock_file.readline().decode().strip()
    if end_line != "END":
        print("Warning: expected END but got:", end_line)


def handle_download(sock_file, filename):
    """
    Send DOWNLOAD <filename> command and save the file.
    Protocol (from server):
        OK
        size
        <size bytes of file>
    or:
        ERROR <reason>
    """
    # send command
    cmd = f"DOWNLOAD {filename}\n"
    sock_file.write(cmd.encode())
    sock_file.flush()

    # first line: status or ERROR
    first_line = sock_file.readline().decode().strip()

    if first_line.startswith("ERROR"):
        print("Server error on DOWNLOAD:", first_line)
        return

    if first_line != "OK":
        print("Unexpected response on DOWNLOAD:", first_line)
        return

    # second line: file size
    size_line = sock_file.readline().decode().strip()
    try:
        size = int(size_line)
    except ValueError:
        print("Invalid size from server:", size_line)
        return

    print(f"Downloading {filename} ({size} bytes)...")

    # read exactly 'size' bytes
    remaining = size
    chunks = []
    while remaining > 0:
        chunk = sock_file.read(min(4096, remaining))
        if not chunk:
            print("Connection closed while downloading.")
            return
        chunks.append(chunk)
        remaining -= len(chunk)

    data = b"".join(chunks)

    # save to downloads directory
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    path = os.path.join(DOWNLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)

    print(f"Saved to {path}")


def main():
    # create TCP socket and connect
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        print(f"Connected to server at {HOST}:{PORT}")

        # wrap socket in a file-like object for easy readline()/read()
        sock_file = sock.makefile("rwb")  # read/write in binary

        try:
            while True:
                cmd = input("Enter command (LIST, DOWNLOAD <file>, QUIT): ").strip()
                if not cmd:
                    continue

                parts = cmd.split(maxsplit=1)
                verb = parts[0].upper()

                if verb == "QUIT":
                    print("Closing connection.")
                    break

                elif verb == "LIST" and len(parts) == 1:
                    handle_list(sock_file)

                elif verb == "DOWNLOAD" and len(parts) == 2:
                    filename = parts[1].strip()
                    if not filename:
                        print("Please provide a filename.")
                        continue
                    handle_download(sock_file, filename)

                else:
                    print("Invalid command. Use: LIST, DOWNLOAD <filename>, QUIT")

        finally:
            sock_file.close()
            print("Disconnected.")


if __name__ == "__main__":
    main()