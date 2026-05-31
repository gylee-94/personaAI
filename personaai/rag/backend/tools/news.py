import feedparser
from urllib.parse import quote
from typing import List, Dict, Optional


class GoogleNews:
    """
    A class that searches Google News and returns the results.
    """

    def __init__(self):
        """
        Initializes the GoogleNews class.
        Sets the base_url attribute.
        """
        self.base_url = "https://news.google.com/rss"

    def _fetch_news(self, url: str, k: int = 3) -> List[Dict[str, str]]:
        """
        Fetches news from the given URL.

        Args:
            url (str): The URL to fetch news from
            k (int): The maximum number of news items to fetch (default: 3)

        Returns:
            List[Dict[str, str]]: A list of dictionaries containing news titles and links
        """
        news_data = feedparser.parse(url)
        return [
            {"title": entry.title, "link": entry.link}
            for entry in news_data.entries[:k]
        ]

    def _collect_news(self, news_list: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Organizes and returns the news list.

        Args:
            news_list (List[Dict[str, str]]): A list of dictionaries containing news information

        Returns:
            List[Dict[str, str]]: A list of dictionaries containing URLs and content
        """
        if not news_list:
            print("There is no news for the given keyword.")
            return []

        result = []
        for news in news_list:
            result.append({"url": news["link"], "content": news["title"]})

        return result

    def search_latest(self, k: int = 3) -> List[Dict[str, str]]:
        """
        Searches for the latest news.

        Args:
            k (int): The maximum number of news items to search for (default: 3)

        Returns:
            List[Dict[str, str]]: A list of dictionaries containing URLs and content
        """
        url = f"{self.base_url}?hl=ko&gl=KR&ceid=KR:ko"
        news_list = self._fetch_news(url, k)
        return self._collect_news(news_list)

    def search_by_keyword(
        self, keyword: Optional[str] = None, k: int = 3
    ) -> List[Dict[str, str]]:
        """
        Searches for news by keyword.

        Args:
            keyword (Optional[str]): The keyword to search for (default: None)
            k (int): The maximum number of news items to search for (default: 3)

        Returns:
            List[Dict[str, str]]: A list of dictionaries containing URLs and content
        """
        if keyword:
            encoded_keyword = quote(keyword)
            url = f"{self.base_url}/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
        else:
            url = f"{self.base_url}?hl=ko&gl=KR&ceid=KR:ko"
        news_list = self._fetch_news(url, k)
        return self._collect_news(news_list)
