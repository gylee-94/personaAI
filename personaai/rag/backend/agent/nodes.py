import os
import uuid
import logging
import re
import asyncio


from pydantic import ValidationError
from typing import Dict, List, Optional, Union, Any, Literal

from dotenv import load_dotenv


from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool
from langchain_community.document_compressors import FlashrankRerank
from langchain_core.documents import Document
from langchain_core.runnables import RunnableConfig
from langchain_classic.retrievers import ContextualCompressionRetriever

from langgraph.types import interrupt, Command

from backend.agent.state import AgentState, SearchResult, SubQuestion, IntentAnalysisResult, EvaluationResult, ChatMetadata, Plan, Act, Response
from backend.agent.utils import update_status_and_visit, merge_and_deduplicate_context, format_search_results

from langgraph.prebuilt.interrupt import (
    ActionRequest,
    HumanInterrupt,
    HumanInterruptConfig,
    HumanResponse,
)

# ! ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Initialization
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

from backend.agent.utils import logger

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

MAX_SEARCH_ATTEMPTS = int(os.getenv("MAX_SEARCH_ATTEMPTS", 5))
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", 0.7))
COMPLETENESS_THRESHOLD = float(os.getenv("COMPLETENESS_THRESHOLD", 0.8))

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Task description
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

async def generate_dynamic_message(llm: BaseChatModel, context: dict) -> str:
    """Use the LLM to generate a dynamic message that tells the user what task the next node to be executed will perform."""

    system_prompt = """You are a professional and helpful AI assistant.

## Role:
- Your role is to generate a concise, user-friendly message that informs the user about the **next step** your system is about to take.
- This message should explain the purpose of the upcoming processing node.
- Phrase the message as if you (the AI) are about to perform the action.

## Response guidelines:
- Keep the message short, clear, and directly related to the node's purpose.

## Before generating the message:
- You need to consider the workflow to determine under what circumstances the next step is performed.
- The loop_count and next_task variables are very important in determining what the situation is, so you need to focus on them.

## Workflow:
1. intent analysis
2. expand query
    - Expand the user query for more detailed information for better retrieval.
3. retrieve and rerank
    - Each time you enter that node, loop_count is incremented by 1.
    - Default loop_count is 0 and maximum loop_count is 5.
4. generate answer
    - Generate draft answer using the retrieved context.
5. evaluate answer
    - If loop_count is 1, go to human_approval node.
        - If user ignores the draft answer in human_approval node, go back to 3. retrieve and rerank.
        - If user approves the draft answer in human_approval node, go to 6. print final answer.
    - If the answer is not satified the threshold and loop_count is bigger than 1, go back to 3. retrieve and rerank.
    - If the answer is satified the threshold and loop_count is bigger than 1, go to 6. print final answer.
6. print final answer

## Example:
1. next_task is "expand query" and loop_count is 0.
    - I will expand the query to retrieve more detailed information.
    - I will perform query expansion to search for detailed information.
2. next_task is "retrieve and rerank" and loop_count is 0.
    - I will perform a search for the expanded query.
3. next_task is "retrieve and rerank" and loop_count is 1.
    - I will perform an additional search to supplement the missing information.
    - There is information missing from the generated draft. I will perform an additional search.
4. next_task is "generate answer" and loop_count is 1.
    - I will generate a draft answer.
5. next_task is "generate answer" and loop_count is bigger than 1.
    - I will revise the draft answer.
    - I will revise the draft answer based on the additionally retrieved information.
6. next_task is "evaluate answer". (in this case, loop_count is not important.)
    - I will evaluate the draft answer and determine whether any information is missing.
    - I will proceed with the draft answer evaluation process.
7. next_task is "human_approval" and loop_count is 1.
    - I have generated the following draft in the first workflow loop. If you would like to run more loops, please press the Ignore button; if you would like to use this draft as the final result, please press the Accept button below.
8. next_task is "print final answer". (in this case, loop_count is not important.)
    - I will now output the final answer.
    - I have completed the final answer. I will output the final answer without any additional search."""

    # Extract needed information from the context dictionary (with default values)
    loop_count = context.get('loop_count', 0)
    next_task = context.get('next_task', 'next step')

    # Define the user prompt template
    user_prompt = """
The system is about to proceed to the next step:
- Next task: {next_task}
- Loop count: {loop_count}

Based on this information, create a message that concisely and clearly tells the user in your language what the system will do next.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])

    chain = prompt | llm | StrOutputParser()

    # When calling the LLM, pass the values extracted from context
    response = await chain.ainvoke(
        {
            "next_task": next_task,
            "loop_count": loop_count
        },
        config=RunnableConfig(callbacks=[])
    )

    return response.strip()

# ! ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Nodes
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

async def intent_analysis_node(state: AgentState, llm: BaseChatModel) -> AgentState:
    """(Step 2) Analyze the intent of the user input to decide whether RAG is needed."""
    # Update node tracking
    updated = update_status_and_visit(state, "reasoning")
    updated.update({"loop_count": 0})

    # Process user input
    messages = state["messages"]
    previous_answer = state.get("answer", "")
    # answer may be passed as a list, so convert it to a string
    if isinstance(previous_answer, list):
        previous_answer = "\n".join(str(item) for item in previous_answer) if previous_answer else ""

    if not messages or not isinstance(messages[-1], HumanMessage):        # If the last message is not user input, GOTO Fallback (implemented in Graph)
        updated.update({"status": "completed"})
        logger.error("[Error] No user input found for intent analysis.")
        return {
            **updated,
            "error": "No user input found for intent analysis."
        }
    user_query = messages[-1].content # User input

    # format_instructions is not needed when using with_structured_output
    # parser = JsonOutputParser(pydantic_object=IntentAnalysisResult)
    # format_instructions = parser.get_format_instructions().replace('{', '{{').replace('}', '}}')

    # Generate an additional prompt depending on whether a previous answer exists
    # previous_answer may contain braces, so escape them
    escaped_previous_answer = previous_answer.replace('{', '{{').replace('}', '}}') if previous_answer else ""

    previous_answer_context = f"""
## Previous Answer Context
The user's query follows a previous response. Consider these additional aspects:

1. **Query-Answer Relationship**
   - Is this a follow-up question to the previous answer?
   - Does it seek clarification of previous content?
   - Is it exploring a new aspect of the previously discussed topic?
   - Is it a completely new topic?
   - Does it challenge or question assumptions from the previous answer?
   - Does it request evidence or sources for previous claims?

2. **Context Continuity**
   - Identify any references to concepts from the previous answer
   - Note any pronouns ("it", "that", "these", etc.) referring to previous content
   - Consider if the previous context adds depth to the current query
   - Track any conceptual threads being developed across questions

3. **Analysis Depth Progression**
   - Does this query dive deeper into previously discussed concepts?
   - Is it broadening the scope of the previous discussion?
   - Does it require integrating previous information with new aspects?
   - Is it seeking more specific examples or evidence?
   - Does it request more detailed explanations of mechanisms or processes?
   - Is it exploring edge cases or exceptions to previously stated principles?

4. **Complexity Indicators in Follow-up Questions**
   - **Mechanism Queries**: Questions about "how" something works in detail
   - **Causal Analysis**: Questions about "why" that require deep explanation
   - **Integration Requests**: Questions that ask to connect multiple concepts
   - **Evidence Demands**: Requests for research support or empirical data
   - **Comparative Analysis**: Questions that ask to compare or contrast concepts
   - **Edge Cases**: Questions about exceptions or special conditions
   - **Theoretical Framework**: Questions about underlying principles or models

5. **Examples of Deep Follow-up Questions (Report Required)**
   - "Please explain in more detail the genetic risk factors for cardiovascular disease you just described, from a molecular biology perspective"
   - "I would like to know more about the impact of the previously mentioned lifestyle factors on the onset of diabetes"
   - "Please explain how the biomarker indicators described earlier are applied in actual disease prediction, with specific research examples"

6. **Examples of Simple Follow-up Questions (Direct Answer Sufficient)**
   - "Could you explain what you just said a bit more simply?"
   - "What does that scientific name mean?"
   - "Can we move on to the next topic?"

## Examples of Main Topics for Follow-up Questions:
### Given variables:
- "user query": "Tell me about the related biomarkers"
- "previous answer": "An in-depth report on the genetic factors and lifestyle risk factors of cardiovascular disease ..."

### Generated main topics:
- ["cardiovascular disease biomarkers", "genetic risk indicators"]

Previous Answer:
{escaped_previous_answer}

Remember to consider this context when determining if the current query requires a detailed report or a conversational response. Pay special attention to whether follow-up questions are seeking deeper understanding (requiring report) or simple clarification (conversation sufficient).
""" if previous_answer else ""

    system_prompt = f"""## System Instruction
You are an expert AI system designed to analyze user queries and determine the appropriate response format, with a particular focus on identifying queries that require in-depth academic analysis.

## Core Objective
Analyze user queries to determine:
1. Whether the query requires comprehensive research and analysis ("report" type)
2. Or if it can be handled through simple conversation ("conversation" type)
3. The main topics of the query

## Query Analysis Framework

### Topic Analysis Guidelines
1. **Main Topic Identification**
   - Identify the central concept or primary subject of inquiry
   - For research-focused queries, this is often a key scientific concept or phenomenon
   - For medical queries, this might be a specific condition, treatment, or biological process
   - Examples:
     * Query: "Tell me about the person who proposed cognitive reserve and the people who have produced major research achievements"
       - Main Topics: ["The person who suggested cognitive reserve", "People who have done a lot of research on cognitive reserve"]
     * Query: "Explain the relationship between frailty and multimorbidity and tell me the most essential papers"
       - Main Topics: ["frailty and multimorbidity relationship", "key papers on frailty and multimorbidity"]
     * Query: "hi?", "hey", "hi", "hello", ...
       - Main Topics: ["greeting and typical conversation"]
     * Query: "how's the weather today?", "how's the weather today?"
       - Main Topics: ["today's weather"]
     * Query: "I had such a hard day today.", "I'm so tired today.", "I'm feeling so down today.", "I'm bored", ...
       - Main Topics: ["emotionally down and typical conversation"]
     * Query: "I need to analyze a cognitive dataset in the previous answer"
       - Main Topics: ["data analysis and data visualization"]
     * Query: "I want to read a paper [23] cited in the previous answer"
       - Main Topics: ["Read the cited paper #23 and explain what it says"]

