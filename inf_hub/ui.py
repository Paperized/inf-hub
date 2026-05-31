import getpass
from typing import Sequence

try:
    import questionary

    HAS_QUESTIONARY = True
except Exception:
    HAS_QUESTIONARY = False

from inf_hub.errors import InteractiveAbort


def print_line(message: str) -> None:
    print(message)


def print_table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(title=title)
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*row)
        Console().print(table)
        return
    except Exception:
        pass

    print(title)
    print(" | ".join(columns))
    for row in rows:
        print(" | ".join(row))


def select(message: str, choices: Sequence[str]) -> str:
    if HAS_QUESTIONARY:
        result = questionary.select(message, choices=list(choices)).ask(kbi_msg="")
        if result is None:
            raise InteractiveAbort("Operation cancelled")
        return result
    print(message)
    for idx, choice in enumerate(choices, 1):
        print(f"{idx}. {choice}")
    raw = input("Select number: ").strip()
    if not raw.isdigit():
        raise InteractiveAbort("Operation cancelled")
    pos = int(raw) - 1
    if pos < 0 or pos >= len(choices):
        raise InteractiveAbort("Operation cancelled")
    return list(choices)[pos]


def autocomplete_choice(message: str, choices: Sequence[str]) -> str:
    if HAS_QUESTIONARY:
        result = questionary.select(message, choices=list(choices)).ask(kbi_msg="")
        if result is None:
            raise InteractiveAbort("Operation cancelled")
        return result
    return select(message, choices)


def prompt(label: str, secret: bool = False, default: str | None = None) -> str:
    if HAS_QUESTIONARY:
        if secret:
            value = questionary.password(label).ask(kbi_msg="")
            if value is None:
                raise InteractiveAbort("Operation cancelled")
            return (value or "").strip()
        value = questionary.text(label, default=default or "").ask(kbi_msg="")
        if value is None:
            raise InteractiveAbort("Operation cancelled")
        return (value or "").strip() or (default or "")

    suffix = f" [{default}]" if default else ""
    if secret:
        value = getpass.getpass(f"{label}{suffix}: ")
    else:
        value = input(f"{label}{suffix}: ")
    value = value.strip()
    return value if value else (default or "")


def confirm(message: str) -> bool:
    if HAS_QUESTIONARY:
        result = questionary.confirm(message, default=False).ask(kbi_msg="")
        if result is None:
            raise InteractiveAbort("Operation cancelled")
        return bool(result)
    return input(f"{message} [y/N]: ").lower() in ("y", "yes")
