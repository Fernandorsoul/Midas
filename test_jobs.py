import unittest
from unittest.mock import MagicMock

from midas_core.application.jobs import (
    JobCancelled,
    JobWorker,
    cancel_job,
    enqueue_job,
    get_job,
    list_jobs,
    retry_job,
)
from midas_core.domain.jobs import (
    CANCELLED,
    FAILED,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    JobSnapshot,
    JobTransitionError,
    safe_error_message,
)


class DomainTransitionTests(unittest.TestCase):
    def test_queued_can_start_or_cancel(self):
        job = JobSnapshot(1, "training", QUEUED, "queued", 0)
        self.assertTrue(job.can_transition_to(RUNNING))
        self.assertTrue(job.can_transition_to(CANCELLED))
        self.assertFalse(job.can_transition_to(SUCCEEDED))

    def test_running_can_finish(self):
        job = JobSnapshot(1, "training", RUNNING, "dataset", 10)
        self.assertTrue(job.can_transition_to(SUCCEEDED))
        self.assertTrue(job.can_transition_to(FAILED))
        self.assertFalse(job.can_transition_to(QUEUED))

    def test_terminal_states_are_final(self):
        for status in (SUCCEEDED, FAILED, CANCELLED):
            job = JobSnapshot(1, "training", status, "done", 100)
            self.assertFalse(job.can_transition_to(RUNNING))
            with self.assertRaises(JobTransitionError):
                job.assert_transition(RUNNING)

    def test_assert_transition_ignores_same_status(self):
        job = JobSnapshot(1, "import", QUEUED, "queued", 0)
        job.assert_transition(QUEUED)

    def test_safe_error_truncates_and_collapses_whitespace(self):
        message = safe_error_message(ValueError("  erro   com \n espacos  " * 100))
        self.assertLessEqual(len(message), 400)
        self.assertNotIn("\n", message)

    def test_safe_error_uses_type_name_when_empty(self):
        self.assertEqual(safe_error_message(RuntimeError()), "RuntimeError")


class FakeJobRepository:
    def __init__(self):
        self.jobs = {}
        self._next_id = 1

    def insert_job(self, job_type, payload, step="queued"):
        if job_type == "training" and any(
            j["job_type"] == "training" and j["status"] in (QUEUED, RUNNING) for j in self.jobs.values()
        ):
            raise ValueError("Já existe um treinamento na fila ou em execução.")
        job = {
            "id": self._next_id,
            "job_type": job_type,
            "status": QUEUED,
            "step": step,
            "payload": payload,
            "result": {},
            "progress": 0,
            "error": None,
            "cancel_requested": False,
            "created_at": None,
            "started_at": None,
            "finished_at": None,
            "updated_at": None,
        }
        self.jobs[job["id"]] = job
        self._next_id += 1
        return dict(job)

    def list_jobs(self, job_type=None, limit=20):
        rows = [dict(j) for j in self.jobs.values() if job_type is None or j["job_type"] == job_type]
        return list(reversed(rows))[:limit]

    def get_job(self, job_id):
        job = self.jobs.get(job_id)
        return dict(job) if job else None

    def claim_next_job(self):
        for job in self.jobs.values():
            if job["status"] == QUEUED and not job["cancel_requested"]:
                job["status"] = RUNNING
                job["started_at"] = "now"
                return dict(job)
        return None

    def update_job_progress(self, job_id, step, progress, result=None):
        job = self.jobs[job_id]
        job["step"] = step
        job["progress"] = progress
        if result is not None:
            job["result"] = result
        return dict(job)

    def finish_job(self, job_id, status, result=None, error=None):
        job = self.jobs[job_id]
        job["status"] = status
        job["error"] = error
        job["finished_at"] = "now"
        if status == SUCCEEDED:
            job["progress"] = 100
        if result is not None:
            job["result"] = result
        return dict(job)

    def request_job_cancel(self, job_id):
        job = self.jobs[job_id]
        job["cancel_requested"] = True
        if job["status"] == QUEUED:
            job["status"] = CANCELLED
            job["finished_at"] = "now"
        return dict(job)


class EnqueueTests(unittest.TestCase):
    def test_enqueues_training_job(self):
        repository = FakeJobRepository()
        result = enqueue_job("training", {"horizon": 12}, repository=repository)
        self.assertEqual(result["job"]["job_type"], "training")
        self.assertEqual(result["job"]["status"], QUEUED)
        self.assertEqual(result["job"]["payload"]["horizon"], 12)

    def test_rejects_second_training(self):
        repository = FakeJobRepository()
        enqueue_job("training", {"horizon": 12}, repository=repository)
        with self.assertRaisesRegex(ValueError, "Já existe"):
            enqueue_job("training", {"horizon": 6}, repository=repository)

    def test_allows_concurrent_imports(self):
        repository = FakeJobRepository()
        enqueue_job("import", {"ticker": "PETR4", "quantity": 1}, repository=repository)
        enqueue_job("import", {"ticker": "VALE3", "quantity": 1}, repository=repository)
        self.assertEqual(len(repository.jobs), 2)

    def test_rejects_invalid_training_horizon(self):
        repository = FakeJobRepository()
        with self.assertRaisesRegex(ValueError, "Horizonte"):
            enqueue_job("training", {"horizon": 99}, repository=repository)

    def test_rejects_unknown_job_type(self):
        repository = FakeJobRepository()
        with self.assertRaisesRegex(ValueError, "Tipo de job"):
            enqueue_job("email", {"ticker": "PETR4"}, repository=repository)


