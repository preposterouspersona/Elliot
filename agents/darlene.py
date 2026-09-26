import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph,START,END


from ..models.schema import AgentState, JudgeSchema
from ..utils.db import DatabaseUtil

load_dotenv()

lower = os.getenv("LOWER_LLM")
higher = os.getenv("HIGHER_LLM")
groq_api_key = os.getenv("GROQ_API_KEY")


## --- TOOLS -- ##

@tool
def curate_question(state: AgentState) -> AgentState:
    """This tool refines the user prompt to a well-structured question"""
    user_prompt = state.user_prompt

    llm = ChatGroq(model=lower, api_key=groq_api_key)

    messages = [
        SystemMessage(content="Curate and refine user prompt to a well defined question."),
        HumanMessage(content=user_prompt)
    ]

    result = llm.invoke(messages)

    state.curated_query = result.content
    state.messages = [HumanMessage(content=result.content)]
    return state


@tool
def add_context(state: AgentState) -> AgentState:
    """This tool adds database context to the refined user prompt, and provides a system prompt for SQL generation"""

    connection_details = {
        "dbname": os.getenv("database"),
        "host": os.getenv("host"),
        "user": os.getenv("user"),
        "password": os.getenv("password"),
        "port": int(os.getenv("port", 5432)),
    }

    db_obj = DatabaseUtil(connection_details)
    context = db_obj.schema_details("public")

    curated_prompt = state.curated_query

    prompt = f"""
            You are a helpful AI assistant. Your job is to generate a single SQL query and no extra content from
            user's natural language input, which is to be executed on a Postgres SQL database directly.
            You will be provided all the database schema details such as table names, column names, data types and
            sample data.
            The output should be a single SQL ready-to-be-executed query, no modifications must be made to it while executing
            the query.
            Unless user specifies the no of rows, limit it to 10 to reduce overhead.

            User's query = {curated_prompt}
            database schema details = {context}
    """

    state.prompt_context_sql = prompt
    return state


@tool
def generate_sql_query(state: AgentState) -> AgentState:
    """This tool generates sql query with database schema details, user's query as context"""
    llm = ChatGroq(model=higher, api_key=groq_api_key)

    prompt = state.prompt_context_sql  # our context. Contains user query, db schema details and system prompt
    result = llm.invoke(prompt).content

    state.generated_sql_query = result

    return state


@tool
def check_safety(state: AgentState) -> AgentState:
    """This tool checks wether the generated SQL query is safe to execute."""
    llm = ChatGroq(model=higher, api_key=groq_api_key)
    llm_as_judge = llm.with_structured_output(JudgeSchema)

    sql_query = state.generated_sql_query

    prompt = f"""
    You are an SQL Judge for data security. Your task is to determine whether the SQL query is 
    safe or not. The SQL query should only be used for data retrieval and should not modify the 
    database in any way. Neither the SQL query nor the prompt should contain any SQL commands that can modify the
    database, such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands that can change
    the structure or content of the database. If the SQL query is safe, respond with 'YES' otherwise respond with 
    'NO'. Additionally, provide comments explaining your decision.
    Here's the SQL query to evaluate:
    {sql_query}"""

    result = llm_as_judge.invoke(prompt)

    state.is_safe = (result.answer == "YES")
    state.comments = result.justification
    return state


@tool
def cancel_sql(state: AgentState) -> AgentState:
    """This tool is fallback if the geenrated SQL query is deemed unsafe."""
    comments = state.comments

    state.final_answer = f"Your query was deemed unsafe by our internal software and cannot be executed. The reason being:{comments}\nPlease try again with another query"

    state.messages = [AIMessage(content=state.final_answer)]

    return state


@tool
def execute_sql(state: AgentState) -> AgentState:
    """This tool executes the generated SQL query if it is deemed safe."""
    sql_query = state.generated_sql_query

    connection_details = {
        "dbname": os.getenv("database"),
        "host": os.getenv("host"),
        "user": os.getenv("user"),
        "password": os.getenv("password"),
        "port": int(os.getenv("port", 5432)),
    }

    db_obj = DatabaseUtil(connection_details)
    result = db_obj.execute_sql(sql_query)

    state.sql_result = result
    return state


@tool
def generate_answer(state: AgentState) -> AgentState:
    """This tool provides an answer to the user at the end"""
    curated_prompt = state.curated_query
    sql_answer = state.sql_result

    llm = ChatGroq(model=lower, api_key=groq_api_key)

    prompt = f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer. \n
    Here is the execution result: {sql_answer} \n
    Here is the user's original question: {curated_prompt}
    """

    result = llm.invoke(prompt).content

    state.final_answer = result
    state.messages = [AIMessage(content=result)]

    return state


#-------------------------------GRAPH------------------------------#
darlene_graph  = StateGraph(AgentState)

darlene_graph.add_node("curate_question", curate_question)
darlene_graph.add_node("add_context", add_context)
darlene_graph.add_node("generate_sql_query", generate_sql_query)
darlene_graph.add_node("check_safety", check_safety)
darlene_graph.add_node("cancel_sql", cancel_sql)
darlene_graph.add_node("execute_sql", execute_sql)
darlene_graph.add_node("generate_answer", generate_answer)


darlene_graph.add_edge(START, "curate_question")
darlene_graph.add_edge("curate_question", "add_context")
darlene_graph.add_edge("add_context","generate_sql_query")
darlene_graph.add_edge("generate_sql_query","check_safety")

def safety_router(state: AgentState) :
    return state.is_safe

darlene_graph.add_conditional_edges(
    "check_safety",
    safety_router,
    {
        True:"execute_sql",
        False :"cancel_sql"
    }

)

darlene_graph.add_edge("generate_answer", END)
darlene_graph.add_edge("execute_sql", "generate_answer")
darlene_graph.add_edge("cancel_sql", END)


darlene=darlene_graph.compile()