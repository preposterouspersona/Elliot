from dotenv import load_env
from pydantic import BaseModel  #enforces type safety during runtime too.
from typing import Annotated,list, Literal
from langgraph.graph.messages import add_messages
from langchain_core.messages import BaseMessage


load_env()

class AgentState(BaseModel):
    messages : Annotated[list[BaseMessage], add_messages]
    user_prompt: str
    curated_query : str
    prompt_context_sql: str 
    is_safe : bool
    generated_sql_query:  str
    sql_result : str 
    final_answer : str
    comments: str

class JudgeSchema(BaseModel):
    answer : Literal["YES", "NO"]
    justfication : str