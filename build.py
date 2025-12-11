from staticjinja import Site  # type: ignore[import]
from datetime import datetime, date
from dataclasses import dataclass
import frontmatter
import markdown
import os
from pathlib import Path
from typing import List, Optional
import shutil
import argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import http.server
import socketserver
import threading
import subprocess


@dataclass
class Post:
    title: str
    date: date
    excerpt: str
    url: str
    content: str
    tags: List[str]


markdowner = markdown.Markdown(
    output_format="html",
    extensions=[
        'fenced_code', 
        'codehilite', 
        'mdx_math', 
        'tables', 
        'extra', 
        'admonition', 
        'toc',
        'pymdownx.tilde',
    ],
    extension_configs={
        'codehilite': {
            'guess_lang': True,
            'use_pygments': True,
            'css_class': 'codehilite',
        }
    }
)

def md_context(template):
    post = frontmatter.load(template.filename)
    content_html = markdowner.convert(post.content)

    return {
        "post": Post(
            title=post.metadata.get("title", "Untitled"),  # type: ignore
            date=post.metadata.get("date", datetime.now().date()),  # type: ignore
            excerpt=post.metadata.get("excerpt", ""),  # type: ignore
            url=f"/posts/{Path(template.name).stem}",
            content=content_html,
            tags=post.metadata.get("tags", []),  # type: ignore
        )
    }


def render_md(site, template, **kwargs):
    stem = Path(template.name).stem
    out = site.outpath / Path("posts/") / Path(stem) / Path("index.html")
    os.makedirs(out.parent, exist_ok=True)
    site.get_template("_post.html").stream(**kwargs).dump(str(out), encoding="utf-8")


def render_html(site, template, **kwargs):
    if template.name in ["index.html", "404.html"]:
        out = site.outpath / Path(template.name)
    else:
        stem = Path(template.name).stem
        out = site.outpath / Path(stem) / Path("index.html")
    os.makedirs(out.parent, exist_ok=True)
    template.stream(**kwargs).dump(str(out), encoding="utf-8")


def load_posts(posts_dir="src/posts"):
    posts = []
    for post_path in Path(posts_dir).glob("*.md"):
        post = frontmatter.load(str(post_path))
        content = markdowner.convert(post.content)

        posts.append(
            Post(
                title=post.metadata.get("title", "Untitled"),  # type: ignore
                date=post.metadata.get("date", datetime.now().date()),  # type: ignore
                excerpt=post.metadata.get("excerpt", ""),  # type: ignore
                url=f"/posts/{post_path.stem}/",
                content=content,
                tags=post.metadata.get("tags", []),  # type: ignore
            )
        )
    return sorted(posts, key=lambda x: x.date, reverse=True)


POSTS = load_posts()


def generate_tag_pages(site, posts):
    tags = {}
    for post in posts:
        for tag in post.tags:
            if tag not in tags:
                tags[tag] = []
            tags[tag].append(post)

    for tag, tagged_posts in tags.items():
        out = site.outpath / Path("posts/tag") / Path(tag) / Path("index.html")
        os.makedirs(out.parent, exist_ok=True)
        site.get_template("_tag.html").stream(tag=tag, posts=tagged_posts).dump(
            str(out), encoding="utf-8"
        )


def get_git_commit_hash(short=False):
    """Get the current git commit hash.

    Args:
        short (bool): If True, return the shortened version of the hash.

    Returns:
        str: The commit hash, or empty string if not in a git repository.
    """
    try:
        if short:
            return subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], text=True
            ).strip()
        else:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
    except subprocess.CalledProcessError:
        return ""


ENV_GLOBALS = {
    "year": str(datetime.now().year),
    "recent_posts": POSTS[:5],
    "posts": POSTS,
    "commit": get_git_commit_hash(short=True),
    "commit_full": get_git_commit_hash(short=False),
}


def skip_render(*args, **kwargs):
    pass


def build() -> None:
    shutil.rmtree("build", ignore_errors=True)
    site = Site.make_site(
        searchpath="src",
        outpath="build",
        staticpaths=["static"],
        contexts=[
            (r".*\.md", md_context),
        ],
        rules=[
            (r".*\.md", render_md),
            (r".*\.html", render_html),
        ],
        env_globals=ENV_GLOBALS,
    )

    site.render()
    generate_tag_pages(site, POSTS)


class RebuildHandler(FileSystemEventHandler):
    def __init__(self, build_func):
        self.build_func = build_func
        self.original_dir = os.getcwd()

    def on_any_event(self, event):
        if not event.is_directory:
            print(f"Change detected: {event.src_path}. Rebuilding...")

            current_dir = os.getcwd()

            try:
                os.chdir(self.original_dir)
                self.build_func()
            finally:
                os.chdir(current_dir)


def run_server(directory="build", port=8000):
    """Run a simple HTTP server to serve the built site"""
    handler = http.server.SimpleHTTPRequestHandler
    os.chdir(directory)

    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving at http://localhost:{port}")
        httpd.serve_forever()


def watch_and_build(path="src", port=8000):
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        os.makedirs(abs_path, exist_ok=True)
        print(f"Created missing directory: {abs_path}")

    build()

    original_dir = os.getcwd()

    server_thread = threading.Thread(target=run_server, args=("build", port))
    server_thread.daemon = True
    server_thread.start()

    event_handler = RebuildHandler(build)
    observer = Observer()
    observer.schedule(event_handler, abs_path, recursive=True)

    try:
        observer.start()
    except FileNotFoundError:
        print(
            f"Error: Could not watch directory {abs_path}. Please make sure it exists."
        )
        return

    print(
        f"Watching '{abs_path}' for changes. Site available at http://localhost:{port}"
    )
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        os.chdir(original_dir)
    observer.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="webcorev3 build script")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Serve the result, watch for changes and rebuild",
    )
    parser.add_argument(
        "--port", type=int, default=3000, help="Port for the development server"
    )
    parser.add_argument(
        "--about", action="store_true", help="Print information about webcore"
    )
    args = parser.parse_args()
    
    if args.about:
        print("webcore v3 :3 - https://n3rdl0rd.xyz/webcore")

    if args.serve:
        watch_and_build(port=args.port)
    else:
        build()