2. **Sub-topics Extraction**
   - Identify related concepts, aspects, or specific areas of investigation
   - Consider measurement methods, historical development, key researchers, etc.
   - Include relevant methodologies, frameworks, or analytical approaches
   - Examples:
     * For cognitive reserve query:
       - Sub-topics: ["key papers on cognitive reserve", "research achievements of cognitive reserve", "assessment methods of cognitive reserve"]
     * For frailty query:
       - Sub-topics: ["relationship mechanisms between frailty and multimorbidity", "key papers on frailty and multimorbidity", "clinical implications of frailty and multimorbidity", "assessment methods of frailty and multimorbidity"]
     * For typical conversation querys:
       - Sub-topics: []
     * For weather query:
       - Sub-topics: []
     * For emotional state query:
       - Sub-topics: []

### Indicators for "report" Type Queries:
1. **Academic/Research Focus**
   - Questions about research history, key researchers, or pioneering studies
   - Requests for analysis of scientific concepts or relationships
   - Queries about methodologies, measurements, or indices
   - Questions requiring citation of specific papers or studies

2. **Complex Relationships**
   - Questions about relationships between multiple concepts
   - Requests for analysis of cause-and-effect relationships
   - Queries about systemic interactions or mechanisms

3. **Evidence-Based Information**
   - Requests for specific research findings
   - Questions about clinical trials or study results
   - Queries requiring statistical or empirical evidence

4. **Historical Development**
   - Questions about the evolution of concepts
   - Requests for information about key contributors
   - Queries about major developments in a field

5. **Comprehensive Analysis**
   - If a user requests a detailed report, the query should be classified as "report"
   - Questions requiring multiple perspectives
   - Queries about complex medical or scientific concepts

6. **Continuation of Previous Answer**
   - If the user is asking for a more detailed explanation rather than a simple explanation of the previous answer, the question should be categorized as a "report" type.
   - This is when the previous question contains modifiers such as "more," "in more depth," "in more detail," etc.
   - Examples:
     * Query: "Please explain the mechanism of cognitive reserve you just described in more detail from a neurobiological perspective"
     * Query: "I would like to know more about the interaction effects among the previously mentioned dementia risk factors"
     * Query: "Please explain how the frailty assessment indicators described earlier are applied in actual clinical practice, with specific research examples"
     * Query: "Tell me about the related biomarkers"

### Indicators for "conversation" Type Queries:
1. Simple greetings or acknowledgments
2. Basic clarification questions about the previous answer (without requiring new research)
3. Follow-up questions seeking simple elaboration of previous points
4. Personal preferences or opinions
5. Simple yes/no questions
6. Basic factual queries

## Example Queries Requiring "report" Type:
- "Tell me about the person who proposed cognitive reserve and the people who have produced major research achievements"
- "Explain the relationship between frailty and multimorbidity and tell me the most essential papers"
- "Tell me about the most recent clinical trials being conducted in relation to dementia"
- "Please list the risk factors and candidates mentioned in the dementia Lancet report that is published every four years"
- "Please explain in more detail the relationship between the cognitive reserve you just described and Alzheimer's disease" (follow-up requiring deeper analysis)

## Example Queries Suitable for "conversation" Type:
- "Hello"
- "How's the weather today?"
- "How are you feeling today?"
- "I had such a hard day today..."
- "What does that mean?"
- "Please explain the previous answer again"
- "Yes, I understand"
- "Could you explain what you just said a bit more simply?" (simple clarification)

## Output Requirements
Respond with a JSON object following this schema:
{format_instructions}

## Analysis Process:
1. Identify key concepts and relationships in the query
2. If previous answer exists, analyze the relationship between the current query and previous content
3. Assess the complexity and depth of information required
4. Evaluate whether the query needs academic/research evidence
5. Determine if multiple perspectives or sources are needed
6. Consider whether historical context or development is relevant

## Response Guidelines:
- Be conservative in classifying queries as "conversation"
- When in doubt, choose "report" for queries that might need detailed analysis
- Consider the potential need for citations and references
- Evaluate whether the answer would benefit from structured sections
- Assess if multiple academic sources might be needed
- For follow-up questions, carefully evaluate if they require new research or just clarification
- Main topics and sub-topics must be written in **english**.

Remember: The goal is to ensure that queries requiring deep analysis and academic rigor are properly identified and handled with the appropriate level of detail and structure.

{previous_answer_context}
"""

    # Use JsonOutputParser (with_structured_output has compatibility issues with Gemini)
    parser = JsonOutputParser(pydantic_object=IntentAnalysisResult)

    # Use partial to escape braces in the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Analyze the following user query:\n\nUser Query:\n{user_query}")
    ])

    chain = prompt | llm | parser

    # Validate output and store values
    try:
        response_dict = await chain.ainvoke({"user_query": user_query})
        response = IntentAnalysisResult(**response_dict)

        # Add debugging logs
        logger.info(f"[DEBUG] Raw LLM Response: {response}")
        logger.info(f"[DEBUG] Response type: {type(response)}")
        if response:
            logger.info(f"[DEBUG] Response dict: {response.model_dump() if hasattr(response, 'model_dump') else response}")
        else:
            logger.warning(f"[DEBUG] Response is None or empty!")
            # If Response is None, handle it with default values
            user_query_content = state["messages"][-1].content if state.get("messages") and isinstance(state["messages"][-1], HumanMessage) else ""
            updated.update({"status": "completed"})
            return {
                **updated,
                "intent_analysis_result": IntentAnalysisResult(
                    user_query=user_query_content,
                    reasoning_result="LLM returned None response. Using default values.",
                    task_type="report",
                    main_topics=[],
                    sub_topics=[],
                ),
                "error": "LLM response was None"
            }

        # async for chunk in response:

        try: # Attempt conversion to a Pydantic model (stricter validation) - may need adjustment.
            analysis_result = response #IntentAnalysisResult(**response)
            logger.debug(f"Intent Analysis Result:\n\ntask_type:\n{analysis_result.task_type}\n\nreasoning_result:\n{analysis_result.reasoning_result}")
            updated.update({"status": "completed"})

            if analysis_result.task_type == "report":
                # Description of the next task
                next_task_description = await generate_dynamic_message(llm, {"next_task": "expand query", "loop_count": state.get("loop_count", 0)})

                return {
                    "messages": [AIMessage(content=next_task_description)],
                    **updated,
                    "intent_analysis_result": analysis_result,
                    "error": None
                }

            else:
                return {
                    **updated,
                    "intent_analysis_result": analysis_result,
                    "error": None
                }

        except ValidationError as ve:
            logger.error(f"Following Error occurred while parsing the LLM response. Please check the response and try again:\nPydantic validation failed for IntentAnalysisResult: {ve}. Raw response: {response}")
            user_query_content = state["messages"][-1].content if state.get("messages") and isinstance(state["messages"][-1], HumanMessage) else ""
            updated.update({"status": "completed"})

            return {
                **updated,
                "intent_analysis_result": IntentAnalysisResult(
                    user_query=user_query_content,
                    reasoning_result="LLM response validation failed.",
                    task_type="report",  # Set report as the default value
                    main_topics=[],
                    sub_topics=[],
                ),
                "error": f"Pydantic validation failed for IntentAnalysisResult: {ve}. Raw response: {response}"
            }

    except Exception as e:
        logger.exception(f"Following Error occurred while parsing the LLM response. Please check the response and try again:\nIntent analysis failed.")
        user_query_content = state["messages"][-1].content if state.get("messages") and isinstance(state["messages"][-1], HumanMessage) else ""
        updated.update({"status": "completed"})
        return {
            **updated,
            "intent_analysis_result": IntentAnalysisResult(
                user_query=user_query_content,
                reasoning_result="Intent analysis process failed. Setting default values.",
                task_type="report",  # Set report as the default value
                main_topics=[],
                sub_topics=[],
            ),
            "error": f"Intent analysis failed: {e}"
        }

# ! ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Direct Answer
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

async def direct_answer(state: AgentState, llm: BaseChatModel) -> AgentState:
    """(Step 2a) The LLM generates an answer directly without producing a report."""
    # Update node tracking
    updated = update_status_and_visit(state, "answering")

    # Process user input
    messages = state.get("messages", [])

    previous_answer = state.get("answer", "")
    # If the previous answer is a list, convert it to a string
    if isinstance(previous_answer, list):
        previous_answer = "\n".join(str(item) for item in previous_answer) if previous_answer else ""
    intent_result = state.get("intent_analysis_result")

    if not intent_result:
        logger.error("[Error] Intent analysis result missing.")
        updated.update({"status": "completed"})
        return {
            **updated,
            "error": "Intent analysis result missing."
        }

    main_topics = intent_result.main_topics if intent_result else []
    user_query = messages[-1].content

    # previous_answer may contain braces, so escape them
    escaped_previous_answer = previous_answer.replace('{', '{{').replace('}', '}}') if previous_answer else ""

    if not main_topics:
        logger.error("[Error] Main topics missing for answer generation.")
        updated.update({"status": "completed"})
        return {
            **updated,
            "error": "Main topics missing for answer generation."
        }

    system_prompt = f"""## Role and Objective
You are an expert AI assistant specializing in the aging literature corpus and aging-related biomedical research. Your role is to provide clear, accurate, and helpful responses without generating formal research reports.

## Current Query Focus
Main Topics to Address: {main_topics}

## Core Capabilities
1. Topic-Focused Answering
   - Address each main topic identified in the query
   - Ensure comprehensive coverage of all topics
   - Maintain logical flow between different topics
   - Prioritize most relevant information for each topic

2. Direct Question Answering
   - Provide clear, concise answers
   - Use natural, conversational language while maintaining professional accuracy
   - Break down complex concepts into understandable explanations

3. Context Awareness
   - Consider previous answers when providing explanations
   - Maintain consistency with previously shared information
   - Build upon established concepts progressively

4. Clarification and Simplification
   - Explain technical terms when used
   - Provide analogies or examples when helpful
   - Adjust explanation complexity based on the context

## Response Guidelines

### Topic Coverage Structure
1. **For Each Main Topic**
   - Provide a clear, focused response
   - Ensure adequate depth without being overly technical
   - Connect related concepts when relevant
   - Maintain balance between topics

2. **Integration**
   - Show relationships between topics when relevant
   - Maintain logical flow between different topics
   - Ensure consistent level of detail across topics

3. **Language**
   - Use natural, conversational language
   - Avoid overly technical language unless necessary
   - When technical terms are used, provide brief explanations

### When Previous Answer Exists
Consider:
1. Reference relevant parts of the previous answer
2. Maintain consistency with previously shared information
3. Clarify any points from the previous answer if needed
4. Build upon the established knowledge
5. Address any specific aspects the user is asking about

