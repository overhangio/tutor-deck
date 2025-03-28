import typing as t

from tutordeck.server import constants


def pagination_context(
    plugins: list[dict[str, str]], current_page: int
) -> dict[str, t.Any]:
    total_pages = (
        len(plugins) + constants.ITEMS_PER_PAGE - 1
    ) // constants.ITEMS_PER_PAGE
    return {
        "current_page": current_page,
        "total_pages": total_pages,
        "previous_page": current_page - 1 if current_page > 1 else None,
        "next_page": current_page + 1 if current_page < total_pages else None,
    }


def current_page_plugins(
    plugins: list[dict[str, str]], current_page: int
) -> list[dict[str, str]]:
    start_index = (current_page - 1) * constants.ITEMS_PER_PAGE
    end_index = start_index + constants.ITEMS_PER_PAGE
    return plugins[start_index:end_index]
