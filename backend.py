"""
AI 뉴스 앱 백엔드
- RSS 피드에서 AI 관련 뉴스 수집
- Claude API로 한국어 요약 생성
- FastAPI로 REST API 제공
"""

import asyncio
import os
import time
import hashlib
import json
from datetime import datetime
from typing import Optional

import anthropic
import feedparser
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="AI 뉴스 앱", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Claude API 클라이언트
client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수 사용

# RSS 피드 소스 목록
RSS_FEEDS = [
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "category": "AI 일반",
    },
    {
        "name": "MIT Technology Review - AI",
        "url": "https://www.technologyreview.com/feed/",
        "category": "AI 연구",
    },
    {
        "name": "The Verge - AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "category": "AI 일반",
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "category": "AI 비즈니스",
    },
    {
        "name": "Google AI Blog",
        "url": "https://blog.google/technology/ai/rss/",
        "category": "AI 연구",
    },
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "category": "AI 연구",
    },
]

# 간단한 메모리 캐시
_cache: dict = {}
CACHE_TTL = 600  # 10분


def get_cache_key(key: str) -> str:
    return hashlib.md5(key.encode()).hexdigest()


def get_cached(key: str) -> Optional[dict]:
    cache_key = get_cache_key(key)
    if cache_key in _cache:
        entry = _cache[cache_key]
        if time.time() - entry["timestamp"] < CACHE_TTL:
            return entry["data"]
        del _cache[cache_key]
    return None


def set_cached(key: str, data: dict):
    cache_key = get_cache_key(key)
    _cache[cache_key] = {"data": data, "timestamp": time.time()}


def fetch_rss_articles(max_per_feed: int = 5) -> list[dict]:
    """RSS 피드에서 기사 수집"""
    articles = []

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:max_per_feed]:
                # 기사 설명 추출
                description = ""
                if hasattr(entry, "summary"):
                    description = entry.summary
                elif hasattr(entry, "description"):
                    description = entry.description

                # HTML 태그 간단 제거
                import re
                description = re.sub(r"<[^>]+>", "", description).strip()
                description = description[:500]  # 최대 500자

                # 발행일 파싱
                published = ""
                if hasattr(entry, "published"):
                    published = entry.published
                elif hasattr(entry, "updated"):
                    published = entry.updated

                articles.append({
                    "title": entry.get("title", "제목 없음"),
                    "link": entry.get("link", ""),
                    "description": description,
                    "published": published,
                    "source": feed_info["name"],
                    "category": feed_info["category"],
                })
        except Exception as e:
            print(f"[경고] {feed_info['name']} 피드 가져오기 실패: {e}")
            continue

    # 최신순 정렬 (published 필드 기준)
    articles.sort(key=lambda x: x.get("published", ""), reverse=True)
    return articles


async def summarize_with_claude(articles: list[dict]) -> list[dict]:
    """Claude API를 사용해 기사들을 한국어로 요약"""

    articles_text = ""
    for i, article in enumerate(articles):
        articles_text += f"""
---
기사 {i + 1}:
제목: {article['title']}
출처: {article['source']}
카테고리: {article['category']}
내용: {article['description']}
링크: {article['link']}
발행일: {article['published']}
---
"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",  # 비용 효율적인 Haiku 사용
            max_tokens=4096,
            system="""당신은 AI 뉴스 큐레이터입니다. 주어진 AI 관련 뉴스 기사들을 분석하고 한국어로 요약해주세요.

각 기사에 대해 다음 JSON 형식으로 응답해주세요:
[
  {
    "index": 기사 번호(0부터),
    "summary_ko": "한국어 요약 (2-3문장)",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2"],
    "importance": "high" 또는 "medium" 또는 "low",
    "tags": ["태그1", "태그2"]
  }
]

중요도 판단 기준:
- high: 업계 전체에 영향을 미치는 중대 발표, 혁신적 기술 발전
- medium: 주요 기업의 AI 관련 업데이트, 주목할 연구 결과
- low: 일반적인 AI 뉴스, 소규모 업데이트

반드시 유효한 JSON 배열만 출력하세요. 다른 텍스트는 포함하지 마세요.""",
            messages=[
                {
                    "role": "user",
                    "content": f"다음 AI 뉴스 기사들을 분석하고 요약해주세요:\n{articles_text}",
                }
            ],
        )

        # JSON 파싱
        response_text = response.content[0].text.strip()

        # JSON 배열 추출 (혹시 다른 텍스트가 포함된 경우)
        import re
        json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
        if json_match:
            summaries = json.loads(json_match.group())
        else:
            summaries = json.loads(response_text)

        # 요약 정보를 기사에 병합
        for summary in summaries:
            idx = summary.get("index", -1)
            if 0 <= idx < len(articles):
                articles[idx]["summary_ko"] = summary.get("summary_ko", "")
                articles[idx]["key_points"] = summary.get("key_points", [])
                articles[idx]["importance"] = summary.get("importance", "medium")
                articles[idx]["tags"] = summary.get("tags", [])

    except anthropic.APIError as e:
        print(f"[오류] Claude API 호출 실패: {e}")
        # API 실패 시 기본값 설정
        for article in articles:
            article.setdefault("summary_ko", "요약을 불러올 수 없습니다.")
            article.setdefault("key_points", [])
            article.setdefault("importance", "medium")
            article.setdefault("tags", [])
    except json.JSONDecodeError as e:
        print(f"[오류] JSON 파싱 실패: {e}")
        for article in articles:
            article.setdefault("summary_ko", "요약 파싱에 실패했습니다.")
            article.setdefault("key_points", [])
            article.setdefault("importance", "medium")
            article.setdefault("tags", [])

    return articles


@app.get("/api/news")
async def get_news(
    max_articles: int = Query(default=15, ge=1, le=50, description="최대 기사 수"),
    summarize: bool = Query(default=True, description="Claude 요약 포함 여부"),
):
    """AI 뉴스 가져오기 API"""

    cache_key = f"news_{max_articles}_{summarize}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # RSS 피드에서 기사 수집
    articles = fetch_rss_articles(max_per_feed=max_articles // len(RSS_FEEDS) + 1)
    articles = articles[:max_articles]

    if not articles:
        raise HTTPException(status_code=503, detail="뉴스를 가져올 수 없습니다.")

    # Claude로 요약
    if summarize:
        articles = await summarize_with_claude(articles)

    result = {
        "articles": articles,
        "total": len(articles),
        "fetched_at": datetime.now().isoformat(),
        "sources": [f["name"] for f in RSS_FEEDS],
    }

    set_cached(cache_key, result)
    return result


@app.get("/api/sources")
async def get_sources():
    """사용 가능한 뉴스 소스 목록"""
    return {"sources": RSS_FEEDS}


@app.get("/api/health")
async def health_check():
    """서버 상태 확인"""
    api_key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {
        "status": "ok",
        "api_key_configured": api_key_set,
        "timestamp": datetime.now().isoformat(),
    }


# 정적 파일 서빙 (프론트엔드)
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))


if __name__ == "__main__":
    print("=" * 50)
    print("  AI 뉴스 앱 서버 시작")
    print("  http://localhost:8000")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