### Response Structure
1. **Direct Answer**
   - Address each main topic clearly
   - Be concise but informative
   - Use natural language

2. **Explanation**
   - Provide context if needed
   - Break down complex concepts
   - Use examples or analogies when helpful

3. **Clarification**
   - Define technical terms
   - Explain relationships between concepts
   - Address potential points of confusion

### Language Style
- Use clear, professional language
- Maintain a conversational tone while ensuring accuracy
- Avoid overly technical language unless necessary
- When technical terms are used, provide brief explanations

### Important Considerations
- Focus on accuracy and clarity
- Be direct and concise
- Acknowledge limitations of current knowledge when appropriate
- Maintain a helpful and professional tone
- If a topic requires deeper research or evidence, acknowledge this

Remember: Your goal is to provide helpful, accurate information in a conversational manner while maintaining scientific accuracy and professional credibility.

Previous Answer Context:
{previous_answer}

Remember: Your goal is to provide helpful, accurate information in a conversational manner while maintaining scientific accuracy and professional credibility.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "\n## Query source:\n{query}")
    ])
    # StrOutputParser removed
    chain = prompt | llm

    try:
        # response is now an AIMessage object
        response: AIMessage = await chain.ainvoke({"query": user_query})
        # Return a dictionary for the state update
        updated.update({"status": "completed", "node_visits": 0, "loop_count": 0})
        return {
            "messages": [response],
            "answer": response.content,
            **updated,
            "error": None
            }

    except Exception as e:
        logger.exception(f"[Error] Answer generation failed.")
        updated.update({"status": "completed"})

        return {
            **updated,
            "answer": f"Error: Answer generation failed. {e}",
            "error": f"Answer generation failed: {e}"
        }

# ! ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      Planner
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

async def planner(state: AgentState, llm: BaseChatModel) -> AgentState:
    """(Step 3a) Generate a plan for the LLM to directly produce an answer without generating a report."""
    # Update node tracking
    updated = update_status_and_visit(state, "planning")

    # Process user input
    messages = state.get("messages", [])

    previous_answer = state.get("answer", "")
    # If the previous answer is a list, convert it to a string
    if isinstance(previous_answer, list):
        previous_answer = "\n".join(str(item) for item in previous_answer) if previous_answer else ""
    intent_result = state.get("intent_analysis_result")

    if not intent_result:
        logger.error("[Error] Intent analysis result missing.")
        updated.update({"status": "completed"})
        return {
            **updated,
            "error": "Intent analysis result missing."
        }

    main_topics = intent_result.main_topics if intent_result else []
    user_query = intent_result.user_query if intent_result else ""

    # previous_answer may contain braces, so escape them
    escaped_previous_answer = previous_answer.replace('{', '{{').replace('}', '}}') if previous_answer else ""

    if not main_topics:
        logger.error("[Error] Main topics missing for answer generation.")
        updated.update({"status": "completed"})
        return {
            **updated,
            "error": "Main topics missing for answer generation."
        }

    system_prompt = f"""## Role and Objective
### Role
You are an expert AI assistant specializing in aging literature corpus and aging-related biomedical research.

### Objective
For the given objective, come up with a simple step by step plan.
- This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps.
- The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.

### Guidelines
- If there is previous answer, consider the relationship between the current query and previous content.

## Previous Answer Context:
{previous_answer}

Remember: Your goal is to provide detailed step by step plan to answer the user's query.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "\n## User's Query:\n{user_query}\n\n## Main Topics:\n{main_topics}")
    ])
    # StrOutputParser removed
    chain = prompt | llm.with_structured_output(Plan)

    try:

        response: Plan = await chain.ainvoke({"user_query": user_query, "main_topics": main_topics},
                                             config=RunnableConfig(callbacks=[]))

        updated.update({"status": "completed", "node_visits": 0, "loop_count": 0})
        return {
            **updated,
            "plan": response.steps,
            "error": None
            }

    except Exception as e:
        logger.exception(f"[Error] Answer generation failed.")
        updated.update({"status": "completed"})

        return {
            **updated,
            "plan": f"Error: Plan generation failed. {e}",
            "error": f"Plan generation failed: {e}"
        }

async def execute_step(state: AgentState, agent_executor) -> AgentState:
    """(Step 3b) Execute each step according to the plan and return the result"""
    plan = state.get("plan")

    plan_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
    task = plan[0]

    task_formatted = f"""For the following plan:
{plan_str}\n\nYou are tasked with executing [step 1. {task}]."""

    agent_response = await agent_executor.ainvoke({"messages": [("user", task_formatted)]},
                                                   config=RunnableConfig(callbacks=[]))

    return {
        "past_steps": [(task, agent_response["messages"][-1].content)]
    }

async def replanner(state: AgentState, llm: BaseChatModel) -> AgentState:
    """(Step 3c) Update the plan based on the result of the previous step, or return the final response"""
    user_query = state.get("intent_analysis_result").user_query
    plan = state.get("plan")
    past_steps = state.get("past_steps")


    system_prompt = """For the given objective, come up with a simple step by step plan. \
This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. \
The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.

Your objective was this:
{user_query}

Your original plan was this:
{plan}

You have currently done the follow steps:
{past_steps}

Update your plan accordingly. If no more steps are needed and you can return to the user, then respond with that. Otherwise, fill out the plan. Only add steps to the plan that still NEED to be done. Do not return previously done steps as part of the plan.
 """

    prompt = ChatPromptTemplate.from_template(system_prompt)
    chain = prompt | llm.with_structured_output(Act)

    response: Act = await chain.ainvoke({"user_query": user_query, "plan": plan, "past_steps": past_steps},
                                        config=RunnableConfig(callbacks=[]))

    if isinstance(response.action, Response):
        return {
            "agent_response": response.action.response
        }

    else:
        next_plan = response.action.steps
        if len(next_plan) == 0:
            return {"agent_response": "No more steps needed"}

        else:
            return {"plan": next_plan}


async def final_agent_answer(state: AgentState, llm: BaseChatModel) -> AgentState:
    """(Step 3d) Generate the final answer"""

    user_query = state.get("intent_analysis_result").user_query

    past_steps = "\n\n".join(
        [
            f"Question: {past_step[0]}\n\nAnswer: {past_step[1]}\n\n####"
            for past_step in state.get("past_steps", [])
        ]
    )

    system_prompt = """
You are given the objective and the previously done steps. Your task is to generate a final report in markdown format.
Final report should be written in professional tone.

Your objective was this:

{user_query}

Your previously done steps(question and answer pairs):

{past_steps}

Generate a final report in markdown format.
"""

    prompt = ChatPromptTemplate.from_template(system_prompt)
    chain = prompt | llm | StrOutputParser()

    response = await chain.ainvoke({"user_query": user_query, "past_steps": past_steps},
                                   config=RunnableConfig(callbacks=[]))

    return {
        "messages": [response],
        "answer": response,
        "agent_response": response,
        "status": "completed"
    }

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                                      RAG process
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



async def expand_query_node(state: AgentState, llm: BaseChatModel) -> AgentState:
    """(Step 3) Expand the query for RAG or web search and decide the search method."""
    # Update state
    updated = update_status_and_visit(state, "searching")

    intent_result = state.get("intent_analysis_result")
    main_topics = intent_result.main_topics if intent_result else []

    if not main_topics:
        logger.error(f"[Error] Expand_Query_Node: Main topics missing.")
        updated.update({"status": "completed"})

        return {
            **updated,
            "error": f"[Error] Expand_Query_Node: Main topics missing."
        }

    # --- Prompt selection ---
    parser = JsonOutputParser(pydantic_object=SubQuestion)
    format_instructions = parser.get_format_instructions().replace('{', '{{').replace('}', '}}')

    system_prompt = f"""You are an expert in creating queries for searching Vector databases.
Your task is to expand each main topic into specific search queries that will effectively retrieve relevant information.

## Core Objectives
1. Generate focused search queries for each main topic
2. Ensure comprehensive coverage of all aspects of each topic
3. Create queries that will retrieve both broad context and specific details

## Vector Database Search Requirements
1. **Precision**
   - Each query must directly relate to one or more main topics
   - Focus on key concepts, relationships, and specific aspects
   - Include technical terms and their variations when relevant

2. **Semantic Richness**
   - Include related concepts and synonyms
   - Consider different phrasings and terminology
   - Incorporate domain-specific vocabulary

3. **Query Structure**
   - Each query should be 5-8 words long
   - Use specific, unambiguous terms
   - Include key identifiers and qualifiers
   - Must written in english

## Query Generation Guidelines

### For Each Main Topic:
1. **Core Concept Queries**
   - Create queries focusing on fundamental aspects
   - Include definition and basic explanation searches
   - Target key characteristics and properties

2. **Relationship Queries**
   - Generate queries about connections with other concepts
   - Include cause-effect relationships
   - Consider system-level interactions

3. **Detail-Specific Queries**
   - Create queries for specific aspects or components
   - Include measurement or assessment methods
   - Target practical applications or implications

### Query Optimization:
- Break complex topics into searchable components
- Ensure coverage of all critical aspects
- Balance breadth and depth of search
- Avoid overly general or vague terms
- Use precise technical terminology when appropriate

The response format should follow this JSON schema:
{format_instructions}

## Example:
Main Topics: ["cognitive reserve definition", "cognitive reserve measurement methods"]

