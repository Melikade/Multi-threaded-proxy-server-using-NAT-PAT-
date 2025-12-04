import socket
import threading

# Proxy listens here (what the CLIENT connects to)
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8000

# File server address (your existing file_server.py)
FILE_SERVER_HOST = "127.0.0.1"
FILE_SERVER_PORT = 9000

# NAT tables:
#   1) client -> proxy/server mapping
#   2) proxy/server -> client mapping
#
# We will USE these tables INSIDE the relay threads.
nat_client_to_server = {}  # (client_ip, client_port) -> (server_conn, proxy_ip, proxy_port)
nat_server_to_client = {}  # (proxy_ip, proxy_port) -> (client_conn, client_ip, client_port)

nat_lock = threading.Lock()


def client_to_server_relay(client_conn, client_addr):
    """
    Relay data from CLIENT to SERVER using the NAT table.

    Steps:
      - Read from client_conn
      - Use (client_ip, client_port) to find the correct server_conn in nat_client_to_server
      - Forward data to that server_conn
    """
    client_ip, client_port = client_addr
    label = f"{client_ip}:{client_port} CLIENT->SERVER"

    try:
        while True:
            data = client_conn.recv(4096)
            if not data:
                print(f"[RELAY {label}] EOF from client, stopping.")
                break

            # Look up the corresponding server connection via NAT table
            with nat_lock:
                entry = nat_client_to_server.get((client_ip, client_port))

            if entry is None:
                print(f"[RELAY {label}] No NAT entry for client, dropping data.")
                break

            server_conn, proxy_ip, proxy_port = entry
            try:
                server_conn.sendall(data)
            except Exception as e:
                print(f"[RELAY {label}] Error sending to server: {e}")
                break

    except Exception as e:
        print(f"[RELAY {label}] Error: {e}")


def server_to_client_relay(server_conn):
    """
    Relay data from SERVER to CLIENT using the NAT table.

    Steps:
      - Read from server_conn
      - Use (proxy_ip, proxy_port) (local address of this server_conn) to find the correct client_conn
      - Forward data to that client_conn
    """
    proxy_ip, proxy_port = server_conn.getsockname()
    label = f"{proxy_ip}:{proxy_port} SERVER->CLIENT"

    try:
        while True:
            data = server_conn.recv(4096)
            if not data:
                print(f"[RELAY {label}] EOF from server, stopping.")
                break

            # Look up the corresponding client connection via NAT table
            with nat_lock:
                entry = nat_server_to_client.get((proxy_ip, proxy_port))

            if entry is None:
                print(f"[RELAY {label}] No NAT entry for server side, dropping data.")
                break

            client_conn, client_ip, client_port = entry
            try:
                client_conn.sendall(data)
            except Exception as e:
                print(f"[RELAY {label}] Error sending to client: {e}")
                break

    except Exception as e:
        print(f"[RELAY {label}] Error: {e}")


def handle_client(client_conn, client_addr):
    """
    Handle a single client connection:
      - Connect to file server
      - Populate NAT tables
      - Start two relay threads that USE the NAT tables
      - On exit, clean up NAT entries and sockets
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

    # Get the proxy's local address used toward the server (this is the PAT port)
    proxy_ip, proxy_ephemeral_port = server_conn.getsockname()

    # Store NAT mappings (BOTH directions)
    with nat_lock:
        nat_client_to_server[(client_ip, client_port)] = (server_conn, proxy_ip, proxy_ephemeral_port)
        nat_server_to_client[(proxy_ip, proxy_ephemeral_port)] = (client_conn, client_ip, client_port)
        print(f"[NAT] ADD client {client_ip}:{client_port}  <-->  proxy {proxy_ip}:{proxy_ephemeral_port}")

    # Start relay threads that explicitly USE the NAT table
    t1 = threading.Thread(
        target=client_to_server_relay,
        args=(client_conn, client_addr),
        daemon=True
    )
    t2 = threading.Thread(
        target=server_to_client_relay,
        args=(server_conn,),
        daemon=True
    )

    t1.start()
    t2.start()

    # Wait for relay threads to finish
    t1.join()
    t2.join()

    # Clean up NAT tables
    with nat_lock:
        # Remove client->server mapping
        if (client_ip, client_port) in nat_client_to_server:
            entry = nat_client_to_server.pop((client_ip, client_port))
            print(f"[NAT] DEL client {client_ip}:{client_port}  (server side was {entry[1]}:{entry[2]})")

        # Remove server->client mapping
        if (proxy_ip, proxy_ephemeral_port) in nat_server_to_client:
            nat_server_to_client.pop((proxy_ip, proxy_ephemeral_port), None)

    # Close sockets
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