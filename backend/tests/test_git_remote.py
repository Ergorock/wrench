import pytest

from wrench.shared.git.remote import host_kind, web_url


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
