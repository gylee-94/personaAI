from langchain_core.tools import BaseTool
from langchain_core.documents import Document

from pydantic import BaseModel, Field
from tavily import TavilyClient
from typing import Literal, Sequence, Optional, List
import json
import os
import asyncio


class TavilySearchInput(BaseModel):
    """Input format for the Tavily tool."""

    query: str = Field(description="Search query")


def format_search_result(result: dict, include_raw_content: bool = False) -> Document:
    """
    Utility function for formatting search results.

    Args:
        result (dict): The original search result

    Returns:
        str: Search result formatted as XML
    """
    # Use json.dumps() to handle Korean character encoding
    title = json.dumps(result["title"], ensure_ascii=False)[1:-1]
    content = json.dumps(result["content"], ensure_ascii=False)[1:-1]
    raw_content = ""
    if (
        include_raw_content
        and "raw_content" in result
        and result["raw_content"] is not None
        and len(result["raw_content"].strip()) > 0
    ):
        raw_content = f"<raw>{result['raw_content']}</raw>"

    # f"<document><title>{title}</title><url>{result['url']}</url><content>{content}</content>{raw_content}</document>"
    return Document(
        page_content=f"<document><title>{title}</title><url>{result['url']}</url><content>{content}</content>{raw_content}</document>",
        metadata={
            "source": result["url"],
            "title": title,
            "content": content,
            "raw_content": raw_content,
        }
    )



