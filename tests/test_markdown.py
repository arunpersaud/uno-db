from unodb.markdown import render


def test_lists_and_emphasis():
    html = render("We play with these rules:\n* one\n* **two**")
    assert "<p>We play with these rules:</p>" in html
    assert "<li>one</li>" in html
    assert "<strong>two</strong>" in html


def test_html_is_text():
    html = render('<script>alert(1)</script> <img src=x onerror="alert(1)">')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img" not in html


def test_links():
    assert 'href="https://example.org" rel="nofollow ugc"' in render(
        "[x](https://example.org)"
    )
    assert "href" not in render("[x](javascript:alert(1))")
    assert "<img" not in render("![x](https://example.org/a.png)")


def test_empty():
    assert render(None) == ""
