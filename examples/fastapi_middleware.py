from fastapi import FastAPI, Request
from openai import OpenAI
from tokvera import (
    create_fastapi_tracking_middleware,
    get_fastapi_track_kwargs,
    track_openai,
)

app = FastAPI()
openai_client = OpenAI(api_key="your-openai-api-key")

tokvera_middleware = create_fastapi_tracking_middleware(
    defaults={
        "feature": "support_chat",
        "environment": "production",
    },
    context_resolver=lambda request: {
        "tenant_id": request.headers.get("x-tenant-id"),
        "customer_id": request.headers.get("x-customer-id"),
    },
)


@app.middleware("http")
async def tokvera_context(request: Request, call_next):
    return await tokvera_middleware(request, call_next)


@app.post("/reply")
async def reply(prompt: str):
    tracked_client = track_openai(
        openai_client,
        api_key="your-tokvera-project-key",
        **get_fastapi_track_kwargs(
            step_name="draft_reply",
            quality_label="good",
            outcome="success",
        ),
    )

    response = tracked_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "answer": response.choices[0].message.content if response.choices else "",
    }
