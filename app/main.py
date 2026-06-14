import re
from pathlib import Path
from datetime import date
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
import frontmatter


def plain_preview(md_text: str, max_len: int = 120) -> str:
    """Strip markdown formatting to produce a plain-text preview."""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', md_text)
    # Remove inline code
    text = re.sub(r'`[^`]+`', '', text)
    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove links, keep text
    text = re.sub(r'\[([^\]]*)\]\(.*?\)', r'\1', text)
    # Remove headings markers, bold/italic markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + '…'
    return text

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "content"

app = FastAPI(title="Personal Blog & Reports")

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")

md = MarkdownIt("commonmark", {"html": True}).enable("table")


def load_posts():
    posts = []
    posts_dir = CONTENT_DIR / "posts"
    if not posts_dir.exists():
        return posts
    for f in sorted(posts_dir.glob("*.md")):
        try:
            post = frontmatter.load(f)
            posts.append({
                "slug": f.stem,
                "title": post.get("title", f.stem),
                "date": post.get("date", date.today()),
                "tags": post.get("tags", []),
                "content": post.content,
                "preview": plain_preview(post.content),
            })
        except Exception:
            raw = f.read_text(encoding="utf-8")
            posts.append({
                "slug": f.stem,
                "title": f.stem,
                "date": date.today(),
                "tags": [],
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
                "name": d.name,
                "files": sorted([f.name for f in d.iterdir()]),
            })
    return reports


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "posts": load_posts()[:5],
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
