from tokvera import (
    create_autogen_tracer,
    create_livekit_tracer,
    create_mastra_tracer,
    create_openai_compatible_gateway_tracer,
    create_pipecat_tracer,
    create_temporal_tracer,
)


def run_autogen() -> None:
    tracer = create_autogen_tracer(
        api_key="tkv_project_key",
        feature="autogen_chat",
        tenant_id="acme",
        emit_lifecycle_events=True,
    )
    conversation = tracer.start_conversation(step_name="autogen_conversation")
    agent = tracer.start_agent(conversation, step_name="planner_agent")
    tracer.finish_node(agent, response={"next": "search_docs"})
    tracer.finish_run(conversation, response={"status": "completed"})


def run_mastra() -> None:
    tracer = create_mastra_tracer(
        api_key="tkv_project_key",
        feature="mastra_workflow",
        tenant_id="acme",
        emit_lifecycle_events=True,
    )
    workflow = tracer.start_workflow(step_name="mastra_workflow")
    step = tracer.start_step(workflow, step_name="search_docs")
    tracer.finish_node(step, response={"matches": 4})
    tracer.finish_run(workflow, response={"status": "completed"})


def run_temporal() -> None:
    tracer = create_temporal_tracer(
        api_key="tkv_project_key",
        feature="temporal_workflow",
        tenant_id="acme",
        emit_lifecycle_events=True,
    )
    workflow = tracer.start_workflow(step_name="temporal_workflow")
    activity = tracer.start_activity(workflow, step_name="lookup_account", tool_name="lookup_account")
    tracer.finish_tool(activity, response={"account_status": "active"})
    tracer.finish_run(workflow, response={"status": "completed"})


def run_pipecat() -> None:
    tracer = create_pipecat_tracer(
        api_key="tkv_project_key",
        feature="voice_pipeline",
        tenant_id="acme",
        emit_lifecycle_events=True,
        capture_content=True,
    )
    turn = tracer.start_turn(step_name="voice_turn")
    transcript = tracer.start_transcription(
        turn,
        step_name="speech_to_text",
        provider="openai",
        model="gpt-4o-mini-transcribe",
    )
    tracer.finish_model(transcript, response={"transcript": "Need account help"})
    tracer.finish_run(turn, response={"status": "completed"})


def run_livekit() -> None:
    tracer = create_livekit_tracer(
        api_key="tkv_project_key",
        feature="livekit_agent",
        tenant_id="acme",
        emit_lifecycle_events=True,
        capture_content=True,
    )
    session = tracer.start_session(step_name="livekit_room_session")
    turn = tracer.start_turn(
        session,
        step_name="voice_turn",
        provider="openai",
        model="gpt-4o-realtime-preview",
    )
    tracer.finish_model(turn, response={"transcript": "Upgrade my plan"})
    tracer.finish_run(session, response={"status": "completed"})


def run_gateway() -> None:
    tracer = create_openai_compatible_gateway_tracer(
        api_key="tkv_project_key",
        feature="gateway_router",
        tenant_id="acme",
        emit_lifecycle_events=True,
    )
    request = tracer.start_request(step_name="gateway_request", model="router")
    downstream = tracer.start_downstream(
        request,
        step_name="downstream_provider_call",
        provider="openai",
        model="gpt-4o-mini",
    )
    tracer.finish_model(
        downstream,
        response={"output_text": "ok"},
        usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
    )
    tracer.finish_run(request, response={"status": "completed"})


if __name__ == "__main__":
    run_autogen()
    run_mastra()
    run_temporal()
    run_pipecat()
    run_livekit()
    run_gateway()
