BEGIN;
CREATE TABLE IF NOT EXISTS jobs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_type text NOT NULL CHECK (job_type IN ('training', 'import')),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'running', 'succeeded', 'failed', 'cancelled'
    )),
    step text NOT NULL DEFAULT 'queued',
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    result jsonb NOT NULL DEFAULT '{}'::jsonb,
    progress numeric(5,2) NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    error text,
    cancel_requested boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT job_running_has_started CHECK (
        (status = 'running' AND started_at IS NOT NULL) OR status <> 'running'
    ),
    CONSTRAINT job_finished_has_timestamp CHECK (
        (status IN ('succeeded', 'failed', 'cancelled') AND finished_at IS NOT NULL)
        OR status NOT IN ('succeeded', 'failed', 'cancelled')
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_single_training
    ON jobs (job_type)
    WHERE job_type = 'training' AND status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS jobs_status_created
    ON jobs (status, created_at, id);
CREATE INDEX IF NOT EXISTS jobs_type_status
    ON jobs (job_type, status, created_at DESC);
GRANT SELECT, INSERT, UPDATE, DELETE ON jobs TO midas_app;
GRANT USAGE, SELECT ON SEQUENCE jobs_id_seq TO midas_app;
COMMIT;
