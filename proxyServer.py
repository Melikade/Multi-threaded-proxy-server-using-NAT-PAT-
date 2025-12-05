import socket
import threading

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8000

FILE_SERVER_HOST = "127.0.0.1"
FILE_SERVER_PORT = 9000

nat_client_to_server = {}
nat_server_to_client = {}

nat_lock = threading.Lock()


def client_to_server_relay(client_conn, client_addr):
    client_ip, client_port = client_addr
    label = f"{client_ip}:{client_port} CLIENT->SERVER"

    try:
        while True:
            data = client_conn.recv(4096)
            if not data:
                print(f"[RELAY {label}] Client closed connection.")
                break

            with nat_lock:
                entry = nat_client_to_server.get((client_ip, client_port))

            if entry is None:
                print(f"[RELAY {label}] NAT entry missing. Dropping data.")
                break

            server_conn, _, _ = entry

            try:
                server_conn.sendall(data)
            except Exception as e:
                print(f"[RELAY {label}] Failed to send to server: {e}")
                break

    except Exception as e:
        print(f"[RELAY {label}] Unexpected error: {e}")


def server_to_client_relay(server_conn):
    proxy_ip, proxy_port = server_conn.getsockname()
    label = f"{proxy_ip}:{proxy_port} SERVER->CLIENT"

    try:
        while True:
            data = server_conn.recv(4096)
            if not data:
                print(f"[RELAY {label}] Server closed connection.")
                break

            with nat_lock:
                entry = nat_server_to_client.get((proxy_ip, proxy_port))

            if entry is None:
                print(f"[RELAY {label}] NAT entry missing. Dropping data.")
                break

            client_conn, _, _ = entry

            try:
                client_conn.sendall(data)
            except Exception as e:
                print(f"[RELAY {label}] Failed to send to client: {e}")
                break

    except Exception as e:
        print(f"[RELAY {label}] Unexpected error: {e}")


def handle_client(client_conn, client_addr):
    client_ip, client_port = client_addr
    print(f"[PROXY] New client from {client_ip}:{client_port}")

    server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server_conn.connect((FILE_SERVER_HOST, FILE_SERVER_PORT))
    except Exception as e:
        print(f"[PROXY] Could not connect to file server: {e}")
        client_conn.close()
        return

    proxy_ip, proxy_port = server_conn.getsockname()

    with nat_lock:
        nat_client_to_server[(client_ip, client_port)] = (server_conn, proxy_ip, proxy_port)
        nat_server_to_client[(proxy_ip, proxy_port)] = (client_conn, client_ip, client_port)

    t_client = threading.Thread(
        target=client_to_server_relay,
        args=(client_conn, client_addr),
        daemon=True
    )
    t_server = threading.Thread(
        target=server_to_client_relay,
        args=(server_conn,),
        daemon=True
    )

    t_client.start()
    t_server.start()

    t_client.join()
    t_server.join()

    with nat_lock:
        nat_client_to_server.pop((client_ip, client_port), None)
        nat_server_to_client.pop((proxy_ip, proxy_port), None)

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
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((PROXY_HOST, PROXY_PORT))
        listener.listen()

        print(f"[PROXY] Listening on {PROXY_HOST}:{PROXY_PORT}")
        print(f"[PROXY] Forwarding traffic to {FILE_SERVER_HOST}:{FILE_SERVER_PORT}")

        while True:
            client_conn, client_addr = listener.accept()
            threading.Thread(
                target=handle_client,
                args=(client_conn, client_addr),
                daemon=True
            ).start()


if __name__ == "__main__":
    main()