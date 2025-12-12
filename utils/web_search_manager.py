import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import aiohttp
from bs4 import BeautifulSoup
import requests

from config import Config


@dataclass
class SearchResult:
    """Represents a search result from any provider"""
    title: str
    url: str
    snippet: str
    source: str
    timestamp: float


class WebSearchManager:
    """Manages web search across multiple providers with smart fallback"""

    def __init__(self):
        self.providers = {
            'tavily': TavilySearchProvider(),
            'perplexity': PerplexitySearchProvider(),
            'openrouter': OpenRouterSearchProvider(),
            'scraping': DirectScrapingProvider()
        }
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache TTL

    async def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """
        Execute search with fallback strategy based on priority
        Priority: 1=Tavily, 2=Perplexity, 3=OpenRouter
        """
        # Check cache first
        cache_key = f"{query}_{max_results}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data

        results = []
        last_error = None

        # Try providers in priority order
        for provider_name in Config.WEB_SEARCH_PRIORITY:
            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]

            # Check if provider is configured
            if not provider.is_configured():
                continue

            try:
                # Implement exponential backoff for retries
                for attempt in range(3):
                    try:
                        results = await provider.search(query, max_results, **kwargs)
                        if results:
                            # Cache successful results
                            self.cache[cache_key] = (results, time.time())
                            return results
                        break
                    except Exception as e:
                        if attempt == 2:  # Last attempt
                            last_error = e
                            break
                        # Exponential backoff: 1s, 2s, 4s
                        await asyncio.sleep(2 ** attempt)

            except Exception as e:
                last_error = e
                print(f"Provider {provider_name} failed: {str(e)}")
                continue

        # If all providers fail, return empty or raise
        if last_error:
            print(f"All web search providers failed. Last error: {str(last_error)}")

        return []


class TavilySearchProvider:
    """Tavily API search provider (Primary)"""

    def __init__(self):
        self.api_key = Config.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """Search using Tavily API"""
        if not self.is_configured():
            raise ValueError("Tavily API key not configured")

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "include_answer": True,
            "include_raw_content": False,
            "max_results": max_results,
            "include_domains": kwargs.get('include_domains', []),
            "exclude_domains": kwargs.get('exclude_domains', [])
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"Tavily API error: {response.status}")

                data = await response.json()
                results = []

                # Process answer if available
                if data.get('answer'):
                    results.append(SearchResult(
                        title="Tavily AI Answer",
                        url="",
                        snippet=data['answer'],
                        source="tavily",
                        timestamp=time.time()
                    ))

                # Process search results
                for result in data.get('results', []):
                    results.append(SearchResult(
                        title=result.get('title', ''),
                        url=result.get('url', ''),
                        snippet=result.get('content', ''),
                        source="tavily",
                        timestamp=time.time()
                    ))

                return results


class PerplexitySearchProvider:
    """Perplexity API search provider (Secondary)"""

    def __init__(self):
        self.api_key = Config.PERPLEXITY_API_KEY
        self.base_url = "https://api.perplexity.ai/search"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """Search using Perplexity API"""
        if not self.is_configured():
            raise ValueError("Perplexity API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "llama-3.1-sonar-large-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful research assistant. Provide accurate, up-to-date information with sources."
                },
                {
                    "role": "user",
                    "content": f"Search for: {query}. Provide a comprehensive answer with relevant sources."
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.1
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"Perplexity API error: {response.status}")

                data = await response.json()
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '')

                # Parse response into SearchResult format
                results = []
                results.append(SearchResult(
                    title="Perplexity Search Results",
                    url="",
                    snippet=content,
                    source="perplexity",
                    timestamp=time.time()
                ))

                return results


class OpenRouterSearchProvider:
    """OpenRouter models with web search capabilities (Tertiary)"""

    def __init__(self):
        self.api_key = Config.OPENROUTER_API_KEY
        self.base_url = Config.OPENROUTER_API_URL
        # Models known to have web access
        self.web_search_models = [
            "anthropic/claude-3.5-sonnet",
            "anthropic/claude-3-opus",
            "openai/gpt-4o"
        ]

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """Search using OpenRouter models with web access"""
        if not self.is_configured():
            raise ValueError("OpenRouter API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://skills-pipeline.local",
            "X-Title": "AI Skills Pipeline"
        }

        # Try models in order of preference
        for model in self.web_search_models:
            try:
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a research assistant with access to current web information. Search for and provide accurate, up-to-date information with sources when possible."
                        },
                        {
                            "role": "user",
                            "content": f"Search the web for: {query}. Provide a comprehensive answer with current information and cite sources if available."
                        }
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.2
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(self.base_url, headers=headers, json=payload) as response:
                        if response.status != 200:
                            continue

                        data = await response.json()
                        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')

                        results = []
                        results.append(SearchResult(
                            title=f"Web Search via {model}",
                            url="",
                            snippet=content,
                            source="openrouter",
                            timestamp=time.time()
                        ))

                        return results

            except Exception as e:
                print(f"OpenRouter model {model} failed: {str(e)}")
                continue

        raise Exception("All OpenRouter web search models failed")


class DirectScrapingProvider:
    """Fallback direct web scraping provider"""

    def __init__(self):
        self.session = None

    def is_configured(self) -> bool:
        return True  # Always available as fallback

    async def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        """Basic web scraping fallback"""
        # Use DuckDuckGo HTML search for basic results
        search_url = f"https://html.duckduckgo.com/html/?q={query}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers={'User-Agent': 'Mozilla/5.0'}) as response:
                    if response.status != 200:
                        raise Exception(f"Web scraping failed: {response.status}")

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    results = []
                    # Parse DuckDuckGo results
                    for result in soup.find_all('div', class_='result')[:max_results]:
                        title_tag = result.find('a', class_='result__a')
                        snippet_tag = result.find('a', class_='result__snippet')

                        if title_tag and snippet_tag:
                            title = title_tag.get_text(strip=True)
                            url = title_tag.get('href', '')
                            snippet = snippet_tag.get_text(strip=True)

                            results.append(SearchResult(
                                title=title,
                                url=url,
                                snippet=snippet,
                                source="scraping",
                                timestamp=time.time()
                            ))

                    return results

        except Exception as e:
            raise Exception(f"Direct scraping failed: {str(e)}")


# Exponential backoff utility
async def exponential_backoff_retry(func, max_retries=3, base_delay=1):
    """Utility for exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)