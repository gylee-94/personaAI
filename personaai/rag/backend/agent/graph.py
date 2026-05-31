import os
import uuid
import functools
import asyncio
import torch
import glob
import logging
import re

from typing import Annotated, Literal, List
from pathlib import Path
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.agent_toolkits import FileManagementToolkit

from backend.agent.state import AgentState
from backend.agent.nodes import (
    intent_analysis_node,
    direct_answer,
    planner,
    execute_step,
    replanner,
    final_agent_answer,
    expand_query_node,
    retrieve_and_rerank_node,
    generate_answer_node,
    evaluate_answer_node,
    print_final_answer,
    fallback_node,
    human_approval,
)

from backend.agent.utils import (
    load_llm,
    get_reranker,
    get_search_tool,
)

from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool
from backend.tools.tavily import TavilySearch
from backend.tools.retrieval import DocumentRetrievalChain

from langchain_core.tools import tool
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langgraph.prebuilt import ToolNode, create_react_agent, InjectedState

from backend.agent.utils import logger

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Tools
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

@tool
def python_code_interpreter(code: str):
    """Call to execute python code."""
    return PythonAstREPLTool().invoke(code)

@tool
def get_cited_paper_source(state: Annotated[AgentState, InjectedState], ids: List[int]) -> str:
    """Get a cited paper sources in the string format from the previous answer using the ids.

    Args:
        ids: The id of the cited paper.

    Returns:
        A list of the cited paper sources.
        - You can get two types of sources:
            - url: The url of the cited paper.
            - local_file_path: The file name of the cited paper.
    """

    sources = []
    cited_papers = state.get("context_str")

    for id in ids:
        # Extract the full document content for the specific ID
        pattern =  f'---Document {id} \\(Source: (.*?)\\)---\\n(.*?)(?=---Document \\d+|---$)'
        match = re.search(pattern, cited_papers, re.DOTALL)

        # local file
        if getattr(match, "group", None):

            if len(match.group(1).split("(")) > 1:
                source = match.group(1).split("(")[0].strip()

                if len(source.split("/")) > 1:
                    sources.append({"id": id, "source": source.split("/")[-1].strip()})

                else:
                    sources.append({"id": id, "source": source.strip()})

            else:
                source = match.group(1).strip()

                if len(source.split("/")) > 1:
                    sources.append({"id": id, "source": source.split("/")[-1].strip()})

                else:
                    sources.append({"id": id, "source": source.strip()})

        # url
        else:
            pattern = f'---Document {id} \\(Source: (.*?)\\)---\\n(.*?)'
            match = re.search(pattern, cited_papers, re.DOTALL)
            sources.append({"id": id, "source": match.group(1).strip()})

    return sources

file_management_tools = FileManagementToolkit(root_dir="/data/users/gunho/projects/rag/docs/",
                                              selected_tools=["read_file", "file_search", "list_directory"]).get_tools()

tools = [python_code_interpreter, TavilySearch(max_results=3), get_cited_paper_source, *file_management_tools]
tool_node = ToolNode(tools)

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Initialization
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Initialize LLM
llm_name_or_path = os.getenv("OPENROUTER_MODEL", "google/gemini-3.5-flash")
llm = load_llm(llm_name_or_path, temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")))

if llm is None:
    raise ValueError("LLM is not loaded")
eval_llm = llm
logger.info(f"Using LLM: {llm_name_or_path}")

# Initialize search tool
retrievers_dict = get_search_tool()

# Initialize reranker
reranker_name_or_path = os.getenv("RERANKER_MODEL_PATH", "ms-marco-MultiBERT-L-12")
reranker_top_n = os.getenv("RERANKER_TOP_N", 3)
reranker_score_threshold = os.getenv("RERANKER_SCORE_THRESHOLD", 0.7)

reranker = get_reranker(reranker_name_or_path, top_n=reranker_top_n, score_threshold=reranker_score_threshold)
logger.info(f"Reranker configured: {bool(reranker)}")

MAX_SEARCH_ATTEMPTS=int(os.getenv("MAX_SEARCH_ATTEMPTS", 5))              # Maximum number of loops
MAX_WEB_SEARCH_ATTEMPTS=int(os.getenv("MAX_WEB_SEARCH_ATTEMPTS", 3))    # Maximum number of web search attempts
RELEVANCE_THRESHOLD=float(os.getenv("RELEVANCE_THRESHOLD", 0.7))        # Answer relevance threshold
COMPLETENESS_THRESHOLD=float(os.getenv("COMPLETENESS_THRESHOLD", 0.8))  # Answer completeness threshold
MIN_NEW_TOKENS=int(os.getenv("MIN_NEW_TOKENS", 3000))                   # Minimum number of tokens in the answer

# Define the graph
workflow = StateGraph(AgentState)

# Define the react agent
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant.",
        ),
        ("human", "{messages}"),
    ]
)
agent_executor = create_react_agent(llm, tools, prompt=prompt)

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Nodes
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

logger.info("Defining graph nodes...")

workflow.add_node("intent_analyzer", functools.partial(intent_analysis_node, llm=llm))

