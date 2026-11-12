from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    id: str
    icon: str


CATEGORIES: tuple[Category, ...] = (
    Category("system", "monitor"),
    Category("productivity", "zap"),
    Category("development", "code"),
    Category("files", "folder"),
)


def category_ids() -> list[str]:
    return [c.id for c in CATEGORIES]