Generated Sub-queries (JSON):
```json
{{{{
    "expanded_query": [
        "cognitive reserve definition mechanisms brain",
        "cognitive reserve measurement clinical assessment",
        "cognitive reserve evaluation methods research",
        "cognitive reserve indicators markers tests"
    ]
}}}}
```
"""

    user_prompt = "## Main Topics to Expand:\n{main_topics}\n\nGenerate focused search queries for each main topic:"

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])

    chain = prompt | llm.with_structured_output(SubQuestion)

    try:
        response: Dict = await chain.ainvoke({"main_topics": main_topics}, config=RunnableConfig(callbacks=[])) # JSON to Dict
        sub_queries_list = response.expanded_query

        logger.debug(f"Expand_Query_Node: Generated {len(sub_queries_list)} sub-queries.")
        sub_queries_obj = response #SubQuestion(expanded_query=sub_queries_list)

            # Generate the list of search queries to show the user
        search_queries_text = "\n".join([f"- {q}" for q in sub_queries_list])
        message_content = f"""Generated Sub-queries:
{search_queries_text}
"""
        next_task_description = await generate_dynamic_message(llm, {"next_task": "retrieve and rerank", "loop_count": state.get("loop_count", 0)})

        return {
            "messages": [ToolMessage(
                name="expand_query",
                content=message_content,
                tool_call_id=f"progress_{uuid.uuid4().hex}", # Dummy Tool Call ID
            ), AIMessage(content=next_task_description)],
                **updated,
                "sub_queries": sub_queries_obj,
                "error": None
            }

    except Exception as e:
        logger.exception(f"[Error] Expand_Query_Node: {e}")
        updated.update({"status": "completed"})

        return {
            **updated,
            "error": f"Expand_Query_Node: {e}"
        }

# ------ Step 4: Search and rerank ------
async def retrieve_and_rerank_node(state: AgentState,
                                   llm: BaseChatModel,
                                   retrievers: Dict[str, Optional[Union[BaseRetriever, BaseTool]]], # Retrievers are passed as a Dict.
                                   reranker: Optional[FlashrankRerank]) -> AgentState:
    """(Step 4) Use the expanded queries to retrieve and rerank documents from RAG or the web."""
    updated = update_status_and_visit(state, "searching")

    loop_count = int(state.get("loop_count", 0)) + 1
    updated.update({"loop_count": loop_count})

    if loop_count > MAX_SEARCH_ATTEMPTS:
        logger.warning(f"[Warning] Search_Node: Max search attempts ({MAX_SEARCH_ATTEMPTS}) reached. Proceeding to fallback.")
        return {
            **updated,
            "error": f"Search_Node: Max search attempts ({MAX_SEARCH_ATTEMPTS}) reached. Proceeding to fallback."
        }

    if loop_count == 1:
        sub_queries: Optional[SubQuestion] = state.get("sub_queries")

        if not sub_queries or not sub_queries.expanded_query:
            logger.error("[Error] Search_Node: Sub-queries missing or empty for retrieval.")
            updated.update({"status": "completed"})

            return {
                **updated,
                "error": "Search_Node: Sub-queries missing or empty for retrieval."
            }

        sub_queries = sub_queries.expanded_query
        existing_context: Optional[List[SearchResult]] = []
        prev_doc_count = 0

    else:
        sub_queries = state.get("eval_result").missing_info
        existing_context: Optional[List[SearchResult]] = state.get("context")
        # Count the number of documents in the existing context (to determine the new document start index)
        prev_doc_count = sum(len(r.documents) for r in existing_context) if existing_context else 0
        logger.info(f"Search_Node: Previous document count: {prev_doc_count}, new documents will start from index {prev_doc_count + 1}")

    if not retrievers:
        logger.error("[Critical Error] Search_Node: Retrievers dictionary not provided to retrieve_and_rerank_node!")
        updated.update({"status": "completed"})

        return {
            **updated,
            "error": "Search_Node: Retriever configuration missing."
        }

    # initializing variables
    all_new_results: List[SearchResult] = []
        # class SearchResult(BaseModel):
        #     question: str = Field(description="Question that used for search")
        #     documents:List[Document] = Field(description="Search Result")

    # Attempt document retrieval
    logger.debug("--- Performing retrieval based on sub_queries ---")
    for sub_q in sub_queries:
        retriever = retrievers.get("semantic") # Load retriever
        web_search = retrievers.get("web") # Load retriever

        # If there is no retriever
        if not retriever:
            logger.warning(f"[Warning] Search_Node: Retriever/Tool for method 'semantic' not found. Skipping query: '{sub_q}'")
            continue # Move on to the next query. This could probably be improved further.

        # Attempt search
        logger.debug(f"Retrieving (Method: semantic): '{sub_q}'")
        retrieved_docs: List[Document] = []

        try:
            # Use document retrieval (with timeout retry logic added)
            if isinstance(retriever, BaseRetriever):
                retriever = ContextualCompressionRetriever(base_compressor = reranker, base_retriever = retriever)

                # Mitigate timeout issues with retry logic
                max_retries = 3
                retrieved_docs: List[Document] = []

                for retry_count in range(max_retries):
                    try:
                        retrieved_docs = await retriever.ainvoke(input = sub_q)
                        if retry_count > 0:  # If it succeeded on a retry
                            logger.info(f"Search_Node: Retrieval succeeded on attempt {retry_count + 1}")
                        break  # Exit the loop on success
                    except Exception as retrieval_error:
                        error_msg = str(retrieval_error)
                        if retry_count < max_retries - 1:  # If it is not the last attempt
                            wait_time = 2 ** retry_count  # Exponential backoff: 1s, 2s, 4s
                            logger.warning(f"Search_Node: Retrieval attempt {retry_count + 1}/{max_retries} failed: {error_msg[:150]}... Waiting {wait_time}s before retry...")
                            await asyncio.sleep(wait_time)
                        else:
                            logger.error(f"Search_Node: All {max_retries} retrieval attempts failed. Last error: {error_msg[:200]}")
                            raise retrieval_error  # Re-raise the exception if the last attempt also fails

                if not retrieved_docs or len(retrieved_docs) < 2:
                    logger.debug(f"Search_Node: Insufficient results from semantic retrieval for query: '{sub_q}' Do web search instead.")

                    # If document retrieval results are insufficient, attempt web search
                    if isinstance(web_search, BaseTool):
                        retrieved_docs: List[Document] = await web_search._arun(query = sub_q)

                        if not retrieved_docs or len(retrieved_docs) < 2:

                            for web_search_attempt in range(3):
                                try:
                                    retrieved_docs: List[Document] = await web_search._arun(query = sub_q)

                                    if retrieved_docs and len(retrieved_docs) >= 2:
                                        logger.debug(f"Search_Node: Web search successful on attempt {web_search_attempt + 1}")
                                        break

                                    else:
                                        logger.warning(f"Search_Node: Web search attempt {web_search_attempt + 1} returned insufficient results")

                                except Exception as e:
                                    logger.warning(f"Search_Node: Unexpected error occured during web search: {e}")
                                    updated.update({"status": "completed"})

                                    return {
                                        **updated,
                                        "error": f"Search_Node: Web search failed on attempt {web_search_attempt + 1}: {e}"
                                    }

                            if not retrieved_docs or len(retrieved_docs) < 2:
                                retrieved_docs = [Document(page_content = "No information found in the web search.", metadata = {"source": "web_search"})]

                    else:
                        logger.error(f"[Error] Search_Node: Unsupported search tool type for method 'web'. Terminate the process.")
                        updated.update({"status": "completed"})

                        return {
                            **updated,
                            "error": f"Search_Node: Unsupported retriever/tool type for method 'web'. Terminate the process."
                        }

                search_result = SearchResult(question=sub_q, documents=retrieved_docs)
                all_new_results.append(search_result)

            else:
                logger.error(f"[Error] Search_Node: Unsupported retriever type for method 'semantic'. Terminate the process.")
                updated.update({"status": "completed"})

                return {
                    **updated,
                    "error": f"Search_Node: Unsupported retriever/tool type for method 'semantic'. Terminate the process."
                }

        except Exception as e:
            logger.exception(f"[Exception] Search_Node: Failed retrieving for query '{sub_q}' using 'semantic': {e}", exc_info=True)
            updated.update({"status": "completed"})
            return {
                **updated,
                "error": f"Search_Node: Failed retrieving for query '{sub_q}' using 'semantic': {e}"
            }

    if not all_new_results:
        logger.error(f"[Warning] Search_Node: No results found for any sub-queries.")
        updated.update({"status": "completed"})

        return {
            **updated,
            "error": "Search_Node: No results found for any sub-queries."
        }

    # Merge search results and remove duplicates
    merged_context = merge_and_deduplicate_context(existing_context, all_new_results)
    logger.debug(f"Total results after merging and deduplication: {len(merged_context)}")

    final_context = merged_context

    # Get document status information (used in Loop 2 and beyond)
    used_doc_indices = state.get("used_doc_indices", [])
    not_used_doc_indices = state.get("not_used_doc_indices", [])

    # Generate context_str including status tags
    context_str = format_search_results(
        final_context,
        used_doc_indices=used_doc_indices,
        not_used_doc_indices=not_used_doc_indices,
        new_doc_start_index=prev_doc_count + 1 if prev_doc_count > 0 else 0
    )

    message_content = f"""Search results:

{context_str}
"""

    next_task_description = await generate_dynamic_message(llm, {"next_task": "generate report", "loop_count": state.get("loop_count", 0)})

    return {
        "messages": [ToolMessage(
            name="searching",
            content=message_content,
            tool_call_id=f"progress_{uuid.uuid4().hex}", # Dummy Tool Call ID
        ), AIMessage(content=next_task_description)],
        **updated,
        "context": final_context,
        "context_str": context_str,
        "prev_doc_count": prev_doc_count,
        "error": None
    }

# ------ Step 5: Generate draft answer ------
async def generate_answer_node(state: AgentState, llm: BaseChatModel,
                               MIN_NEW_TOKENS: int = 3000) -> AgentState:
    """(Step 5) Generate a draft answer based on the retrieved and reranked context."""
    # Update state
    updated = update_status_and_visit(state, "answering")
    loop_count = state.get("loop_count", 0)

    original_query = state.get("intent_analysis_result", {}).user_query
    context = state.get("context")

    if not original_query: # GOTO fallback
        logger.error(f"[Error] Generate_Answer_Node: Original query missing for answer generation.")
        updated.update({"status": "completed"})
        return {
            **updated,
            "answer": "Error: Cannot generate answer due to missing original query. Please try again.",
            "error": "Generate_Answer_Node: Original query missing for answer generation."
        }

    context_str = state.get("context_str")

    if not context: # GOTO fallback. Should probably also handle the case where the first search returns no results at all? -> go straight to web search
        logger.error("[Error] Generate_Answer_Node: No context found. Generating answer based on query only.")
        updated.update({"status": "completed"})
        return {
            **updated,
            "answer": "Error: No context found. Generating answer based on query only.",
            "error": "Generate_Answer_Node: No context found for answer generation."
        }

    intent_result = state.get("intent_analysis_result")

    if loop_count == 1:

    # --- Academic paper-style citation --- #
        system_prompt = f"""## System Instruction:
This process generates a thorough analytical report based solely on the documents provided by the user.

## Query Focus:
Main Topics to Address: {intent_result.main_topics}
Sub-topics (if available): {intent_result.sub_topics if hasattr(intent_result, 'sub_topics') else []}

## Role Definition:
You are an expert AI assistant specializing in the aging literature corpus and aging-related biomedical research. Your role is to provide clear, accurate, and helpful responses without generating formal research reports.

## Core Mandate:
Answer the user's question by synthesizing the provided context into a structured, analytical report. **Go beyond mere summarization; provide critical analysis, insightful connections, and well-supported conclusions based *exclusively* on the given documents.** Do not introduce outside knowledge or assumptions. Ensure comprehensive coverage of all main topics identified above.

