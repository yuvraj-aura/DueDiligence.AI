import os
import logging
import httpx
from dotenv import load_dotenv

logger = logging.getLogger("mcp.web_scraper")
load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

async def search_competitors(niche_slug: str) -> list:
    """
    Search for competitors using SerpAPI.
    Returns a list of dictionaries with competitor name, URL, founding year, and review count.
    Falls back to mock data if SerpAPI key is missing or calls fail.
    """
    if not SERPAPI_KEY or SERPAPI_KEY == "YOUR_SERPAPI_KEY_HERE":
        logger.warning("SerpAPI key not found. Using mock competitor database.")
        return _get_mock_competitors(niche_slug)
        
    url = "https://serpapi.com/search.json"
    queries = [f"{niche_slug} software", f"best {niche_slug} alternatives"]
    competitors = {}

    from tenacity import retry, stop_after_attempt, wait_exponential
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
    async def _fetch_serpapi_with_retry(client, q):
        params = {
            "engine": "google",
            "q": q,
            "api_key": SERPAPI_KEY
        }
        response = await client.get(url, params=params)
        if response.status_code != 200:
            raise httpx.HTTPStatusError(f"SerpAPI returned {response.status_code}", request=response.request, response=response)
        return response.json()

    async with httpx.AsyncClient(timeout=10.0) as client:
        for q in queries:
            try:
                data = await _fetch_serpapi_with_retry(client, q)
                # Parse organic results
                for result in data.get("organic_results", []):
                    title = result.get("title", "")
                    link = result.get("link", "")
                    snippet = result.get("snippet", "")
                    
                    # Exclude informational links like blogs/news if possible
                    if link and title and not any(x in link.lower() for x in ["blog", "news", "reddit", "youtube", "wikipedia"]):
                        # Clean competitor name from title (e.g. "Competitor: Invoicing Tool" -> "Competitor")
                        name = title.split(" - ")[0].split(" | ")[0].split(":")[0].strip()
                        if name not in competitors:
                            # Parse founding year and review counts from snippet if they exist, else default
                            competitors[name] = {
                                "name": name,
                                "url": link,
                                "founding_year": _extract_founding_year(snippet),
                                "review_count": _extract_reviews(snippet)
                            }
            except Exception as e:
                logger.error(f"SerpAPI request error for query '{q}': {e}")
                
    result_list = list(competitors.values())[:20]
    
    # If API returned nothing, use mock database
    if not result_list:
        return _get_mock_competitors(niche_slug)
        
    return result_list

def _extract_founding_year(text: str) -> int:
    import re
    # Simple regex searching for years between 1990 and 2026
    match = re.search(r'\b(199[0-9]|20[0-2][0-6])\b', text)
    return int(match.group(1)) if match else 2021  # Default fallback founding year

def _extract_reviews(text: str) -> int:
    import re
    # Simple regex to search for reviews, e.g. "Rating: 4.8 - 1,200 reviews" or "500 votes"
    match = re.search(r'(\d+[\d,]*)\s*(?:reviews|votes|ratings)', text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return 150  # Default fallback reviews count

def _get_mock_competitors(niche_slug: str) -> list:
    """Fallback generator for local testing"""
    base_niche = niche_slug.replace("-", " ").title()
    return [
        {
            "name": f"{base_niche} Pro",
            "url": f"https://www.{niche_slug}pro.com",
            "founding_year": 2018,
            "review_count": 450
        },
        {
            "name": f"{base_niche} Flow",
            "url": f"https://www.{niche_slug}flow.io",
            "founding_year": 2020,
            "review_count": 280
        },
        {
            "name": f"Easy {base_niche}",
            "url": f"https://www.easy{niche_slug.replace('-', '')}.com",
            "founding_year": 2022,
            "review_count": 95
        },
        {
            "name": f"Cloud {base_niche}",
            "url": f"https://www.cloud{niche_slug.replace('-', '')}.net",
            "founding_year": 2015,
            "review_count": 1200
        },
        {
            "name": f"Simple {base_niche}",
            "url": f"https://www.simple{niche_slug.replace('-', '')}.co",
            "founding_year": 2023,
            "review_count": 40
        }
    ]
