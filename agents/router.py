import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage
from models.schema import AgentState

load_dotenv()
lower = os.getenv("LLM_LOWER", "llama-3.1-8b-instant")
groq_api_key = os.getenv("GROQ_API_KEY")

def route_intent(state: AgentState) -> AgentState:
    llm = ChatGroq(model=lower, api_key=groq_api_key, max_retries=3)

    prompt = f"""
    You are Mr. Robot, Master Router for the Elliot Assistant.
    Classify the user input into exactly one category:

    1. 'direct_sql': User wants to fetch, filter, view records, list tables, inspect schema/columns/data types, check table structures, or count rows in a table.
    2. 'sql_then_analytics': User asks for visual charts, statistical trends, aggregations, or plotting.
    3. 'out_of_scope': General greetings ("hi", "hello"), casual chit-chat, or questions completely unrelated to databases.

    User Query: {state.user_prompt}

    Respond ONLY with a JSON object in this format:
    {{
        "intent": "direct_sql" | "sql_then_analytics" | "out_of_scope"
    }}
    """
    try:
        raw_response = llm.invoke(prompt).content.strip()
        if "```json" in raw_response:
            raw_response = raw_response.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_response:
            raw_response = raw_response.split("```")[1].split("```")[0].strip()

        data = json.loads(raw_response)
        state.intent = data.get("intent", "direct_sql")
    except Exception:
        prompt_lower = state.user_prompt.lower()
        schema_keywords = ["schema", "table", "column", "data type", "rows", "count", "describe", "explain", "structure", "payments"]
        if any(w in prompt_lower for w in ["chart", "plot", "graph", "visualize", "trend"]):
            state.intent = "sql_then_analytics"
        elif any(w in prompt_lower for w in schema_keywords + ["select", "show", "get", "find", "list"]):
            state.intent = "direct_sql"
        else:
            state.intent = "out_of_scope"

    return state


def handle_out_of_scope(state: AgentState) -> AgentState:
    llm = ChatGroq(model=lower, api_key=groq_api_key, max_retries=3)
    prompt = f"""
    You are Elliot, a friendly SQL & Data Analytics Assistant.
    The user sent a greeting, chit-chat, or off-topic question.
    Acknowledge them politely, clarify that you specialize in querying PostgreSQL databases and generating charts, and ask how you can help with their data.

    User Input: {state.user_prompt}
    """
    try:
        response = llm.invoke(prompt).content
    except Exception:
        response = "Hello! I am Elliot, your PostgreSQL & Data Analytics assistant. How can I help you query your database or generate charts today?"

    state.final_answer = response
    state.messages = [AIMessage(content=response)]
    return state