class WorkerTests(unittest.TestCase):
    def test_run_once_succeeds_and_persists_result(self):
        repository = FakeJobRepository()
        enqueue_job("import", {"ticker": "PETR4", "quantity": 10, "add_to_portfolio": False}, repository=repository)

        def handler(job):
            return {"message": "ok", "prices": 3}

        worker = JobWorker(repository=repository, handlers={"import": handler})
        finished = worker.run_once()
        self.assertEqual(finished["status"], SUCCEEDED)
        self.assertEqual(finished["result"]["prices"], 3)
        self.assertEqual(finished["progress"], 100)

    def test_run_once_stores_safe_error_on_failure(self):
        repository = FakeJobRepository()
        enqueue_job("import", {"ticker": "PETR4", "quantity": 1}, repository=repository)

        def handler(job):
            raise RuntimeError("falha interna detalhada")

        worker = JobWorker(repository=repository, handlers={"import": handler})
        finished = worker.run_once()
        self.assertEqual(finished["status"], FAILED)
        self.assertEqual(finished["error"], "falha interna detalhada")

    def test_run_once_returns_none_when_empty(self):
        repository = FakeJobRepository()
        worker = JobWorker(repository=repository, handlers={})
        self.assertIsNone(worker.run_once())

    def test_cancel_requested_before_run_skips_execution(self):
        repository = FakeJobRepository()
        enqueue_job("import", {"ticker": "PETR4", "quantity": 1}, repository=repository)
        repository.request_job_cancel(1)
        # já cancelado ao estar queued; não deve ser reivindicado
        worker = JobWorker(repository=repository, handlers={"import": MagicMock()})
        self.assertIsNone(worker.run_once())
        self.assertEqual(repository.jobs[1]["status"], CANCELLED)

    def test_running_job_cancel_becomes_cancelled(self):
        repository = FakeJobRepository()
        enqueue_job("import", {"ticker": "PETR4", "quantity": 1}, repository=repository)

        def handler(job):
            repository.request_job_cancel(job["id"])
            raise JobCancelled()

        worker = JobWorker(repository=repository, handlers={"import": handler})
        finished = worker.run_once()
        self.assertEqual(finished["status"], CANCELLED)

    def test_worker_requeues_interrupted_running_jobs(self):
        repository = FakeJobRepository()

        def requeue_interrupted_jobs():
            recovered = []
            for job in repository.jobs.values():
                if job["status"] == RUNNING:
                    job["status"] = QUEUED
                    job["step"] = "queued"
                    job["progress"] = 0
                    job["started_at"] = None
                    recovered.append(job["id"])
            return recovered

        repository.requeue_interrupted_jobs = requeue_interrupted_jobs
        enqueue_job("import", {"ticker": "PETR4", "quantity": 1}, repository=repository)
        repository.jobs[1]["status"] = RUNNING
        worker = JobWorker(repository=repository, handlers={"import": lambda job: {"ok": True}})
        self.assertEqual(repository.jobs[1]["status"], QUEUED)
        finished = worker.run_once()
        self.assertEqual(finished["status"], SUCCEEDED)


class RetryTests(unittest.TestCase):
    def test_retry_creates_new_job_from_failed_payload(self):
        repository = FakeJobRepository()
        first = enqueue_job("import", {"ticker": "PETR4", "quantity": 5}, repository=repository)
        repository.jobs[first["job"]["id"]]["status"] = FAILED
        second = retry_job(first["job"]["id"], repository=repository)
        self.assertEqual(second["job"]["id"], first["job"]["id"] + 1)
        self.assertEqual(second["job"]["status"], QUEUED)
        self.assertEqual(second["job"]["payload"]["ticker"], "PETR4")

    def test_retry_rejects_succeeded_job(self):
        repository = FakeJobRepository()
        first = enqueue_job("import", {"ticker": "PETR4", "quantity": 5}, repository=repository)
        repository.jobs[first["job"]["id"]]["status"] = SUCCEEDED
        with self.assertRaisesRegex(ValueError, "Somente jobs"):
            retry_job(first["job"]["id"], repository=repository)


if __name__ == "__main__":
    unittest.main()