# Direct Answer
workflow.add_node("direct_answer", functools.partial(direct_answer, llm = llm))

# Agent Answer
# workflow.add_node("planner", functools.partial(planner, llm=llm))
# workflow.add_node("execute", functools.partial(execute_step, agent_executor=agent_executor))
# workflow.add_node("replanner", functools.partial(replanner, llm=llm))
# workflow.add_node("final_agent_answer", functools.partial(final_agent_answer, llm=llm))

# RAG process
workflow.add_node("expand_query", functools.partial(expand_query_node, llm=llm))
workflow.add_node("retriever", functools.partial(retrieve_and_rerank_node, llm=llm, retrievers=retrievers_dict, reranker=reranker))
workflow.add_node("generator", functools.partial(generate_answer_node, llm=llm, MIN_NEW_TOKENS=MIN_NEW_TOKENS))
workflow.add_node("evaluator", functools.partial(evaluate_answer_node, llm=eval_llm)) # Use evaluator_llm here
workflow.add_node("human_approval", human_approval)
workflow.add_node("fallback", functools.partial(fallback_node, llm=llm))
workflow.add_node("print_final_answer", functools.partial(print_final_answer, llm=llm))

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Edges
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

logger.info("Defining graph edges...")

# 1. Start: Intent Analysis
workflow.set_entry_point("intent_analyzer")

# 2. Branch based on the Intent Analysis result
def router_for_intent_analysis_result(state: AgentState) -> Literal["direct_answer", "planner", "expand_query", "fallback"]:
    """Decide whether to answer directly or perform a search based on the intent analysis result"""
    logger.debug("--- Deciding: Retrieve or Direct Answer ---")
    # On error, GOTO fallback
    if state.get("error"):
        logger.warning(f"Error before decision: {state['error']}")
        return "fallback"

    # If the task_type value is missing from the intent analysis result, GOTO fallback
    task_type = state.get("intent_analysis_result", {}).task_type
    if task_type is None:
        logger.warning("Intent analysis result missing 'task_type', defaulting to report generation.")
        state["error"] = "Intent analysis result missing 'task_type' by unknown reason. "
        return "fallback" # Default to retrieval if unsure

    # If the task_type value is "report", GOTO query expansion
    if task_type == "report":
        logger.info("Decision: report required, proceeding to expand query.")
        return "expand_query"

    # If the task_type value is "conversation", GOTO direct_answer
    elif task_type == "direct_answer":
        logger.info("Decision: Direct answer required.")
        return "direct_answer"

    # # If the task_type value is "planner", GOTO planner
    # elif task_type == "planner":
    #     logger.info(f"Decision: Planner required, proceeding to planner.")
    #     return "planner"

    else:
        logger.warning(f"Unknown task type: {task_type}, defaulting to report generation.")
        state["error"] = f"Unknown task type: {task_type}"
        return "fallback"

workflow.add_conditional_edges(
    "intent_analyzer",
    router_for_intent_analysis_result,
    {
        "direct_answer": "direct_answer",
        # "planner": "planner",
        "expand_query": "expand_query",
        "fallback": "fallback" # When intent analysis itself fails
    }
)

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Direct Answer
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Branch based on the Direct Answer result
def router_for_direct_answer(state: AgentState) -> Literal["end", "fallback"]:
    """Branch based on the Direct Answer result"""
    logger.debug("--- Deciding: Direct Answer Result ---")

    if state.get("error") is not None:
        logger.warning(f"Error before decision: {state['error']}")
        return "fallback"

    else:
        return "end"

workflow.add_conditional_edges(
    "direct_answer",
    router_for_direct_answer,
    {
        "end": END,
        "fallback": "fallback"
    }
)

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Agent Answer
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# workflow.add_edge("planner", "execute")
# workflow.add_edge("execute", "replanner")

def should_end(state: AgentState) -> Literal["execute", "final_agent_answer"]:
    """Decide whether to end the Agent Answer"""
    if "agent_response" in state and state["agent_response"]:
        return "final_agent_answer"

    else:
        return "execute"

# workflow.add_conditional_edges(
#     "replanner",
#     should_end,
#     {
#         "execute": "execute",
#         "final_agent_answer": "final_agent_answer",
#     }
# )

# workflow.add_edge("final_agent_answer", END)

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      RAG process
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# 4. Branch based on the query expansion result
def router_for_query_expansion(state: AgentState) -> Literal["expand_query", "retriever", "fallback"]:
    """Branch based on the query expansion result"""
    logger.debug("--- Deciding: Query Expansion Result ---")

    # On error, GOTO fallback (all exception and error handling is done inside the node)
    if state.get("error"):
        logger.warning(f"Error before decision: {state['error']}")
        return "fallback"

    elif state.get("sub_queries") is None and state.get("error") is None:
        logger.debug("Query expansion result is empty, but no error. Try again query expansion in loop.")
        return "expand_query"

    else:
        logger.debug("Query expansion result is valid, proceeding to retriever.")
        return "retriever"

