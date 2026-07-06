# 교권지기 MCP 서버 — 카카오 클라우드(PlayMCP in KC) Git 소스 빌드용
# linux/amd64 대상. Streamable HTTP(:8000/mcp)로 서비스. 순수 파이썬(무거운 의존 없음).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 카카오 클라우드는 PORT 환경변수를 주입할 수 있다(없으면 8000).
# 법제처 API 키는 LAW_OC 환경변수로 덮어쓸 수 있다.
ENV PORT=8000
EXPOSE 8000

CMD ["python", "mcp_server.py"]
