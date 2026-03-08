from openai import OpenAI
from tokvera import (
    create_background_job_context,
    get_background_track_kwargs,
    track_openai,
)


def run_job() -> None:
    openai_client = OpenAI(api_key="sk-...")

    job_context = create_background_job_context(
        job_id="job_daily_summary_001",
        feature="daily_summary",
        tenant_id="acme",
        environment="production",
    )

    tracked = track_openai(
        openai_client,
        api_key="tokvera_project_key",
        **get_background_track_kwargs(
            job_context,
            step_name="summarize_incidents",
        ),
    )

    tracked.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Summarize incidents from last 24h."}],
    )


if __name__ == "__main__":
    run_job()

