"""Worker dedicado de jobs persistidos (importação e treinamento).

Execute com `python midas_core/worker.py` ou o serviço `worker` do compose.
Vários workers podem coexistir: a reivindicação usa FOR UPDATE SKIP LOCKED.
"""
from __future__ import annotations

import argparse
import signal
import threading

from midas_core.application.jobs import JobWorker


def main(argv=None):
    parser = argparse.ArgumentParser(description="Worker de jobs do Midas")
    parser.add_argument("--poll", type=float, default=1.0, help="Intervalo de polling em segundos")
    parser.add_argument("--once", action="store_true", help="Processa no máximo um job e encerra")
    arguments = parser.parse_args(argv)

    worker = JobWorker(poll_seconds=arguments.poll)
    if arguments.once:
        job = worker.run_once()
        if job is None:
            print("Nenhum job na fila.")
        else:
            print(f"Job {job['id']} finalizado com status {job['status']}.")
        return

    stop_event = threading.Event()

    def handle_signal(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    print("Worker de jobs iniciado.", flush=True)
    worker.run_forever(stop_event=stop_event)
    print("Worker de jobs encerrado.", flush=True)


if __name__ == "__main__":
    main()