## Report Requirements:
1.  **Expert-Level Analysis:** Demonstrate deep domain understanding by interpreting the context critically. Analyze relationships, causal links, underlying assumptions, and potential limitations or biases within the provided information. Ensure thorough coverage of all main topics.
2.  **Comprehensive Synthesis:** Integrate information from multiple documents meaningfully. Identify and discuss patterns, trends, convergences, or contradictions across the sources. Evaluate the relative significance of different findings.
3.  **Insightful Interpretation:** Extract key insights and implications from the data. Where applicable and supported by the context, discuss potential consequences or future considerations.
4.  **Rigorous Structure & Clarity:** Organize the report logically with clear headings and subheadings. Explain complex concepts precisely and systematically. Ensure the report flows coherently. The report should be at least {MIN_NEW_TOKENS} words long, or longer if the complexity demands.
5.  **Evidence-Based Credibility:** Every factual claim, significant assertion, or piece of data presented **must be meticulously cited** using numeric references in square brackets (e.g., [1], [2, 3]), corresponding to the document number (N) in the context header (`---Document N...`).

## Chain-of-Thought Process (Internal):
Before writing the report, mentally perform these steps:
1.  Deconstruct the user's query into core components, focusing on the main topics identified above.
2.  Identify all relevant documents and passages for each main topic and sub-topic.
3.  Critically extract and evaluate key information, noting source document numbers.
4.  Analyze connections, patterns, and discrepancies *between* documents.
5.  Synthesize findings into logical arguments and insights.
6.  Structure the report outline, ensuring complete coverage of all main topics.
7.  Identify information gaps **within the context** and how to address them (e.g., explicitly state limitations).

## Setting quality metrics before creation:
Before writing the report, plan how your analysis should be organized based on these quality metrics:
1. All important claims must be supported by document evidence
2. Consistency between information from different documents must be checked
3. Logical flow and validity of causal relationships must be correct
4. Citation must be accurate and complete
5. All main topics must be thoroughly addressed

## Report Structure:
Organize your report into these sections:

1.  **Introduction / Executive Summary**: (Approx. 200-300 words, 5-10% of total length) Briefly state the report's purpose (addressing the user's query). Provide a high-level overview of the key findings and conclusions derived from the context. Include a brief mention of all main topics that will be covered.
2.  **Detailed Analysis**: (70-75% of total length) This is the main body of the report. Present a comprehensive and in-depth analysis addressing the user's question.
    -   Break down the topic into logical sections with clear, descriptive headings (each section 600-1000 words), ensuring coverage of all main topics. **Main topics should be the largest and most in-depth in the report**
    -   For each section, synthesize information from relevant documents, providing detailed explanations, evidence, and critical analysis.
    -   **Cite sources ([N]) meticulously for every assertion.**
    -   Include thinking processes in your analysis:
        1. State key claims explicitly
        2. List evidence supporting these claims
        3. Consider alternative interpretations
        4. Evaluate strengths and limitations of the evidence
        5. Draw final conclusions
    -   Clearly explain technical terms or concepts using the context.
    -   Compare and contrast information from different documents where relevant.
    -   Discuss any ambiguities or limitations found within the provided context.
3.  **Conclusion**: (Approx. 200-300 words, 10-15% of total length) Summarize the main analytical points and key insights derived from the context. Reiterate the answer to the core query based on the analysis. Mention any significant limitations imposed by the context. Address each main topic in your summary.
4.  **Suggestions / Future Considerations**: (Approx. 100-200 words, 5-10% of total length) Based *only* on the analysis of the provided context, suggest 1-2 specific, relevant follow-up questions, potential areas for further investigation (if context hints at them), or related tasks. Phrase these helpfully.
5.  **References**:
    - List all unique source documents cited in the analysis.
    - **CRITICAL RULE: You MUST place each reference on its own, separate line.**
    - Never combine multiple references onto a single line.
    - Follow the exact format `[N] <document_source>` for each entry.

    Example of the required format:
    [1] pmc_result
    [2] PMC3791984
    [3] PMC3843606
    [4] ...

6. **Appendices**: If the analysis requires additional information or context, include it in the appendices. This section is optional.

## Citation Examples:
- "Cognitive reserve patterns vary across different age groups" [1, 3]
- "Research results showed that frailty measures had a negative correlation with quality of life outcomes" [2]
- "Yaakov Stern first proposed the concept of cognitive reserve in 1988, describing it as a protective factor against cognitive decline" [5]

## Writing Style and Guidelines:
- Maintain a professional, objective, and analytical tone throughout the report.
- Ensure clarity, accuracy, and precision in language.
- Develop arguments logically and step-by-step.
- Focus exclusively on information verifiable within the provided context.
- If the context is insufficient to fully answer a part of the query, explicitly state this limitation rather than speculating.
- Include original English terms in parentheses if they are crucial technical terms found in the source documents and aid clarity.
- Ensure comprehensive coverage of all main topics identified in the query focus.
- After appendices section, anything else is not allowed. Even if the sentence like "Completed report" is not allowed.
- So, if you need to add any other information, please add it in the appendices section.

--- Provided Context ---
{{context_str}}
"""

        user_prompt = f"""Question: {{query}}

Based *only* on the provided context documents, generate a comprehensive and in-depth analysis report addressing this question. Ensure meticulous citation and adhere strictly to the required structure and professional standards outlined in the system prompt. The report must be at least {MIN_NEW_TOKENS} words long.
"""

    else:
        system_prompt = f"""## System Instruction:
This process refines a previously generated analytical report by substantially deepening the analysis with newly discovered information from additional searching.

## Query Focus:
Main Topics to Address: {intent_result.main_topics}
Sub-topics (if available): {intent_result.sub_topics if hasattr(intent_result, 'sub_topics') else []}

## Role Definition:
You are a **world-class expert and senior analyst** with over 20 years of academic and research experience. You excel at integrating new information into existing analyses and significantly deepening the intellectual rigor of reports. Your primary goal is to reinforce the existing report into a substantially more profound and comprehensive analysis by leveraging the newly provided context.

## Core Mandate:
Substantially deepen the intellectual depth and analytical rigor of the existing answer using the new information found in the context. **Your primary mission is to make the analysis significantly more profound, nuanced, and insightful - not just longer or more detailed.** Critically evaluate how the new information allows for deeper exploration of underlying principles, theoretical frameworks, or conceptual relationships, especially regarding the main topics identified above.

## Report Enhancement Requirements:
1. **Intellectual Depth Enhancement:** Dramatically increase the depth of analysis by exploring root causes, theoretical foundations, and systemic relationships that weren't possible with the previous information. Ensure comprehensive coverage of all main topics.
2. **Conceptual Sophistication:** Introduce more sophisticated conceptual frameworks or analytical models that better explain the phenomena discussed, supported by the new context.
3. **Analytical Precision:** Replace general statements with specific, nuanced analysis that shows deeper understanding of the subject matter.
4. **Complex Relationship Analysis:** Identify and analyze more complex relationships, dependencies, and causal mechanisms between key elements and between main topics.
5. **Critical Perspective Expansion:** Integrate alternative perspectives, counterarguments, or theoretical tensions that add intellectual depth.
6. **Enhanced Evidence Integration:** Seamlessly incorporate new evidence to support deeper claims, maintaining proper citations with the numeric reference system [N].
7. **Structural Refinement:** As the content deepens, intelligently reorganize sections into logical sub-sections that enhance clarity and intellectual progression.
8. **Citation Accuracy:** Ensure that all citations are accurate and complete, and that the numeric reference system [N] is used correctly.

## Chain-of-Thought Process (Internal):
Before revising for depth, mentally perform these steps:
1. Review the main topics and sub-topics that need to be addressed
2. Identify what deeper analytical frameworks the new information enables for each main topic
3. Determine which parts of the existing analysis can be pushed to greater depth
4. Plan how to transform surface-level descriptions into profound analysis
5. Consider how new information reveals more complex relationships or systems
6. Map out how to build more sophisticated intellectual scaffolding around key points
7. Identify where logical sub-section divisions would enhance understanding of complex topics
8. Check if the report content is consistent with the document content and if there are any incorrect contents, recognize that it needs to be fixed

## Setting quality metrics before creation:
Before writing the report, Evaluate previous reports based on the following metrics:
1. How deeply each main topic has been analyzed
2. Which claims have not been sufficiently supported by document evidence
3. Which sections have been superficial descriptions without theoretical frameworks
4. Which parts of the main topics have insufficient relationship analysis
5. Which parts of the report are currently descriptive but need to be transformed into analytical

## Report Structure:
Maintain the existing report structure while dramatically increasing its intellectual depth:

