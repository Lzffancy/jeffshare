import re
import json
import uuid
import time
import logging
import contextvars
from pathlib import Path
from datetime import date
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
import frontmatter

# ── logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("blog")
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")

# 关闭 uvicorn 自带 access log（我们的中间件已输出 REQ/RSP）
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ── helpers ───────────────────────────────────────────────────────────
def plain_preview(md_text: str, max_len: int = 120) -> str:
    """Strip markdown formatting to produce a plain-text preview."""
    text = re.sub(r'```[\s\S]*?```', '', md_text)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]*)\]\(.*?\)', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + '…'
    return text


# ── app ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "content"

app = FastAPI(title="Personal Blog & Reports")

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")

md = MarkdownIt("commonmark", {"html": True}).enable("table")


# ── trace-log middleware ──────────────────────────────────────────────
@app.middleware("http")
async def trace_log_middleware(request: Request, call_next):
    # trace_id: use incoming header or generate 12-char hex
    trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:12]
    trace_id_var.set(trace_id)

    start_ts = time.time()

    # ── REQ: 完整 HTTP 请求信息 ──
    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    req_payload = {
        "trace_id": trace_id,
        "method":  request.method,
        "url":     f"{scheme}://{request.headers.get('host', '-')}{request.url.path}",
        "path":    request.url.path,
        "query":   request.url.query or "-",
        "client":  f"{request.client.host}:{request.client.port}" if request.client else "-",
        "user_agent":      request.headers.get("user-agent", "-"),
        "referer":         request.headers.get("referer", "-"),
        "content_type":    request.headers.get("content-type", "-"),
        "content_length":  request.headers.get("content-length", "-"),
        "x_forwarded_for": request.headers.get("x-forwarded-for", "-"),
    }
    logger.info(f"REQ | {json.dumps(req_payload, ensure_ascii=False)}")

    # ── process ──
    response = await call_next(request)

    # ── RSP: HTML/Markdown 页面只打印资源路径 ──
    duration_ms = round((time.time() - start_ts) * 1000, 1)
    content_type = response.headers.get("content-type", "")

    if "text/html" in content_type or "text/markdown" in content_type:
        rsp_detail = f"path={request.url.path} type=page"
    else:
        rsp_detail = (
            f"path={request.url.path} "
            f"status={response.status_code} "
            f"content_type={content_type} "
            f"size={response.headers.get('content-length', '-')}"
        )

    logger.info(f"RSP | trace_id={trace_id} | {rsp_detail} | duration={duration_ms}ms")

    response.headers["X-Trace-Id"] = trace_id
    return response


# ── content loaders ───────────────────────────────────────────────────
def load_posts():
    posts = []
    posts_dir = CONTENT_DIR / "posts"
    if not posts_dir.exists():
        return posts
    for f in sorted(posts_dir.glob("*.md")):
        try:
            post = frontmatter.load(f)
            posts.append({
                "slug":    f.stem,
                "title":   post.get("title", f.stem),
                "date":    post.get("date", date.today()),
                "tags":    post.get("tags", []),
                "content": post.content,
                "preview": plain_preview(post.content),
            })
        except Exception:
            raw = f.read_text(encoding="utf-8")
            posts.append({
                "slug":    f.stem,
                "title":   f.stem,
                "date":    date.today(),
                "tags":    [],
                "content": raw,
                "preview": plain_preview(raw),
            })
    return sorted(posts, key=lambda p: p["date"], reverse=True)


def load_reports():
    reports = []
    reports_dir = CONTENT_DIR / "reports"
    if not reports_dir.exists():
        return reports
    for d in sorted(reports_dir.iterdir()):
        if d.is_dir():
            reports.append({
                "name":  d.name,
                "files": sorted([f.name for f in d.iterdir()]),
            })
    return reports


# ── routes ────────────────────────────────────────────────────────────
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "posts":   load_posts()[:5],
        "reports": load_reports(),
    })


@app.get("/blog")
def blog_list(request: Request):
    return templates.TemplateResponse(request, "blog_list.html", {
        "posts": load_posts(),
    })


@app.get("/blog/{slug}")
def blog_post(request: Request, slug: str):
    posts = {p["slug"]: p for p in load_posts()}
    if slug not in posts:
        raise HTTPException(404, detail="Post not found")
    post = posts[slug]
    html = md.render(post["content"])
    return templates.TemplateResponse(request, "blog_post.html", {
        "post": post,
        "html": html,
    })


@app.get("/reports")
def reports_list(request: Request):
    return templates.TemplateResponse(request, "reports_list.html", {
        "reports": load_reports(),
    })
