from typing import Annotated, Literal, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

load_dotenv()

class AgentState(BaseModel):
    messages: Annotated[list[BaseMessage], add_messages]
    user_prompt: str
    db_config: Optional[dict] = None
    intent: Optional[Literal["direct_sql", "sql_then_analytics", "out_of_scope"]] = None
    curated_query: Optional[str] = None
    prompt_context_sql: Optional[str] = None
    is_safe: Optional[bool] = None
    generated_sql_query: Optional[str] = None
    sql_result: Optional[str] = None
    python_code: Optional[str] = None
    code_execution_result: Optional[str] = None
    chart_path: Optional[str] = None
    final_answer: Optional[str] = None
    comments: Optional[str] = None

class RouterSchema(BaseModel):
    intent: Literal["direct_sql", "sql_then_analytics", "out_of_scope"]
    reasoning: str

class JudgeSchema(BaseModel):
    answer: Literal["YES", "NO"]
    justification: str
