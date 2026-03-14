from tokvera import (
    configure_claude_agent_sdk,
    configure_google_adk,
    create_crewai_tracer,
    create_instructor_tracer,
    create_langgraph_tracer,
    create_pydanticai_tracer,
)


def run_claude_agent() -> None:
    tracer = configure_claude_agent_sdk(
        api_key="tkv_project_key",
        feature="claude_agent",
        tenant_id="acme",
        emit_lifecycle_events=True,
    )
    run = tracer.start_agent(step_name="claude_agent_run")
    tool = tracer.start_tool(run, step_name="crm_lookup", tool_name="crm_lookup")
    tracer.finish_tool(tool, response={"customer_tier": "priority"})
    tracer.finish_run(run, response={"status": "completed"})


def run_langgraph() -> None:
    tracer = create_langgraph_tracer(
        api_key="tkv_project_key",
        feature="langgraph_workflow",
        tenant_id="acme",
        emit_lifecycle_events=True,
    )
    graph = tracer.start_graph(step_name="langgraph_run")
    node = tracer.start_node(graph, step_name="planner")
    tracer.finish_node(node, response={"next": "kb_search"})
    tracer.finish_run(graph, response={"status": "completed"})


def run_other_helpers() -> None:
    configure_google_adk(api_key="tkv_project_key", feature="google_adk", tenant_id="acme")
    create_instructor_tracer(api_key="tkv_project_key", feature="instructor", tenant_id="acme")
    create_pydanticai_tracer(api_key="tkv_project_key", feature="pydanticai", tenant_id="acme")
    create_crewai_tracer(api_key="tkv_project_key", feature="crewai", tenant_id="acme")


if __name__ == "__main__":
    run_claude_agent()
    run_langgraph()
    run_other_helpers()