1. **Introduction / Executive Summary**: Transform to reflect the deeper analytical approach. Ensure all main topics and sub topics are properly introduced.
2. **Detailed Analysis**: Replace surface-level analysis with profound exploration throughout:
   - Convert descriptive passages into deeply analytical ones.
   - Replace general statements with specific, theoretically-grounded insights.
   - **Build more sophisticated intellectual frameworks around key concepts and main topics.** (Main topics should be the largest and most in-depth in the report)
   - Analyze complex inter-relationships between elements and between main topics.
   - **Create logical sub-sections** as content deepens to improve structural clarity.
   - Each major section should have 2-4 well-defined sub-sections when appropriate to organize deeper content.
   - Use hierarchical headings (e.g., ### for subsections, #### for nested subsections) to create a clear information architecture
   - Maintain meticulous citations ([N]) for all assertions.
3. **Conclusion**: Elevate to reflect the more profound understanding achieved for all main topics and sub topics.
4. **Suggestions / Future Considerations**: Revise to suggest deeper investigative directions.
5.  **References**:
    - Update the list of source documents cited in the analysis.
    - Map the document number (N) to the source information exactly as provided in the context header.

    **Formatting Rules:**
    - **CRITICAL:** Each reference MUST be placed on its own, separate line. Do not combine multiple references.
    - The format for each line must be: `[N] <document_source>`

    **Example:**
    [1] pmc_result
    [2] PMC3791984
    [3] PMC3843606
    [4] ...
6. **Appendices**: If the analysis requires additional information or context, include it in the appendices. This section is optional.

## Writing Style and Guidelines:
- Maintain scholarly rigor while ensuring accessibility
- Include original English terms in parentheses for crucial technical terms
- Focus exclusively on deepening analysis using information from the provided context
- The depth-enhanced report should demonstrate a quantum leap in intellectual sophistication compared to the original
- Use structural elements (sections, sub-sections, paragraphs) strategically to enhance intellectual flow and comprehension
- Ensure all main topics receive adequate attention and depth of analysis
- The report should be at least {MIN_NEW_TOKENS} words long.
- The report should cite all the provided context documents.
- After appendices section, anything else is not allowed. Even if the sentence like "Completed report" is not allowed.
- So, if you need to add any other information, please add it in the appendices section.

--- Provided Context ---
{{context_str}}
"""

        user_prompt = f"""Question: {{query}}

Below is the previously generated report:

{{previous_answer}}

Using **all** the newly provided context documents, transform this report by substantially deepening its intellectual rigor and analytical depth. Your primary goal is to **make the analysis profoundly more insightful and sophisticated** - not just to add more information.

As you deepen the content:
1. Create logical sub-sections within major sections to organize complex ideas
2. Use appropriate heading levels (##, ###, ####) to establish clear hierarchy
3. Replace surface-level observations with deep analysis
4. Substitute general claims with specific theoretical insights
5. Transform simple descriptions into complex relationship analysis

Remember: The final report should represent a quantum leap in depth and intellectual sophistication while maintaining logical flow and cohesive structure. The expanded content should be organized into clear sub-sections that guide the reader through increasingly sophisticated levels of analysis.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])

    chain = prompt | llm | StrOutputParser()

    try:
        # Use config=RunnableConfig(callbacks=[]) to prevent streaming callback
        # propagation for this specific LLM call.
        if loop_count == 1:
            draft_answer = await chain.ainvoke(
                {"query": original_query, "context_str": context_str},
                config=RunnableConfig(callbacks=[])  # <--- Use RunnableConfig
                )

        else:
            previous_answer = state.get("answer")
            # answer may be passed as a list, so convert it to a string
            if isinstance(previous_answer, list):
                previous_answer = "\n".join(str(item) for item in previous_answer) if previous_answer else ""
            # previous_answer may contain braces, so escape them
            escaped_previous_answer = previous_answer.replace('{', '{{').replace('}', '}}') if previous_answer else ""
            draft_answer = await chain.ainvoke(
                {"query": original_query, "context_str": context_str, "previous_answer": escaped_previous_answer},
                config=RunnableConfig(callbacks=[])  # <--- Use RunnableConfig
            )

        used_document_indices = set()
        citations = re.findall(r'\[(\d+(?:,\s*\d+)*)\]', draft_answer)

        for citation in citations:
            indices = [int(idx.strip()) for idx in citation.split(',')]
            used_document_indices.update(indices) # Remove duplicates

        document_usage = {}
        doc_index = 1

        if context:
            for search_result in context:
                if search_result.documents:
                    for doc in search_result.documents:
                        document_usage[doc_index] = {
                            "document": doc,
                            "used": doc_index in used_document_indices,
                            "source": doc.metadata.get("source", f"doc_{doc_index}")
                        }
                        doc_index += 1

        next_task_description = await generate_dynamic_message(llm, {"next_task": "evaluate answer", "loop_count": state.get("loop_count", 0)})

        return {
            "messages": [ToolMessage(
                name="generate draft answer",
                content=f"Generateddraft answer:\n{draft_answer}",
                tool_call_id=f"progress_{uuid.uuid4().hex}", # Dummy Tool Call ID
            ), AIMessage(content=next_task_description)],
            **updated,
            "answer": draft_answer.strip(), # Store the full LLM output here
            "context_str": context_str,
            "document_usage": document_usage,
            "error": None
        }

    except Exception as e:
        logger.exception(f"[Error] Answer generation failed.")
        updated.update({"status": "completed"})
        return {
            **updated,
            "answer": f"Error: Answer generation failed. {e}",
            "error": f"Answer generation failed: {e}"
        }

# ------ Step 6: Evaluate answer ------
async def evaluate_answer_node(state: AgentState, llm: BaseChatModel) -> AgentState:
    """(Step 6) Evaluate the generated draft answer (relevance, completeness, missing information). Only track the used document indices (filtering removed)."""
    updated = update_status_and_visit(state, "evaluating")

    draft_answer = state.get("answer")
    intent_result = state.get("intent_analysis_result")
    original_query = intent_result.user_query if intent_result else None

    # Get the original context and context_str
    original_context: Optional[List[SearchResult]] = state.get("context")
    original_context_str = state.get("context_str", "")
    document_usage: Optional[Dict[int, Dict[str, Any]]] = state.get("document_usage")
    loop_count = state.get("loop_count", 0)

    # --- Extract used document indices (instead of filtering) ---
    # The context is kept as-is without filtering to ensure numbering consistency
    used_doc_indices: List[int] = []
    not_used_doc_indices: List[int] = []

    if document_usage:
        for doc_index, usage_info in document_usage.items():
            if usage_info.get("used", False):
                used_doc_indices.append(doc_index)
            else:
                not_used_doc_indices.append(doc_index)

        logger.info(f"Evaluate_Answer_Node: Used documents: {sorted(used_doc_indices)}, Not used: {sorted(not_used_doc_indices)}")

        # Save the used document indices to the state (used in the next loop)
        updated.update({
            "used_doc_indices": sorted(used_doc_indices),
            "not_used_doc_indices": sorted(not_used_doc_indices)
        })
    else:
        logger.warning("Evaluate_Answer_Node: document_usage info missing.")

    # The context is not filtered - keep the original to maintain numbering consistency
    # --- End of used document index extraction ---


    if loop_count < 1:
        logger.error(f"[Error] Evaluate_Answer_Node: Evaluation skipped due to loop count is less than 1.")
        updated.update({"status": "completed"})
        return {
            **updated,
            "eval_result": EvaluationResult(relevance=0.0, completeness=0.0, missing_info=["Evaluation skipped due to loop count"], need_web_search=False),
            "error": "Evaluate_Answer_Node: Evaluation skipped due to loop count is less than 1." # GOTO fallback
        }

    if not original_query:
        logger.error(f"[Error] Evaluate_Answer_Node: Original query missing for answer evaluation.")
        updated.update({"status": "completed"})
        return {
            **updated,
            "eval_result": EvaluationResult(relevance=0.0, completeness=0.0, missing_info=["Evaluation skipped due to missing original query"], need_web_search=False),
            "error": "Evaluate_Answer_Node: Original query missing for answer evaluation. Cannot evaluate answer due to missing original query." # GOTO fallback
        }

    if not draft_answer or draft_answer.startswith("Error:"):
        error_msg = state.get("error", "Evaluate_Answer_Node: Draft answer missing or invalid for evaluation.")
        logger.warning(f"Evaluate_Answer_Node: Skipping evaluation due to prior error: {error_msg}")
        updated.update({"status": "completed"})
        return {
            **updated,
            "eval_result": EvaluationResult(relevance=0.0, completeness=0.0, missing_info=["Evaluation skipped due to prior error"], need_web_search=False),
            "error": error_msg # GOTO fallback
        }

    # Prepare for evaluation
    parser = JsonOutputParser(pydantic_object=EvaluationResult)
    format_instructions = parser.get_format_instructions().replace('{', '{{').replace('}', '}}')

    # --- Updated System Prompt for Evaluation --- #
    enable_loop = MAX_SEARCH_ATTEMPTS - loop_count

    system_prompt = f"""
You are an extremely critical academic evaluator tasked with analyzing the quality of generated answers. Your evaluation standards should be exceptionally high - comparable to those used for evaluating doctoral dissertations at elite universities. You should also evaluate whether the answers clearly cover the main topics and subtopics.

## Core Evaluation Focus
User Query: {original_query}
Main Topics to Evaluate: {intent_result.main_topics}
Sub-topics (if available): {intent_result.sub_topics if hasattr(intent_result, 'sub_topics') else []}

## Primary Evaluation Criteria (Main Topics Coverage):
### Relevance (0.0-1.0):
Measures how directly and comprehensively the answer addresses each main topic.

Strict Scoring Guide for Main Topics:
- 0.0-0.3: Answer largely misses most main topics or addresses them superficially
- 0.4-0.6: Answer addresses some main topics but has significant gaps in coverage
- 0.7-0.8: Answer addresses most main topics well with minor gaps
- 0.9-1.0: Answer comprehensively addresses ALL main topics with precision (RESERVE FOR TRULY EXCEPTIONAL COVERAGE)

Main Topics Evaluation Checklist:
1. Coverage Depth
   - Does the answer thoroughly explore each main topic?
   - Is the treatment of each main topic balanced and appropriate?
   - Are key aspects of each main topic addressed?

2. Integration Quality
   - How well are different main topics connected when relevant?
   - Is there logical flow between related main topics?
   - Are relationships between main topics properly explained?

3. Accuracy and Precision
   - Is the information about each main topic accurate?
   - Are technical terms related to main topics used correctly?
   - Are claims about main topics well-supported?

### Completeness (0.0-1.0):
Measures intellectual depth and analytical sophistication in addressing main topics and their relationships.

Strict Scoring Guide for Analysis Depth:
- 0.0-0.2: Superficial treatment of main topics, lacking depth
- 0.3-0.5: Basic analysis of main topics with limited theoretical grounding
- 0.6-0.7: Good analysis of main topics with some theoretical foundations
- 0.8-0.9: Excellent analysis with strong theoretical grounding of main topics
- 0.9-1.0: Exceptional analysis with profound insights into all main topics (RESERVE FOR WORLD-CLASS ANALYSIS ONLY)

## Secondary Evaluation Criteria (Sub-topics and Context):
1. Sub-topics Coverage
   - Are relevant sub-topics adequately explored?
   - Do sub-topics support understanding of main topics?
   - Is the treatment of sub-topics proportional to their importance?

2. Contextual Integration
   - How well is context provided for each main topic?
   - Are relationships between topics and sub-topics clear?
   - Is background information appropriately integrated?

### IMPORTANT: BE EXTREMELY CONSERVATIVE WITH HIGH SCORES
- A score of 0.8+ in completeness should represent analysis that would be lauded in top academic journals
- A score of 0.9+ should be reserved for analysis that demonstrates exceptional expertise and insight
- Most answers, even good ones, should score in the 0.5-0.8 range for completeness

## Identify missing information for deeper analysis:
- Your primary goal is to identify information that would significantly deepen the intellectual rigor and analytical depth of the current answer.
- Be exhaustive and critical in identifying gaps in the current analysis.
- Focus on identifying:
  1. Identify any main topics that need deeper exploration
  2. Note aspects of main topics that are underdeveloped
  3. Highlight missing connections between main topics
  4. Point out where theoretical frameworks for main topics and user query are needed
  5. Missing theoretical frameworks and models
  6. Absence of critical perspectives or counterarguments
  7. Lack of comparative analysis between competing viewpoints
  8. Insufficient exploration of causal relationships and systemic factors
  9. Inadequate contextual grounding or historical perspective
  10. Gaps in methodological justification or limitations
  11. Underdeveloped implications or applications
- Each item must be specific and clearly stated to facilitate effective searching.
- Always assume that more depth is possible - be extremely hesitant to conclude that an answer is "complete enough."
- There are/is **{enable_loop} number of retrievable loops** left.

Secondary considerations for missing information:
- Important sub-topics that would enhance main topics understanding
- Contextual elements needed for better comprehension
- Supporting evidence or examples for main topics
- Methodological aspects related to main topics

## CRITICAL: Determining if more search is needed
- Set the missing_info to an empty list [] ONLY when ALL of these conditions are met:
  1. The answer demonstrates exceptional depth with multiple integrated theoretical frameworks
  2. **ALL main topics are covered with exceptional depth and clarity** (Main topics should be the largest and most in-depth in the report)
  3. Relationships between main topics are thoroughly explored
  4. The completeness score is genuinely above 0.85 by the strict criteria defined above
  5. The answer **thoroughly addresses counterarguments and competing perspectives**
  6. The analysis includes sophisticated treatment of contextual factors and implications
  7. Additional searches are highly unlikely to yield significant conceptual improvements
- missing_info must be written in **english**.
- Remember: It is far better to continue searching than to prematurely conclude an answer is complete.
- If there is ANY significant area where deeper analysis could be added, continue with searches.
- If user query is specific about a certain topic, you should not include too broad topics.
    - (e.g. user query: "Tell me about the related biomarkers", main topic: "biomarkers for cognitive function of the brain" -> Includes only biomarkers of cognitive function in the brain, not biomarkers of cancer or lung disease, etc.)
    - In this case, you can suggest to user to ask about the other biomarkers in the Suggestions section.
- System Alert: There are/is **{enable_loop} number of retrievable loops** left.

## Response Format:
The response should follow this JSON format:
{format_instructions}
"""

    evaluate_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "## User Query: {query}\n\n## Context (Used Documents Only):\n{context_str}\n\n## Generated Answer:\n{answer}")
    ])

    chain = evaluate_prompt | llm | StrOutputParser() | parser

    try:
        evaluation_result_dict: Dict = await chain.ainvoke(
            {
                "query": original_query,
                "context_str": original_context_str,
                "answer": draft_answer
            },
            config=RunnableConfig(callbacks=[])
        )

        eval_result = EvaluationResult(**evaluation_result_dict)

        # Additional: stop further searches if the completeness score is very high
        if eval_result.completeness >= 0.90:
            eval_result.missing_info = []
            logger.info(f"Evaluate_Answer_Node: Achieved excellent completeness score ({eval_result.completeness:.2f}). Stopping further searches.")

        # Additional: measure improvement by comparing with the previous completeness
        previous_completeness = state.get("previous_completeness", 0.0)
        improvement = eval_result.completeness - previous_completeness

        if improvement < 0.05 and eval_result.completeness > 0.75 and loop_count > 2:
            eval_result.missing_info = []
            logger.info(f"Evaluate_Answer_Node: Minimal improvement in completeness ({improvement:.2f}). Stopping further searches.")

        if loop_count >= MAX_SEARCH_ATTEMPTS:
            eval_result.missing_info = []
            logger.debug(f"Evaluate_Answer_Node: Reached maximum search attempts. Stopping further searches.")

        # Save the current completeness
        updated.update({"previous_completeness": eval_result.completeness})

        logger.info(f"Evaluate_Answer_Node: Evaluation complete - Relevance: {eval_result.relevance}, Completeness: {eval_result.completeness}")
        logger.debug(f"Evaluate_Answer_Node: Missing info: {eval_result.missing_info}")

        if eval_result.missing_info and loop_count == 1:
            next_task_description = await generate_dynamic_message(llm, {"next_task": "human_approval", "loop_count": state.get("loop_count", 0)})
        elif eval_result.missing_info and loop_count > 1:
            next_task_description = await generate_dynamic_message(llm, {"next_task": "retrieve and rerank", "loop_count": state.get("loop_count", 0)})
        else:
            next_task_description = await generate_dynamic_message(llm, {"next_task": "print final answer", "loop_count": state.get("loop_count", 0)})

        return {
            "messages": [AIMessage(content=next_task_description)],
            **updated,
            "eval_result": eval_result,
            "error": None
        }

    except (Exception, ValidationError) as e:
        logger.exception(f"[Error] Evaluate_Answer_Node: Evaluation failed or parsing error.")
        return {
            **updated,
            "eval_result": EvaluationResult(relevance=0.0, completeness=0.0, missing_info=["Evaluation process failed"], need_web_search=False),
            "error": f"Evaluation failed or parsing error: {e}" # GOTO fallback
        }

