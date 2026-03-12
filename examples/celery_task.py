from __future__ import annotations

from tokvera import (
    create_celery_task_context,
    get_celery_track_kwargs,
    track_openai,
)


def run_celery_task(task_request):
    context = create_celery_task_context(
        task_request,
        tenant_id="acme",
        environment="production",
    )

    openai = track_openai(
        __import__("openai").OpenAI(api_key="YOUR_OPENAI_API_KEY"),
        api_key="YOUR_TOKVERA_API_KEY",
        **get_celery_track_kwargs(context, step_name="celery_worker_reply"),
    )

    return openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Summarize daily usage"}],
    )

