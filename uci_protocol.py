import threading
from queue import Queue, Empty
from config import ENGINE_TIMEOUT


class UCIProtocol:
    def __init__(self, process):
        self.restart = None
        self.attach_process(process)

    def attach_process(self, process):
        self.process = process
        self.output_queue = Queue()

        # Background reader
        threading.Thread(
            target=self._reader,
            daemon=True
        ).start()

    def send(self, command: str):

        if self.process.poll() is not None:
            if self.restart is None:
                raise RuntimeError("No restart handler configured.")
            self.restart()

        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()

        except (BrokenPipeError, OSError):
            if self.restart is None:
                raise RuntimeError("No restart handler configured.")
            self.restart()
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()

    def _reader(self):

        try:
            while True:

                line = self.process.stdout.readline()

                if not line:
                    break

                self.output_queue.put(line.strip())

        finally:
            self.output_queue.put(None)

    def read_until(self, token: str):
        lines = []

        while True:
            line = self.read_line()

            if line:
                lines.append(line)

            if token in line:
                break

        return lines

    def read_line(self, timeout=ENGINE_TIMEOUT):

        if self.process.poll() is not None:
            if self.restart is None:
                raise RuntimeError("No restart handler configured.")
            self.restart()
            raise RuntimeError(
                "Stockfish restarted. Please retry the request."
            )

        try:
            line = self.output_queue.get(timeout=timeout)

            if line is None:
                raise RuntimeError(
                    "Stockfish reader thread stopped."
                )

            return line

        except Empty:
            if self.restart is None:
                raise RuntimeError("No restart handler configured.")
            self.restart()

            raise TimeoutError(
                f"Stockfish timed out after {timeout} seconds."
            )
