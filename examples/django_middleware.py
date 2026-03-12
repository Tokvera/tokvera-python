from __future__ import annotations

from tokvera import (
    create_django_tracking_middleware,
    get_django_track_kwargs,
    track_openai,
)


def tokvera_context_resolver(request):
    tenant_id = None
    user = getattr(request, "user", None)
    if user is not None:
        tenant_id = getattr(user, "tenant_id", None)
    return {
        "feature": "django_support",
        "tenant_id": tenant_id,
        "environment": "production",
    }


tokvera_middleware_factory = create_django_tracking_middleware(
    context_resolver=tokvera_context_resolver
)


def example_view(request):
    openai = track_openai(
        __import__("openai").OpenAI(api_key="YOUR_OPENAI_API_KEY"),
        api_key="YOUR_TOKVERA_API_KEY",
        **get_django_track_kwargs(step_name="django_view_reply"),
    )
    result = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello from Django"}],
    )
    return {"result": result}

