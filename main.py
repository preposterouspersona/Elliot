from langgraph.graph import StateGraph, END
from models.schema import AgentState
from agents.router import route_intent, handle_out_of_scope
from agents.darlene import darlene as darlene_agent_node
from agents.tyrell import generate_python_code, execute_python_code, generate_tyrell_answer

def decide_route(state: AgentState) -> str:
    if state.intent == "out_of_scope":
        return "out_of_scope"
    return "darlene_pipeline"

def decide_analytics_route(state: AgentState) -> str:
    if state.intent == "sql_then_analytics" and state.is_safe:
        return "tyrell_analytics"
    return "end"

builder = StateGraph(AgentState)
builder.add_node("router", route_intent)
builder.add_node("out_of_scope_handler", handle_out_of_scope)
builder.add_node("darlene_pipeline", darlene_agent_node)
builder.add_node("generate_chart_code", generate_python_code)
builder.add_node("run_chart_code", execute_python_code)
builder.add_node("synthesize_analytics", generate_tyrell_answer)

builder.set_entry_point("router")

builder.add_conditional_edges("router", decide_route, {
    "out_of_scope": "out_of_scope_handler",
    "darlene_pipeline": "darlene_pipeline"
})

builder.add_edge("out_of_scope_handler", END)

builder.add_conditional_edges("darlene_pipeline", decide_analytics_route, {
    "tyrell_analytics": "generate_chart_code",
    "end": END
})

builder.add_edge("generate_chart_code", "run_chart_code")
builder.add_edge("run_chart_code", "synthesize_analytics")
builder.add_edge("synthesize_analytics", END)

elliot_system = builder.compile()