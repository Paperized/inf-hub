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


def select(message: str, choices: Sequence[str]) -> str:
    if HAS_QUESTIONARY:
        result = questionary.select(message, choices=list(choices)).ask()
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
        result = questionary.autocomplete(
            message,
            choices=list(choices),
            validate=lambda text: text in choices or "Choose a value from autocomplete list",
        ).ask()
        if result is None:
            raise InteractiveAbort("Operation cancelled")
        return result
    while True:
        value = input(f"{message}: ").strip()
        if value in choices:
            return value
        print("Choose a value from the available list.")


def prompt(label: str, secret: bool = False, default: str | None = None) -> str:
    if HAS_QUESTIONARY:
        if secret:
            value = questionary.password(label).ask()
            if value is None:
                raise InteractiveAbort("Operation cancelled")
            return (value or "").strip()
        value = questionary.text(label, default=default or "").ask()
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
        result = questionary.confirm(message, default=False).ask()
        if result is None:
            raise InteractiveAbort("Operation cancelled")
        return bool(result)
    return input(f"{message} [y/N]: ").lower() in ("y", "yes")
