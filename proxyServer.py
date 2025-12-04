import socket
import threading

# Proxy listens here (what the CLIENT connects to)
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8000

# File server address (your existing file_server.py)
FILE_SERVER_HOST = "127.0.0.1"
FILE_SERVER_PORT = 9000

# NAT table: (client_ip, client_port) -> (proxy_ip, proxy_ephemeral_port)
nat_table = {}
nat_lock = threading.Lock()


def relay(src_sock, dst_sock, direction_label):
    """
    Relay raw bytes from src_sock to dst_sock until EOF or error.
    direction_label is just for logging, e.g. "CLIENT->SERVER" or "SERVER->CLIENT".
    """
    try:
        while True:
            data = src_sock.recv(4096)
            if not data:
                # connection closed on this side
                # print for debugging, but not too noisy
                print(f"[RELAY {direction_label}] EOF, closing direction.")
                break
            dst_sock.sendall(data)
    except Exception as e:
        print(f"[RELAY {direction_label}] Error: {e}")
    finally:
        # We just stop relaying in this direction. Closing is handled in outer handler.
        pass


def handle_client(client_conn, client_addr):
    """
    Handle a single client connection:
      - connect to file server
      - record NAT mapping
      - relay data both ways using two threads
    """
    client_ip, client_port = client_addr
    print(f"[PROXY] Client connected from {client_ip}:{client_port}")

    # Connect to the file server
    server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_conn.connect((FILE_SERVER_HOST, FILE_SERVER_PORT))
    except Exception as e:
        print(f"[PROXY] Failed to connect to file server: {e}")
        client_conn.close()
        return

    # Get proxy side address used to talk to file server (this is the "NAT/PAT" port)
    proxy_ip, proxy_ephemeral_port = server_conn.getsockname()

    # Store NAT mapping
    with nat_lock:
        nat_table[(client_ip, client_port)] = (proxy_ip, proxy_ephemeral_port)
        print(f"[NAT] ADD {client_ip}:{client_port}  <-->  {proxy_ip}:{proxy_ephemeral_port}")

    # Start relay threads
    t1 = threading.Thread(
        target=relay,
        args=(client_conn, server_conn, "CLIENT->SERVER"),
        daemon=True
    )
    t2 = threading.Thread(
        target=relay,
        args=(server_conn, client_conn, "SERVER->CLIENT"),
        daemon=True
    )

    t1.start()
    t2.start()

    # Wait until either direction finishes
    t1.join()
    t2.join()

    # Clean up
    with nat_lock:
        if (client_ip, client_port) in nat_table:
            print(f"[NAT] DEL {client_ip}:{client_port}  <-->  {nat_table[(client_ip, client_port)][0]}:{nat_table[(client_ip, client_port)][1]}")
            del nat_table[(client_ip, client_port)]

    try:
        client_conn.close()
    except Exception:
        pass
    try:
        server_conn.close()
    except Exception:
        pass

    print(f"[PROXY] Connection with {client_ip}:{client_port} closed.")


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((PROXY_HOST, PROXY_PORT))
        s.listen()
        print(f"[PROXY] Listening on {PROXY_HOST}:{PROXY_PORT}")
        print(f"[PROXY] Forwarding to file server at {FILE_SERVER_HOST}:{FILE_SERVER_PORT}")

        while True:
            client_conn, client_addr = s.accept()
            t = threading.Thread(
                target=handle_client,
                args=(client_conn, client_addr),
                daemon=True
            )
            t.start()


if __name__ == "__main__":
    main()