# ------ human approval node -------
async def human_approval(state: AgentState, config: RunnableConfig) -> Command[Literal["retriever", "print_final_answer"]]:
    """Get human feedback on the report and route to next steps.

    This node:
    1. Formats the current report for human review
    2. Gets feedback via an interrupt
    3. Routes to either:
       - Section writing if report is approved
       - Report regeneration if feedback is provided

    Args:
        state: Current graph state with sections to review
        config: Configuration for the workflow

    Returns:
        Command to either regenerate plan or start section writing
    """

    # Get sections
    draft_answer = state["answer"]

    # Get feedback on the report plan from interrupt
    interrupt_message = f"""Please provide feedback on the following report.
                        \n\n{draft_answer}"""

    action_request = ActionRequest(
        action="Draft Report",
        args={"report_plan": interrupt_message},
    )

    interrupt_config = HumanInterruptConfig(
        allow_ignore=True,  # Allow the user to `ignore` the interrupt.
        allow_respond=False,  # Allow the user to `respond` to the interrupt.
        allow_edit=False,  # Allow the user to `edit` the interrupt's args.
        allow_accept=True,  # Allow the user to `accept` the interrupt's args.
    )

    description = (
        "# Draft Report"
        + "Please carefully review the draft report and provide feedback on whether it meets your needs. "
        + "If you accept, it will kick off section writing. "
        + "If you edit and submit, the edited report will be used to generate the sections."
        + "If you ignore, the report will not be generated."
        + "If you respond, the response will be used to generate new report"
    )

    request = HumanInterrupt(
        action_request=action_request, config=interrupt_config, description=description
    )

    human_response: HumanResponse = interrupt([request])[0]

    # print(human_response.get("args")) # {'type': 'accept', 'args': {'action': 'Confirm report plan', 'args': {'report_plan': 'Please provide...'}}}

    if human_response.get("type") == "ignore":
        # If the user provides feedback, regenerate the report plan

        next_task_description = "I will search for additional information."

        return Command(
            goto="retriever",
            update={"feedback_on_report_plan": human_response.get("args"),
                    "messages": [AIMessage(content=next_task_description)],
                },
        )
    elif human_response.get("type") == "accept":
        # If the user approves the report plan, kick off section writing
        next_task_description = "I will use this document as the final answer."

        return Command(goto = "print_final_answer",
                        update={"messages": [AIMessage(content=next_task_description)],
                                "status": "completed",
                                "error": None,
                                }
                        )

    else:
        raise TypeError(
            f"Interrupt value of type {type(human_response)} is not supported."
        )

def _clean_source_name(source: str) -> str:
    """Clean up the document source path and return a tidy name."""
    if not source or not isinstance(source, str):
        return "Unknown Source"

    # 1. Extract only the file name
    name = os.path.basename(source)

    # 2. Remove chunk information (if present)
    name = name.split('(Chunk:')[0].strip()

    # 3. Remove the last extension
    if '.' in name:
        name = name.rsplit('.', 1)[0]

    # 4. Remove the 'number.' pattern at the beginning of the file name (key fix)
    name = re.sub(r'^\d+\.\s*', '', name)

    return name

# ------ Step 7: Output before termination -------
def _format_reference_entry(doc_num: int, doc_info: Dict[str, Any]) -> str:
    """Format a reference entry based on the document metadata."""
    doc = doc_info.get("document")
    if not doc:
        source = doc_info.get("source", f"Document {doc_num}")
        return f"{doc_num}. {_clean_source_name(source)}"

    metadata = doc.metadata
    parts = []

    # Use the title first if available
    title = metadata.get("title")
    if title:
        # Truncate the title if it is too long
        if len(title) > 100:
            title = title[:97] + "..."
        parts.append(title)

    # Author information
    authors = metadata.get("authors") or metadata.get("first_author")
    if authors:
        # If the authors string is too long, keep only the first author
        if len(authors) > 50:
            first_author = authors.split(";")[0].strip()
            authors = f"{first_author} et al."
        parts.append(f"({authors})")

    # Journal information
    journal = metadata.get("journal")
    year = metadata.get("publication_year")
    if journal:
        journal_info = journal
        if year:
            journal_info += f", {year}"
        parts.append(journal_info)
    elif year:
        parts.append(year)

    # DOI or PMID/PMC ID
    doi = metadata.get("doi")
    pmid = metadata.get("pmid")
    pmc_id = metadata.get("pmc_id")

    if doi:
        parts.append(f"DOI: {doi}")
    elif pmid:
        parts.append(f"PMID: {pmid}")
    elif pmc_id:
        parts.append(f"PMC: {pmc_id}")

    # If metadata is insufficient, use the source file name
    if not parts:
        source = metadata.get("source", doc_info.get("source", f"Document {doc_num}"))
        parts.append(_clean_source_name(source))

    return f"{doc_num}. " + " - ".join(parts)


