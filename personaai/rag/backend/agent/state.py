from typing import TypedDict, List, Optional, Dict, Literal, Any, Annotated, Tuple, Union
from langchain_core.documents import Document
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
import uuid
import operator
import datetime

# --- Base Models ---
class IntentAnalysisResult(BaseModel):
    user_query: Optional[Annotated[str, "Original User Query"]]
    reasoning_result: str = Field(description="Detailed reasoning for the decision regarding report generation.")
    task_type: Literal["report", "direct_answer"] = Field(
        default="report",
        description="The type of task or output format required: report (detailed analysis), conversation (chat-based response)")
    main_topics: List[str] = Field(description="The main topics of the user's query")
    sub_topics: Optional[List[str]] = Field(description="The sub-topics of the user's query")

class SubQuestion(BaseModel):
    expanded_query: List[str] = Field(description="Expanded querys for retrieval/web search")

class SearchResult(BaseModel):
    question: str = Field(description="Question that used for search")
    documents: List[Document] = Field(description="Search Result")

class EvaluationResult(BaseModel):
    relevance: float = Field(description="Relevance score (0.0 ~ 1.0)", ge= .0, le= 1.0)
    completeness: float = Field(description="Completeness score (0.0 ~ 1.0)", ge= .0, le= 1.0)
    missing_info: Optional[List[str]] = Field(description = "Missing information from the retrieved docs")

class ChatMetadata(BaseModel):
    # user_id: str
    # session_id: uuid.UUID
    title: str = Field(default="new chatting", description="Title of the conversation that summarizes the first conversation.")
    created_at: datetime.datetime
    updated_at: datetime.datetime
    user_preference: Optional[str] = Field(description="User preference for the conversation")

class Plan(BaseModel):
    """Sorted steps to execute the plan"""
    steps: Annotated[List[str], "Different steps to follow, should be in sorted order"]

class Response(BaseModel):
    """Response to user"""
    response: str

class Act(BaseModel):
    """Action to perform"""

    # Action to perform: "Response, Plan". Use Response when replying to the user; use Plan when additional tool use is needed.
    action: Union[Response, Plan] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )

# --- Agent State ---

class AgentState(TypedDict):
    """
    Self-correcting RAG agent's state.

    Attributes:
        messages: Actual conversation history that printed out to the user.
        sub_queries: Expanded sub-queries for searching.
        context: Context from retrival or web search.
        answer: Answer to the user's question.
            - (it can be used as a draft/final answer)
        eval_result: Evaluation result of the answer.
        status: Status of the agent.
        node_visits: Number of node visits.
        metadata: Metadata of the conversation.
        error: Error message for debugging.
    """
    # conversation management
    messages: Annotated[list, add_messages]
    plan: Optional[Annotated[List[str], "Step by step plan for the answer"]]
    past_steps: Optional[Annotated[List[Tuple], operator.add]]

    # query management
    intent_analysis_result: Optional[Annotated[IntentAnalysisResult, "Intent Analysis Result"]]
    sub_queries: Optional[Annotated[SubQuestion, "Sub-queries for Searching"]]
    context: Optional[Annotated[List[SearchResult], "Searched Documents"]]
    context_str: Optional[Annotated[str, "Searched Documents in String Format"]]
    document_usage: Optional[Annotated[Dict[int, Dict[str, Any]], "Document Usage"]]

    # document tracking for multi-loop consistency
    used_doc_indices: Optional[Annotated[List[int], "Document indices used in previous answer"]]
    not_used_doc_indices: Optional[Annotated[List[int], "Document indices not used in previous answer"]]
    prev_doc_count: Optional[Annotated[int, "Total document count from previous loop"]]

    # answer management
    answer: Optional[Annotated[str, "Draft/Final Answer"]]
    agent_response: Optional[Annotated[str, "Agent Response"]]

    # evaluation
    eval_result: Optional[Annotated[EvaluationResult, "Evaluation Result - Relevance and Completeness"]]
    previous_completeness: Optional[Annotated[float, "Previous Completeness"]]

    # control
    status: Literal["Initializing", "reasoning", "searching", "answering", "evaluating", "completed", "planning"] = "Initializing"
    loop_count: Annotated[int, "Number of loop"] = 0
    node_visits: Annotated[int, "Number of node visits"] = 0
    error: Optional[Annotated[str, "Error message for debugging"]]
    metadata: Annotated[ChatMetadata, "Chat Metadata - session_id, created_at, updated_at, user_preference"]
