# AI 뉴스 브리핑 앱

RSS 피드에서 AI 관련 뉴스를 수집하고 Claude API로 한국어 요약을 생성하는 웹 앱입니다.

## 기능

- **RSS 뉴스 수집**: TechCrunch, The Verge, MIT Technology Review, VentureBeat 등 6개 소스
- **Claude AI 요약**: 각 기사를 한국어 2-3문장으로 요약 + 핵심 포인트 추출
- **중요도 분류**: Claude가 기사별 중요도(high/medium/low)를 판단
- **태그 자동 생성**: 기사 내용 기반 자동 태그 부여
- **필터링**: 중요도별 필터링 지원
- **캐싱**: 10분간 결과 캐싱으로 API 비용 절감

## 아키텍처

```
[RSS 피드] → [FastAPI 백엔드] → [Claude API 요약] → [웹 프론트엔드]
```

- **백엔드**: Python + FastAPI
- **프론트엔드**: Vanilla JS (단일 HTML 파일)
- **AI 요약**: Claude Haiku 4.5 (비용 효율적)

## 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### 3. 서버 실행

```bash
python backend.py
```

브라우저에서 http://localhost:8000 접속

## API 엔드포인트

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /` | 웹 프론트엔드 |
| `GET /api/news?max_articles=15&summarize=true` | AI 뉴스 가져오기 |
| `GET /api/sources` | 뉴스 소스 목록 |
| `GET /api/health` | 서버 상태 확인 |

## 뉴스 소스

| 소스 | 카테고리 |
|------|---------|
| TechCrunch AI | AI 일반 |
| MIT Technology Review | AI 연구 |
| The Verge AI | AI 일반 |
| VentureBeat AI | AI 비즈니스 |
| Google AI Blog | AI 연구 |
| OpenAI Blog | AI 연구 |

## 비용 참고

- Claude Haiku 4.5 사용: 입력 $1.00/1M 토큰, 출력 $5.00/1M 토큰
- 15개 기사 요약 1회 약 $0.01 미만
- 10분 캐싱으로 반복 호출 방지
