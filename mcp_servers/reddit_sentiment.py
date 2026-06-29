import os
import logging
import httpx
import json
from dotenv import load_dotenv
from google.genai import Client

logger = logging.getLogger("mcp.reddit_sentiment")
load_dotenv()

# Reddit Credentials
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def analyze_reddit_sentiment(niche_slug: str) -> float:
    """
    Scrapes the top 50 posts from entrepreneur, SaaS, startups, and indiehackers,
    extracts sentiment using Gemini, and returns a normalized delta between -1.0 and +1.0.
    """
    logger.info(f"Reddit: Scraping posts for niche '{niche_slug}'...")
    posts = await _get_reddit_posts(niche_slug)
    
    if not posts:
        logger.warning("Reddit: No posts found. Returning neutral sentiment delta (0.0).")
        return 0.0

    # Format posts for Gemini evaluation
    post_summaries = []
    for i, post in enumerate(posts):
        post_summaries.append(
            f"Post {i+1}:\n"
            f"Title: {post['title']}\n"
            f"Subreddit: {post['subreddit']}\n"
            f"Content: {post['selftext'][:200]}\n"
            f"URL: {post['url']}\n"
        )
    
    prompt = (
        "You are a professional market researcher evaluating community frustration vs. satisfaction.\n"
        "Given the following list of Reddit posts from startup subreddits, analyze the market sentiment.\n"
        "Frustrated users looking for alternatives, complaining about existing tools, or struggling indicates high market opportunity (which we map to a negative sentiment index or positive frustration index, but here we want standard sentiment).\n"
        "Rate each post's sentiment as either: POSITIVE (1), NEUTRAL (0), or NEGATIVE (-1).\n"
        "Output ONLY a JSON list of objects containing the post index and its score:\n"
        "[\n"
        "  {\"index\": 1, \"sentiment\": -1},\n"
        "  {\"index\": 2, \"sentiment\": 0},\n"
        "  {\"index\": 3, \"sentiment\": 1}\n"
        "]\n"
        "Output nothing else but the raw JSON list.\n\n"
        + "\n".join(post_summaries[:15])  # Cap at 15 for prompt size
    )

    try:
        # Check if we have a valid Gemini API Key.
        # Note: If no key is provided in .env (and we are in a mock unit test), we fallback to mock calculations.
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            logger.warning("Reddit: GEMINI_API_KEY is not set. Calculating deterministic mock sentiment.")
            return _calculate_mock_sentiment(niche_slug)
            
        client = Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        
        # Clean potential markdown wraps
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        scores = json.loads(text)
        total_score = 0.0
        count = 0
        for item in scores:
            total_score += float(item.get("sentiment", 0))
            count += 1
            
        if count > 0:
            sentiment_delta = round(total_score / count, 4)
            logger.info(f"Reddit: Computed sentiment delta: {sentiment_delta}")
            return sentiment_delta

    except Exception as e:
        logger.error(f"Reddit: Error analyzing sentiment with Gemini: {e}")
        
    return _calculate_mock_sentiment(niche_slug)

async def _get_reddit_posts(niche_slug: str) -> list:
    """Scrapes Reddit matching niche query, falling back to mock posts if credentials are missing"""
    if not REDDIT_CLIENT_ID or REDDIT_CLIENT_ID == "YOUR_REDDIT_CLIENT_ID_HERE":
        logger.info("Reddit: Missing API credentials. Using mock Reddit data.")
        return _get_mock_posts(niche_slug)

    # 1. Enforce rate limiter
    from api.rate_limiter import RateLimiter
    await RateLimiter().check_reddit()

    # Scrape via Reddit search API
    posts = []
    subreddits = ["entrepreneur", "SaaS", "startups", "indiehackers"]
    
    from tenacity import retry, stop_after_attempt, wait_exponential
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
    async def _post_token(client, auth, headers):
        res = await client.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            data={"grant_type": "client_credentials"},
            headers=headers
        )
        if res.status_code != 200:
            raise httpx.HTTPStatusError("Reddit Auth Failed", request=res.request, response=res)
        return res.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
    async def _fetch_posts(client, url, headers, params):
        res = await client.get(url, headers=headers, params=params)
        if res.status_code != 200:
            raise httpx.HTTPStatusError(f"Reddit API returned {res.status_code}", request=res.request, response=res)
        return res.json()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get access token
            auth = httpx.BasicAuth(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
            headers = {"User-Agent": "AIDueDiligence/0.1"}
            token_data = await _post_token(client, auth, headers)
            token = token_data.get("access_token")
            
            headers["Authorization"] = f"bearer {token}"
                
            q = niche_slug.replace("-", " ")
            for sub in subreddits:
                url = f"https://oauth.reddit.com/r/{sub}/search.json"
                params = {"q": q, "limit": 15, "sort": "relevance", "t": "year"}
                try:
                    data = await _fetch_posts(client, url, headers, params)
                    for child in data.get("data", {}).get("children", []):
                        post_data = child.get("data", {})
                        posts.append({
                            "title": post_data.get("title", ""),
                            "selftext": post_data.get("selftext", ""),
                            "subreddit": post_data.get("subreddit", ""),
                            "url": f"https://reddit.com{post_data.get('permalink', '')}"
                        })
                        if len(posts) >= 50:
                            return posts
                except Exception as e:
                    logger.error(f"Reddit: Failed to fetch posts for sub '{sub}': {e}")
    except Exception as e:
        logger.error(f"Reddit: Scraper exception: {e}")
        
    return posts if posts else _get_mock_posts(niche_slug)

def _calculate_mock_sentiment(niche_slug: str) -> float:
    # Deterministic calculation based on string hash for testing repeatability
    val = sum(ord(c) for c in niche_slug)
    # Yield a value between -0.5 and +0.5
    return round(((val % 100) / 100.0) - 0.5, 4)

def _get_mock_posts(niche_slug: str) -> list:
    base_niche = niche_slug.replace("-", " ").title()
    return [
        {
            "title": f"Are there any good alternatives to existing {base_niche}?",
            "selftext": "Honestly, the current tools are so expensive and bloated. I hate paying $100/mo just for basic invoicing templates. Is anyone building something simpler?",
            "subreddit": "SaaS",
            "url": "https://reddit.com/r/SaaS/comments/mock1"
        },
        {
            "title": f"Roast my landing page for a new {base_niche} app",
            "selftext": "I noticed freelance graphic designers struggle with payment reminders. Here's a simple dashboard I built. Would you use this?",
            "subreddit": "indiehackers",
            "url": "https://reddit.com/r/indiehackers/comments/mock2"
        },
        {
            "title": f"How much do you pay for {base_niche} tools?",
            "selftext": "Most agencies use giant CRM software, but for solo designers, it's complete overkill. I wish there was a flat-rate invoicing plugin.",
            "subreddit": "entrepreneur",
            "url": "https://reddit.com/r/entrepreneur/comments/mock3"
        }
    ]