class TavilySearch(BaseTool):
    """
    Tool that queries the Tavily Search API and gets back json
    """

    name: str = "tavily_web_search"
    description: str = (
        "A search engine optimized for comprehensive, accurate, and trusted results. "
        "Useful for when you need to answer questions about current events. "
        "Input should be a search query. [IMPORTANT] Input(query) should be over 5 characters."
    )
    args_schema: type[BaseModel] = TavilySearchInput
    client: TavilyClient = None
    include_domains: list = []
    exclude_domains: list = []
    max_results: int = 5
    topic: Literal["general", "news"] = "general"
    days: int = 3
    search_depth: Literal["basic", "advanced"] = "basic"
    include_answer: bool = False
    include_raw_content: bool = False
    include_images: bool = False
    format_output: bool = False

    def __init__(
        self,
        api_key: Optional[str] = None,
        include_domains: list = [],
        exclude_domains: list = [],
        max_results: int = 5,
        topic: Literal["general", "news"] = "general",
        days: int = 3,
        search_depth: Literal["basic", "advanced"] = "basic",
        include_answer: bool = False,
        include_raw_content: bool = False,
        include_images: bool = False,
        format_output: bool = False,
    ):
        """
        Initializes an instance of the TavilySearch class.

        Args:
            api_key (str): Tavily API key
            include_domains (list): List of domains to include in the search
            exclude_domains (list): List of domains to exclude from the search
            max_results (int): Default number of search results
        """
        super().__init__()
        if api_key is None:
            api_key = os.environ.get("TAVILY_API_KEY", None)

        if api_key is None:
            raise ValueError("Tavily API key is not set.")

        self.client = TavilyClient(api_key=api_key)
        self.include_domains = include_domains
        self.exclude_domains = exclude_domains
        self.max_results = max_results
        self.topic = topic
        self.days = days
        self.search_depth = search_depth
        self.include_answer = include_answer
        self.include_raw_content = include_raw_content
        self.include_images = include_images
        self.format_output = format_output

    def _run(self, query: str) -> str:
        """Implementation of BaseTool's _run method"""
        results = self.search(query)
        return results
        # return json.dumps(results, ensure_ascii=False)

    async def _arun(self, query: str) -> List[Document]:
        """Implementation of BaseTool's asynchronous _arun method"""
        results = await asyncio.to_thread(
            self.search,
            query=query,
            include_raw_content=False
        )
        return results

    def search(
        self,
        query: str,
        search_depth: Literal["basic", "advanced"] = None,
        topic: Literal["general", "news"] = None,
        days: int = None,
        max_results: int = 5,
        include_domains: Sequence[str] = None,
        exclude_domains: Sequence[str] = None,
        include_answer: bool = None,
        include_raw_content: bool = None,
        include_images: bool = None,
        format_output: bool = True,
        **kwargs,
    ) -> list:
        """
        Performs a search and returns the results.

        Args:
            query (str): Search query
            search_depth (str): Search depth ("basic" or "advanced")
            topic (str): Search topic ("general" or "news")
            days (int): Date range to search
            max_results (int): Maximum number of search results
            include_domains (list): List of domains to include in the search
            exclude_domains (list): List of domains to exclude from the search
            include_answer (bool): Whether to include an answer
            include_raw_content (bool): Whether to include the raw content
            include_images (bool): Whether to include images
            format_output (bool): Whether to format the results
            **kwargs: Additional keyword arguments

        Returns:
            list: List of search results
        """
        # Set default values
        params = {
            "query": query,
            "search_depth": search_depth or self.search_depth,
            "topic": topic or self.topic,
            "max_results": max_results or self.max_results,
            "include_domains": include_domains or self.include_domains,
            "exclude_domains": exclude_domains or self.exclude_domains,
            "include_answer": (
                include_answer if include_answer is not None else self.include_answer
            ),
            "include_raw_content": (
                include_raw_content
                if include_raw_content is not None
                else self.include_raw_content
            ),
            "include_images": (
                include_images if include_images is not None else self.include_images
            ),
            **kwargs,
        }

        # Handle the days parameter
        if days is not None:
            if params["topic"] == "general":
                print(
                    "Warning: days parameter is ignored for 'general' topic search. Set topic parameter to 'news' to use days."
                )
            else:
                params["days"] = days

        # API call
        response = self.client.search(**params)

        # Format the results
        format_output = (
            format_output if format_output is not None else self.format_output
        )
        if format_output:
            return [format_search_result(r, params["include_raw_content"]) for r in response["results"]]

        else:
            return response["results"]

    def get_search_context(
        self,
        query: str,
        search_depth: Literal["basic", "advanced"] = "basic",
        topic: Literal["general", "news"] = "general",
        days: int = 3,
        max_results: int = 5,
        include_domains: Sequence[str] = None,
        exclude_domains: Sequence[str] = None,
        max_tokens: int = 4000,
        format_output: bool = True,
        **kwargs,
    ) -> str:
        """
        Retrieves context for a search query. Useful for fetching only the relevant content
        from websites, without having to handle context extraction and limiting yourself.

        Args:
            query (str): Search query
            search_depth (str): Search depth ("basic" or "advanced")
            topic (str): Search topic ("general" or "news")
            days (int): Date range to search
            max_results (int): Maximum number of search results
            include_domains (list): List of domains to include in the search
            exclude_domains (list): List of domains to exclude from the search
            max_tokens (int): Maximum number of tokens to return. Defaults to 4000.
            format_output (bool): Whether to format the results
            **kwargs: Additional keyword arguments

        Returns:
            str: A JSON string containing the search context up to the context limit
        """
        response = self.client.search(
            query,
            search_depth=search_depth,
            topic=topic,
            days=days,
            max_results=max_results,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            include_answer=False,
            include_raw_content=False,
            include_images=False,
            **kwargs,
        )

        sources = response.get("results", [])
        if format_output:
            context = [
                format_search_result(source, include_raw_content=False)
                for source in sources
            ]
        else:
            context = [
                {
                    "url": source["url"],
                    "content": json.dumps(
                        {"title": source["title"], "content": source["content"]},
                        ensure_ascii=False,
                    ),
                }
                for source in sources
            ]

        # The max_tokens handling logic should be implemented here.
        # For now, it simply returns all the context.
        return json.dumps(context, ensure_ascii=False)
