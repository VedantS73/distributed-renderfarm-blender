import json
import socket
import threading
import time
from typing import Callable, Dict, Optional, Tuple, Any, List


class SequencerServer:
    """
    Leader-side sequencer:
    - accepts TCP connections from workers
    - assigns a global increasing sequence number to each control message
    - broadcasts messages to all connected workers
    """

    def __init__(self, host: str, port: int = 8890):
        self.host = host
        self.port = port

        self._server_sock: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._running = threading.Event()

        self._clients_lock = threading.Lock()
        self._clients: List[Tuple[socket.socket, Tuple[str, int]]] = []

        self._seq_lock = threading.Lock()
        self._next_seq = 1

    def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(64)

        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def stop(self) -> None:
        self._running.clear()

        try:
            if self._server_sock:
                try:
                    self._server_sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._server_sock.close()
        except Exception:
            pass

        with self._clients_lock:
            for sock, _addr in self._clients:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    sock.close()
                except Exception:
                    pass
            self._clients.clear()

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                assert self._server_sock is not None
                client_sock, addr = self._server_sock.accept()
                client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with self._clients_lock:
                    self._clients.append((client_sock, addr))
            except Exception:
                # short sleep to avoid busy loop on transient errors
                time.sleep(0.1)

    def broadcast_control(self, msg_type: str, payload: Dict[str, Any]) -> int:
        """Assign seq and send to all connected clients. Returns assigned seq."""
        with self._seq_lock:
            seq = self._next_seq
            self._next_seq += 1

        wire = json.dumps({
            "seq": seq,
            "type": msg_type,
            "payload": payload
        }, separators=(",", ":")) + "\n"
        data = wire.encode("utf-8")

        dead: List[Tuple[socket.socket, Tuple[str, int]]] = []
        with self._clients_lock:
            for sock, addr in self._clients:
                try:
                    sock.sendall(data)
                except Exception:
                    dead.append((sock, addr))

            if dead:
                for sock, _addr in dead:
                    try:
                        sock.close()
                    except Exception:
                        pass
                self._clients = [(s, a) for (s, a) in self._clients if (s, a) not in dead]

        return seq

    def connected_peers(self) -> List[str]:
        with self._clients_lock:
            return [addr[0] for _sock, addr in self._clients]


class SequencedClient:
    """
    Worker-side sequenced receiver:
    - connects to leader via TCP
    - receives JSON lines containing {seq,type,payload}
    - buffers out-of-order messages until gaps are filled
    - dispatches messages strictly in seq order
    """

    def __init__(self, leader_host: str, leader_port: int = 8890, on_message: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.leader_host = leader_host
        self.leader_port = leader_port
        self.on_message = on_message

        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()

        self._next_expected = 1
        self._buffer: Dict[int, Dict[str, Any]] = {}

        self._lock = threading.Lock()

    def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        try:
            if self._sock:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._sock.close()
        except Exception:
            pass
        self._sock = None

        with self._lock:
            self._buffer.clear()

    def _connect(self) -> Optional[socket.socket]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(5)
            sock.connect((self.leader_host, self.leader_port))
            sock.settimeout(None)
            return sock
        except Exception:
            return None

    def _run(self) -> None:
        buf = b""
        while self._running.is_set():
            if self._sock is None:
                self._sock = self._connect()
                if self._sock is None:
                    time.sleep(1.0)
                    continue

            try:
                chunk = self._sock.recv(4096)
                if not chunk:
                    # leader closed
                    self.stop()
                    continue
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line:
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        self._handle(msg)
                    except Exception:
                        # ignore malformed
                        continue
            except Exception:
                self.stop()
                time.sleep(1.0)

    def _handle(self, msg: Dict[str, Any]) -> None:
        seq = msg.get("seq")
        if not isinstance(seq, int):
            return

        with self._lock:
            if seq < self._next_expected:
                return

            if seq != self._next_expected:
                self._buffer[seq] = msg
                return

            # seq == next_expected
            self._dispatch(msg)
            self._next_expected += 1

            while self._next_expected in self._buffer:
                nxt = self._buffer.pop(self._next_expected)
                self._dispatch(nxt)
                self._next_expected += 1

    def _dispatch(self, msg: Dict[str, Any]) -> None:
        if self.on_message:
            try:
                self.on_message(msg)
            except Exception:
                pass
