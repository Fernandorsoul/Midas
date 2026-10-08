"""Estados e transições do ciclo de vida de jobs persistidos.

Máquina de estados deliberadamente pequena e idempotente: repetir uma
transição válida não corrompe o job; transições ilegais são rejeitadas.
"""
from dataclasses import dataclass

QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
CANCELLED = "cancelled"

JOB_STATUSES = frozenset({QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED})
TERMINAL_STATUSES = frozenset({SUCCEEDED, FAILED, CANCELLED})
ACTIVE_STATUSES = frozenset({QUEUED, RUNNING})

JOB_TYPES = frozenset({"training", "import"})

ALLOWED_TRANSITIONS = {
    QUEUED: frozenset({RUNNING, CANCELLED}),
    RUNNING: frozenset({SUCCEEDED, FAILED, CANCELLED}),
    SUCCEEDED: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
}

TRAINING_STEPS = ("queued", "dataset", "training", "done", "failed")
IMPORT_STEPS = ("queued", "import", "portfolio", "done", "failed")

STEPS_BY_TYPE = {
    "training": TRAINING_STEPS,
    "import": IMPORT_STEPS,
}


class JobTransitionError(ValueError):
    """Transição de estado inválida para o job."""


@dataclass(frozen=True)
class JobSnapshot:
    id: int
    job_type: str
    status: str
    step: str
    progress: float

    def can_transition_to(self, target):
        return target in ALLOWED_TRANSITIONS.get(self.status, frozenset())

    def assert_transition(self, target):
        if target == self.status:
            return
        if not self.can_transition_to(target):
            raise JobTransitionError(
                f"Transição inválida de {self.status} para {target}."
            )


def normalize_job_type(value):
    if not value or not isinstance(value, str):
        raise ValueError("Tipo de job é obrigatório.")
    kind = value.strip().lower()
    if kind not in JOB_TYPES:
        raise ValueError("Tipo de job inválido. Use training ou import.")
    return kind


def validate_step(job_type, step):
    allowed = STEPS_BY_TYPE.get(job_type, ())
    if step not in allowed:
        raise ValueError("Etapa inválida para este job.")
    return step


def can_start_new(job_type, active_types):
    """Impede dois treinos ativos; importações concorrentes são permitidas."""
    if job_type == "training" and "training" in active_types:
        raise ValueError("Já existe um treinamento na fila ou em execução.")
    return True


def safe_error_message(error, limit=400):
    """Mensagem de erro segura para persistir e expor na API."""
    if error is None:
        return None
    if isinstance(error, BaseException):
        text = str(error).strip() or type(error).__name__
    else:
        text = str(error).strip()
    text = " ".join(text.split())
    return text[:limit]