async def print_final_answer(state: AgentState, llm: BaseChatModel = None) -> AgentState:
    updated = update_status_and_visit(state, "answering")
    raw_answer = state.get("answer", "")
    document_usage: Optional[Dict[int, Dict[str, Any]]] = state.get("document_usage")

    if not raw_answer:
        logger.error("Print_Final_Answer: Final answer is missing.")
        return {"messages": [AIMessage(content="Error: Final answer missing.")], "answer": "Error: Final answer missing.", **updated, "error": "Final answer missing"}

    final_answer_content = raw_answer

    try:
        # 1. Find the 'References' header to split into the body and the reference candidate area
        ref_header_pattern = r"^\s*(?:#|\*|\d\.).*?References"
        ref_match = re.search(ref_header_pattern, raw_answer, re.MULTILINE | re.IGNORECASE)

        if not ref_match:
            logger.warning("No valid reference header found. Returning raw answer.")
            final_answer_content = raw_answer.strip()
        else:
            # Everything before the header is treated as the body
            answer_body = raw_answer[:ref_match.start()].strip()

            logger.debug(f"Successfully split content. Body length: {len(answer_body)}")

            # 2. Extract the citation numbers used in the body
            used_citations = set()
            citation_matches = re.findall(r'\[([\d\s,]+)\]', answer_body)
            for match in citation_matches:
                for num_str in match.split(','):
                    try:
                        used_citations.add(int(num_str.strip()))
                    except ValueError:
                        pass

            logger.debug(f"Found {len(used_citations)} unique citations in answer body: {sorted(used_citations)}")

            # 3. Generate references based on document_usage (key change)
            if document_usage and used_citations:
                logger.debug(f"Using document_usage for references. Available docs: {list(document_usage.keys())}")

                # Filter only the used documents and remove duplicates by source
                used_docs = {}
                source_to_old_nums = {}  # source -> [old_num1, old_num2, ...]

                for old_num in sorted(used_citations):
                    if old_num in document_usage:
                        doc_info = document_usage[old_num]
                        doc = doc_info.get("document")
                        if doc:
                            source = doc.metadata.get("source", f"doc_{old_num}")
                        else:
                            source = doc_info.get("source", f"doc_{old_num}")

                        # Remove duplicates by source
                        if source not in source_to_old_nums:
                            source_to_old_nums[source] = []
                            used_docs[source] = doc_info
                        source_to_old_nums[source].append(old_num)

                # Generate the new number mapping (sorted by source)
                unique_sources = sorted(source_to_old_nums.keys())
                old_to_new_num_map = {}
                for new_num, source in enumerate(unique_sources, 1):
                    for old_num in source_to_old_nums[source]:
                        old_to_new_num_map[old_num] = new_num

                logger.debug(f"Citation mapping: {old_to_new_num_map}")

                # 4. Replace the citation numbers in the body
                def replace_citation(match):
                    old_nums_str = match.group(1).split(',')
                    new_nums = []
                    for n_str in old_nums_str:
                        try:
                            old_num = int(n_str.strip())
                            if old_num in old_to_new_num_map:
                                new_nums.append(str(old_to_new_num_map[old_num]))
                        except ValueError:
                            pass
                    if new_nums:
                        sorted_unique_nums = sorted(list(set(new_nums)), key=int)
                        return f"[{', '.join(sorted_unique_nums)}]"
                    return match.group(0)

                updated_answer_body = re.sub(r'\[([\d\s,]+)\]', replace_citation, answer_body)

                # 5. Generate references using the metadata from document_usage
                final_references_lines = []
                for new_num, source in enumerate(unique_sources, 1):
                    doc_info = used_docs[source]
                    ref_entry = _format_reference_entry(new_num, doc_info)
                    final_references_lines.append(ref_entry)

                final_references_section = "\n".join(final_references_lines)
                final_answer_content = f"{updated_answer_body}\n\n### References\n{final_references_section}"
                logger.info(f"Generated references from document_usage: {len(final_references_lines)} entries")

            else:
                # Fallback: if document_usage is not available, use the existing LLM output parsing method
                logger.warning("document_usage not available, falling back to LLM output parsing")
                references_candidate_str = raw_answer[ref_match.start():].strip()
                individual_refs = re.findall(r'\[\d+\](?:(?!\[\d+\])[\s\S])*', references_candidate_str)

                if not individual_refs:
                    logger.warning("Reference header found, but no actual reference items. Returning raw answer.")
                    final_answer_content = raw_answer.strip()
                else:
                    old_ref_map = {}
                    for ref_text in individual_refs:
                        match = re.match(r'\[(\d+)\]\s*(.*)', ref_text.strip())
                        if match:
                            old_num, source_path = int(match.group(1)), match.group(2).strip()
                            if source_path.startswith("/data/users/gunho/project/forest/docs/"):
                                source_path = source_path.replace("/data/users/gunho/project/forest/docs/", "")
                            old_ref_map[old_num] = source_path

                    unique_sources = sorted(list(set(old_ref_map.values())))
                    new_ref_map = {name: i + 1 for i, name in enumerate(unique_sources)}

                    old_to_new_num_map = {
                        old_num: new_ref_map.get(source_path)
                        for old_num, source_path in old_ref_map.items()
                        if new_ref_map.get(source_path) is not None
                    }

                    def replace_citation_fallback(match):
                        old_nums_str = match.group(1).split(',')
                        new_nums = []
                        for n_str in old_nums_str:
                            try:
                                old_num = int(n_str.strip())
                                if old_num in old_to_new_num_map:
                                    new_nums.append(str(old_to_new_num_map[old_num]))
                            except ValueError:
                                pass
                        if new_nums:
                            sorted_unique_nums = sorted(list(set(new_nums)), key=int)
                            return f"[{', '.join(sorted_unique_nums)}]"
                        return match.group(0)

                    updated_answer_body = re.sub(r'\[([\d\s,]+)\]', replace_citation_fallback, answer_body)
                    final_references_lines = [f"{i+1}. {name}" for i, name in enumerate(unique_sources)]
                    final_references_section = "\n".join(final_references_lines)
                    final_answer_content = f"{updated_answer_body}\n\n### References\n{final_references_section}"

    except Exception as e:
        logger.exception(f"FATAL: Error during final answer processing: {e}")
        final_answer_content = raw_answer.strip()

    ai_message = AIMessage(content=final_answer_content.strip())
    logger.info("Delivering final answer to user.")

    updated.update({"status": "completed", "node_visits": 0, "loop_count": 0})

    return {
        "messages": [ai_message],
        "answer": final_answer_content.strip(),
        **updated,
        "error": None
    }

# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# !                                                                             Error Management
# !----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

async def generate_dynamic_error_message(llm: BaseChatModel, context: dict) -> str:
    """Use the LLM to generate a dynamic error message appropriate to the situation."""
    system_prompt = """You're a professional and helpful AI assistant.
We encountered a technical issue while generating an answer to your question.

## Role:
- You need to explain the error in a way that is easy for the user to understand.
- Write your response in a friendly and empathetic tone.
- Avoid technical details and speak at a level the user can understand.
- Offer possible solutions or alternatives.

## Response guidelines:
1. start with a polite apology.
2. briefly explain what the problem is.
3. If you have a partially generated answer, let them know that it may not be complete.
4. Suggest next steps the user can take.
5. At the end, mention the error type and details.
"""

    partial_answer = context['partial_answer']
    partial_answer_preview = partial_answer[:100] + '...' if len(partial_answer) > 100 else partial_answer

    # error_details may contain braces, so simplify it
    error_details = context['error_details']
    if len(error_details) > 200:
        error_details = error_details[:200] + '...'
    # Escape braces
    error_details = error_details.replace('{', '{{').replace('}', '}}')

    user_prompt = f"""Please generate an appropriate error message for the following situations:

Original question: {context['original_query']}
Error type: {context['error_type']}
Error details: {context['error_details']}
Search attempts: {context['search_attempts']}
Partial answer: {context['partial_answer'][:100] + '...' if len(context['partial_answer']) > 100 else context['partial_answer']}

Based on the above information, please write a friendly and empathetic message to the user explaining the technical issue and providing possible solutions or alternatives."""

    # Pass messages directly rather than using a LangChain template
    messages = [
        ("system", system_prompt),
        ("human", user_prompt)
    ]

    chain = ChatPromptTemplate.from_messages(messages) | llm | StrOutputParser()
    response = await chain.ainvoke({}, config=RunnableConfig(callbacks=[]))

    return response.strip()

# ------ Step fallback: Handle fallback when an error occurs or the maximum number of attempts is reached ------
async def fallback_node(state: AgentState, llm: BaseChatModel = None, reason: str = "Unknown error") -> AgentState:
    """(Step 7) Handle fallback when an error occurs or the maximum number of attempts is reached."""
    updated = update_status_and_visit(state, "fallback")
    logger.warning(f"--- Entering Fallback Node --- Reason: {reason}")

    error_message = state.get("error", "No specific error message.")
    fallback_reason = f"Process ended unexpectedly. Reason: {reason}. Last error: {error_message}"
    logger.error(fallback_reason) # Log the error situation

    # If no LLM is provided, use the default response
    if not llm:
        fallback_comment = "Sorry. Answer generation has stopped due to an unexpected error. The most recently generated initial draft will be displayed, and it may be an answer that does not meet the standards.\nPlease ask again in a new chat.\n\n"
        # state.get("answer") may be a list, so convert it to a string
        previous_answer = state.get("answer", "")
        if isinstance(previous_answer, list):
            previous_answer = "\n".join(str(a) for a in previous_answer)
        answer_part = previous_answer if previous_answer and "Error:" not in str(previous_answer) else fallback_reason
        final_answer = fallback_comment + answer_part
        ai_message = AIMessage(content=final_answer)

    else:
        try:
            # Get the original query information
            intent_result = state.get("intent_analysis_result")
            original_query = intent_result.user_query if intent_result else "Unknown query"

            # Build the context for generating a dynamic response
            context = {
                "original_query": original_query,
                "error_type": reason,
                "error_details": error_message,
                "search_attempts": state.get("loop_count", 0),
                "partial_answer": state.get("answer", "")
            }

            # Generate a dynamic response via the LLM
            final_answer = await generate_dynamic_error_message(llm, context)
            ai_message = AIMessage(content=final_answer)
            logger.info(f"Fallback_Node: Generated dynamic fallback response")

        except Exception as dynamic_error:
            # If generating the dynamic response fails, use the default response
            logger.exception(f"Fallback_Node: Failed to generate dynamic response: {dynamic_error}")
            fallback_comment = "Sorry. Answer generation has stopped due to an unexpected error. The most recently generated initial draft will be displayed, and it may be an answer that does not meet the standards.\nPlease ask again in a new chat.\n\n"
            # state.get("answer") may be a list, so convert it to a string
            previous_answer = state.get("answer", "")
            if isinstance(previous_answer, list):
                previous_answer = "\n".join(str(a) for a in previous_answer)
            answer_part = previous_answer if previous_answer and "Error:" not in str(previous_answer) else fallback_reason
            final_answer = fallback_comment + answer_part
            ai_message = AIMessage(content=final_answer)

    updated.update({"node_visits": 0, "loop_count": 0})

    logger.info(f"Fallback_Node: Delivering fallback answer to user")
    return {
        "messages": [ai_message],
        "answer": final_answer,
        "status": "completed",
        **updated,
        "error": "Fallback node executed."
    }
