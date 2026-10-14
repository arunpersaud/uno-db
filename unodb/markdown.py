"""Markdown for texts users write (rules of the game types).

CommonMark with raw HTML switched off: HTML in the text shows up as text,
markdown-it refuses javascript:/data: links, images are off (the CSP
blocks other sites' images anyway), and links get rel="nofollow ugc".
"""

from markdown_it import MarkdownIt
from markupsafe import Markup

_md = MarkdownIt("commonmark", {"html": False, "linkify": False}).disable("image")


def _link_open(renderer, tokens, idx, options, env):
    tokens[idx].attrSet("rel", "nofollow ugc")
    return renderer.renderToken(tokens, idx, options, env)


_md.add_render_rule("link_open", _link_open)


def render(text: str | None) -> Markup:
    return Markup(_md.render(text or ""))
