import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END

from models.schema import AgentState
from utils.db import DatabaseUtil

load_dotenv()

lower = os.getenv("LLM_LOWER", "llama-3.1-8b-instant")
higher = os.getenv("LLM_HIGHER", "llama-3.3-70b-versatile")
groq_api_key = os.getenv("GROQ_API_KEY")


def get_db_connection_details(state: AgentState) -> dict:
    """Helper to retrieve DB credentials from state or fallback to .env."""
    if hasattr(state, "db_config") and state.db_config and any(state.db_config.values()):
        return state.db_config
    return {
        "dbname": os.getenv("database") or os.getenv("dbname") or "postgres",
        "host": os.getenv("host", "localhost"),
        "user": os.getenv("user", "postgres"),
        "password": os.getenv("password", ""),
        "port": int(os.getenv("port", 5432)),
    }


# --- NODES --- #

def curate_question(state: AgentState) -> AgentState:
    """Refines user prompt to a well-structured question."""
    user_prompt = state.user_prompt
    llm = ChatGroq(model=lower, api_key=groq_api_key, max_retries=3)

    messages = [
        SystemMessage(content="Curate and refine user prompt to a well defined question."),
        HumanMessage(content=user_prompt)
    ]

    try:
        result = llm.invoke(messages)
        curated_text = result.content
    except Exception:
        curated_text = user_prompt

    state.curated_query = curated_text
    state.messages = [HumanMessage(content=curated_text)]
    return state


def add_context(state: AgentState) -> AgentState:
    """Adds database context to the prompt."""
    connection_details = get_db_connection_details(state)

    try:
        db_obj = DatabaseUtil(connection_details)
        context = db_obj.schema_details("public")
    except Exception as e:
        context = f"Unable to fetch schema details: {str(e)}"

    curated_prompt = state.curated_query or state.user_prompt

    prompt = f"""
    You are an AI PostgreSQL expert. Your job is to generate a single valid, ready-to-execute SQL query for a PostgreSQL database.

    User's Query: {curated_prompt}
    Database Schema Context: {context}

    INSTRUCTIONS:
    1. If the user asks for schema info, table details, column names, data types, OR row counts, write a valid PostgreSQL query to retrieve that exact information (e.g., querying `information_schema.columns` or using `SELECT COUNT(*) FROM <table_name>`).
    2. Do NOT output explanations or markdown commentary outside of standard ```sql ``` code blocks.
    3. Output ONLY a single SQL query ready for execution.
    """

    state.prompt_context_sql = prompt
    return state


def generate_sql_query(state: AgentState) -> AgentState:
    """Generates SQL query with DB schema context."""
    llm = ChatGroq(model=higher, api_key=groq_api_key, max_retries=3)

    prompt = state.prompt_context_sql
    try:
        result = llm.invoke(prompt).content
        if "```sql" in result:
            result = result.split("```sql")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()
    except Exception:
        result = "-- Error generating SQL query."

    state.generated_sql_query = result
    return state


def check_safety(state: AgentState) -> AgentState:
    """Evaluates SQL query safety using Groq JSON mode (no tool calls)."""
    # Force native JSON mode to eliminate tool_choice errors
    llm = ChatGroq(
        model=higher, 
        api_key=groq_api_key, 
        max_retries=3,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

    prompt = f"""
    You are an SQL Safety Judge. Evaluate if the following SQL query is safe (read-only / data retrieval ONLY).
    A query is UNSAFE if it contains any data modification or schema alteration commands (e.g. INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE).

    Query to evaluate:
    {state.generated_sql_query}

    Respond ONLY with a valid JSON object matching this exact structure:
    {{
        "answer": "YES",
        "justification": "Detailed explanation here"
    }}
    """

    try:
        raw_response = llm.invoke(prompt).content.strip()
        data = json.loads(raw_response)
        ans = str(data.get("answer", "")).strip().upper()

        state.is_safe = (ans == "YES")
        state.comments = data.get("justification", "No justification provided.")

    except Exception as e:
        query_lower = (state.generated_sql_query or "").lower()
        dangerous_keywords = ["insert", "update", "delete", "drop", "alter", "truncate", "create", "grant", "revoke"]
        state.is_safe = not any(kw in query_lower for kw in dangerous_keywords)
        state.comments = f"Rule-based safety check applied. (Detail: {str(e)})"

    return state


def cancel_sql(state: AgentState) -> AgentState:
    """Fallback if SQL is unsafe."""
    comments = state.comments
    state.final_answer = f"Your query was deemed unsafe and cannot be executed. Reason: {comments}"
    state.messages = [AIMessage(content=state.final_answer)]
    return state


def execute_sql(state: AgentState) -> AgentState:
    """Executes safe SQL query."""
    sql_query = state.generated_sql_query
    connection_details = get_db_connection_details(state)

    try:
        db_obj = DatabaseUtil(connection_details)
        result = db_obj.execute_sql(sql_query)
    except Exception as e:
        result = f"Error executing SQL: {str(e)}"

    state.sql_result = result
    return state


def generate_answer(state: AgentState) -> AgentState:
    """Synthesizes final answer for SQL queries."""
    curated_prompt = state.curated_query or state.user_prompt
    sql_answer = state.sql_result

    llm = ChatGroq(model=lower, api_key=groq_api_key, max_retries=3)

    prompt = f"""
    You are an SQL analyst agent. Provide a final answer to the user based on the execution result of the SQL query.
    Make it concise, clear, and directly address the user's query. Avoid technical jargon or raw SQL in the final output.

    Execution result: {sql_answer}
    User question: {curated_prompt}
    """

    try:
        result = llm.invoke(prompt).content
    except Exception:
        result = f"Query executed successfully. Result:\n{sql_answer}"

    state.final_answer = result
    state.messages = [AIMessage(content=result)]
    return state


# --- GRAPH --- #

darlene_graph = StateGraph(AgentState)

darlene_graph.add_node("curate_question", curate_question)
darlene_graph.add_node("add_context", add_context)
darlene_graph.add_node("generate_sql_query", generate_sql_query)
darlene_graph.add_node("check_safety", check_safety)
darlene_graph.add_node("cancel_sql", cancel_sql)
darlene_graph.add_node("execute_sql", execute_sql)
darlene_graph.add_node("generate_answer", generate_answer)

darlene_graph.add_edge(START, "curate_question")
darlene_graph.add_edge("curate_question", "add_context")
darlene_graph.add_edge("add_context", "generate_sql_query")
darlene_graph.add_edge("generate_sql_query", "check_safety")


def safety_router(state: AgentState):
    return state.is_safe


darlene_graph.add_conditional_edges(
    "check_safety",
    safety_router,
    {
        True: "execute_sql",
        False: "cancel_sql"
    }
)

darlene_graph.add_edge("execute_sql", "generate_answer")
darlene_graph.add_edge("generate_answer", END)
darlene_graph.add_edge("cancel_sql", END)

darlene = darlene_graph.compile()