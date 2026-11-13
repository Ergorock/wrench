import pytest

from wrench.shared.git.remote import host_kind, is_remote_url, web_url


@pytest.mark.parametrize(
    "url,kind,web",
    [
        ("git@github.com:Ergorock/wrench.git", "github", "https://github.com/Ergorock/wrench"),
        ("https://github.com/Ergorock/wrench", "github", "https://github.com/Ergorock/wrench"),
        (
            "https://user@gitea.example.org/team/app.git",
            "gitea",
            "https://gitea.example.org/team/app",
        ),
        ("ssh://git@git.corp.local:2222/a/b.git", "other", "https://git.corp.local/a/b"),
        ("C:/repos/bare.git", "other", None),
        ("file:///C:/x", "other", None),
        (None, "none", None),
        ("", "none", None),
    ],
)
def test_host_and_web(url: str | None, kind: str, web: str | None) -> None:
    assert host_kind(url) == kind
    assert web_url(url) == web


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://github.com/Ergorock/wrench.git", True),
        ("https://gitea.example.org:8443/team/app", True),
        ("ssh://git@git.corp.local:2222/a/b.git", True),
        ("ssh://host/a/b", True),
        ("git@github.com:Ergorock/wrench.git", True),
        ("", False),
        ("https://github.com", False),
        ("https://github.com/", False),
        ("ssh://git@host", False),
        ("git@github.com:", False),
        ("https://git hub.com/a/b", False),
        ("https://github.com/a/b c", False),
        ("https://github.com/a/b\n", False),
        ("https://github.com/a\x00b", False),
        ("--upload-pack=x", False),
        ("-ugit@host:a/b", False),
        ("ftp://host/a/b", False),
        ("C:/repos/bare.git", False),
        ("/srv/git/repo.git", False),
        ("https://host:notaport/a/b", False),
    ],
)
def test_is_remote_url(url: str, ok: bool) -> None:
    assert is_remote_url(url) is ok