workflow.add_conditional_edges(
    "expand_query",
    router_for_query_expansion,
    {
        "retriever": "retriever",
        "expand_query": "expand_query",
        "fallback": "fallback"
    }
)

# 5. Branch based on retrieval/reranking
def router_for_retrieval_result(state: AgentState) -> Literal["generator", "fallback"]:
    """Branch based on the retrieval/reranking result"""
    logger.debug("--- Deciding: Retrieval Result ---")

    # On error, GOTO fallback
    if state.get("error"):
        logger.error(f"Error in retrieval/reranking: {state['error']}")
        return "fallback"

    # Otherwise
    else:
        logger.debug("Retrieval result is valid, proceeding to answer generation.")
        return "generator"

workflow.add_conditional_edges(
    "retriever",
    router_for_retrieval_result,
    {
        "generator": "generator",
        "fallback": "fallback"
    }
)

# 6. Branch after answer generation
def router_for_answer_generation(state: AgentState) -> Literal["evaluator", "fallback"]:
    """Branch after answer generation"""
    logger.debug("--- Deciding: Answer Generation Result ---")

    # On error, GOTO fallback
    if state.get("error"):
        logger.error(f"Error in answer generation: {state['error']}")
        return "fallback"

    else:
        return "evaluator"

workflow.add_conditional_edges(
    "generator",
    router_for_answer_generation,
    {
        "evaluator": "evaluator",
        "fallback": "fallback"
    }
)

# 7. Branch based on the evaluation result (loop or end)
def decide_action_after_evaluation(state: AgentState) -> Literal["retriever", "print_final_answer", "fallback"]:
    """Decide the next action after evaluating the answer (loop back, end, fallback)"""
    logger.debug("--- Deciding: Loop, End, or Fallback after Evaluation ---")
    error = state.get("error")
    eval_result = state.get("eval_result")
    loop_count = state.get("loop_count", 0)

    if error:
        logger.warning(f"Error detected during evaluation or previous steps: {error}")
        # If an error already exists, go to fallback
        return "fallback"

    if not eval_result:
        logger.error("Evaluation result is missing after evaluator node ran!")
        return "fallback" # Abnormal if there is no evaluation result

    # human approval node
    if loop_count == 1 and eval_result.missing_info:
        logger.debug("First loop with missing info. Needs user approval to continue.")
        return "human_approval"

    # If there is missing info, proceed with the search
    elif eval_result.missing_info:
        logger.info(f"Decision: Answer insufficient - missing info: {eval_result.missing_info}")
        return "retriever"

    # If there is no missing info
    elif not eval_result.missing_info:
        logger.info(f"Decision: Answer sufficient (Rel: {eval_result.relevance}, Comp: {eval_result.completeness}). Ending.")
        return "print_final_answer"

    # final_answer when the maximum number of attempts is reached
    elif loop_count > MAX_SEARCH_ATTEMPTS: # TODO: A composite condition may be needed when web search is included
        logger.warning(f"Decision: Max attempts ({MAX_SEARCH_ATTEMPTS}) reached. Proceeding to print_final_answer.")
        return "print_final_answer"

    # Answer insufficient, continue
    else:
        logger.info(f"Decision: Answer insufficient (Rel: {eval_result.relevance}, Comp: {eval_result.completeness}). Looping back to retriever (Loop {loop_count+1}).")
        # Whether web search is needed in the next loop is determined by the retriever node based on the need_web_search flag
        return "retriever"

workflow.add_conditional_edges(
    "evaluator",
    decide_action_after_evaluation,
    {
        "retriever": "retriever",
        "human_approval": "human_approval",
        "print_final_answer": "print_final_answer",
        "fallback": "fallback"
    }
)

# 8. Output before ending
workflow.add_edge("print_final_answer", END)

# 9. End after fallback
workflow.add_edge("fallback", END)


# --- Compile the graph ---
logger.info("Compiling graph...")
# from langgraph.checkpoint.sqlite import SqliteSaver
# memory = SqliteSaver.from_conn_string("threads.sqlite")
graph = workflow.compile()
logger.info("Graph compiled successfully.")


async def test_app(input, config):
    async for chunk in graph.astream(input, config=config):
        for node, value in chunk.items():
            print(f"------------{node}------------")
            print(value, end="", flush=True)


# --- Example execution code ---
if __name__ == "__main__":
    thread_id = str(uuid.uuid4())
    config = RunnableConfig(resursion_limit = os.getenv("RECURSION_LIMIT", 30), configurable = {"thread_id": thread_id})

    print("\n--- Running Graph Example ---")
    # Define the initial state (including the user question)
    from langchain_core.messages import HumanMessage
    initial_state = AgentState(
        messages=[HumanMessage("Please explain how to measure frailty and also introduce the latest papers.")],
        # Other fields start with default values or None
        intent_analysis_result=None,
        sub_queries=None,
        context=None,
        answer=None,
        eval_result=None,
        status="Initializing",
        loop_count=0,
        node_visits=0,
        error=None,
        metadata=None # Create a ChatMetadata object if needed
    )

    asyncio.run(test_app(initial_state, config))
