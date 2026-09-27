import os, sys, io, contextlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage
from models.schema import AgentState
import pandas as pd
load_dotenv()
lower = os.getenv("LLM_LOWER", "llama-3.1-8b-instant")
higher = os.getenv("LLM_HIGHER", "llama-3.3-70b-versatile")
groq_api_key = os.getenv("GROQ_API_KEY")

def generate_python_code(state: AgentState) -> AgentState:
    llm = ChatGroq(model=higher, api_key=groq_api_key, max_retries=3)
    user_prompt = state.curated_query or state.user_prompt
    sql_data = state.sql_result or "[]"

    prompt = f"""
    You are Tyrell, expert Python Data Science Agent.
    Write executable Python code to transform this SQL data into insights and a beautiful visual chart.

    SQL Data: {sql_data}
    User Request: {user_prompt}

    REQUIREMENTS:
    - Use `seaborn` and `matplotlib.pyplot`.
    - Apply a clean aesthetic: `sns.set_theme(style="whitegrid", palette="Blues_r")`.
    - Set figure size: `plt.figure(figsize=(10, 5), dpi=300)`.
    - Remove top and right borders with `sns.despine()`.
    - PANDAS COLUMN SAFETY: ALWAYS use explicit, uniquely named aggregations (e.g., `.agg(total_count=('col', 'size'))`) to prevent duplicate column names like 'count' or MultiIndex headers that crash matplotlib.
    - Always save the figure to 'output_chart.png' using `plt.savefig('output_chart.png', bbox_inches='tight')` and then call `plt.close()`.
    - Output ONLY valid executable python code in ```python ... ``` blocks.
    """
    try:
        result = llm.invoke(prompt).content
    except Exception as e:
        result = f"# Error generating code: {str(e)}"

    state.python_code = result
    return state

def execute_python_code(state: AgentState) -> AgentState:
    code = state.python_code or ""
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0]
    elif "```" in code:
        code = code.split("```")[1].split("```")[0]

    stdout_capture = io.StringIO()
    try:
        if os.path.exists("output_chart.png"):
            os.remove("output_chart.png")

        # FIX: Include sql_data, pandas, and io in the execution context
        execution_globals = {
            "os": os,
            "sys": sys,
            "plt": plt,
            "sns": sns,
            "pd": pd,
            "sql_data": state.sql_result or []
        }

        with contextlib.redirect_stdout(stdout_capture):
            exec(code, execution_globals)

        output = stdout_capture.getvalue() or "Analysis completed successfully."
        state.code_execution_result = output
        if os.path.exists("output_chart.png"):
            state.chart_path = "output_chart.png"
    except Exception as e:
        state.code_execution_result = f"Python Execution Error: {str(e)}"
    return state

def generate_tyrell_answer(state: AgentState) -> AgentState:
    llm = ChatGroq(model=lower, api_key=groq_api_key, max_retries=3)
    prompt = f"""
    You are Tyrell, Senior Analytics Agent for Elliot.
    Summarize the data analysis findings into a concise, executive summary.

    User Goal: {state.user_prompt}
    Execution Output: {state.code_execution_result}
    Chart Created: {'Yes' if state.chart_path else 'No'}
    """
    try:
        result = llm.invoke(prompt).content
    except Exception:
        result = f"Analysis completed successfully. Summary output:\n{state.code_execution_result}"

    state.final_answer = result
    state.messages = [AIMessage(content=result)]
    return state