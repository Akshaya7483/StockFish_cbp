import threading
from queue import Queue
from time import perf_counter
from engine import StockfishEngine
from config import POOL_SIZE


class EnginePool:
    def __init__(self, size: int = POOL_SIZE):
        self.size = size

        # All engines created by the pool (never mutated after init).
        self._engines = [StockfishEngine() for _ in range(size)]

        # Stable id per engine (1-based), used in health/stats output.
        self._engine_ids = {
            id(engine): index + 1
            for index, engine in enumerate(self._engines)
        }

        # Thread-safe queue of currently available engines.
        self._available = Queue()
        for engine in self._engines:
            self._available.put(engine)

        # Guards shared metrics and checkout bookkeeping.
        self._lock = threading.Lock()

        # Engines currently handed out (by id()), to prevent duplicate release.
        self._checked_out = set()

        self._shutdown = False

        # Pool-level metrics
        self.total_requests_served = 0
        self.current_busy_engines = 0
        self.peak_busy_engines = 0
        self.total_waits = 0
        self.total_acquire_wait_time_ms = 0.0

    def _average_acquire_wait_ms(self):
        if self.total_waits:
            return round(
                self.total_acquire_wait_time_ms / self.total_waits,
                4
            )
        return 0

    def acquire(self):
        """
        Block until an engine is available and return it.

        Records how long the call waited, even when an engine was
        immediately available.
        """
        with self._lock:
            if self._shutdown:
                raise RuntimeError("EnginePool is shut down.")

        start = perf_counter()
        engine = self._available.get()
        end = perf_counter()

        wait_ms = (end - start) * 1000

        with self._lock:
            self.total_waits += 1
            self.total_acquire_wait_time_ms += wait_ms
            self.total_requests_served += 1

            self._checked_out.add(id(engine))
            self.current_busy_engines = len(self._checked_out)
            self.peak_busy_engines = max(
                self.peak_busy_engines,
                self.current_busy_engines
            )

        return engine

    def release(self, engine):
        """
        Return an engine to the pool. Always safe to call.

        Duplicate releases are ignored so an engine can never appear
        twice inside the available queue.
        """
        if engine is None:
            return

        with self._lock:
            key = id(engine)

            # Only accept engines that belong to this pool.
            if key not in self._engine_ids:
                return

            # Ignore duplicate / spurious releases.
            if key not in self._checked_out:
                return

            self._checked_out.discard(key)
            self.current_busy_engines = len(self._checked_out)

            # Do not hand stopped engines back out after shutdown.
            if self._shutdown:
                return

            self._available.put(engine)

    def shutdown(self):
        """
        Stop every engine cleanly. After this, acquire() fails immediately.
        """
        with self._lock:
            self._shutdown = True

        for engine in self._engines:
            try:
                engine.stop()
            except Exception:
                pass

    def health(self):
        with self._lock:
            total = len(self._engines)
            busy = self.current_busy_engines
            available = total - busy
            peak = self.peak_busy_engines

        engines = []
        for engine in self._engines:
            engine_health = engine.health()
            engines.append({
                "id": self._engine_ids[id(engine)],
                "healthy": bool(engine_health.get("engine_running")),
                **engine_health,
            })

        return {
            "pool": {
                "total_engines": total,
                "available_engines": available,
                "busy_engines": busy,
                "peak_busy_engines": peak,
            },
            "engines": engines,
        }

    def stats(self):
        with self._lock:
            total_requests = self.total_requests_served
            average_wait = self._average_acquire_wait_ms()
            peak = self.peak_busy_engines

        engines = [engine.stats() for engine in self._engines]

        return {
            "pool": {
                "total_requests": total_requests,
                "average_acquire_wait_ms": average_wait,
                "peak_busy_engines": peak,
            },
            "engines": engines,
        }
