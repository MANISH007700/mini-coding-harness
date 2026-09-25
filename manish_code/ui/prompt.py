"""The input line.

`input()` cannot edit a line that has wrapped past the screen width - the
terminal owns the wrapping and readline cannot see it. prompt_toolkit redraws
the line itself, so deleting, word jumps and history all keep working once the
text is longer than the screen.
"""

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from manish_code import config

HISTORY = config.HOME / "history"

STYLE = Style.from_dict({"prompt": "bold ansimagenta"})

bindings = KeyBindings()


# macOS sends option-arrow as escape then arrow. Terminals configured to send
# option as meta emit alt-b / alt-f instead, which prompt_toolkit binds itself.
@bindings.add("escape", "left")
def _word_left(event):
    document = event.current_buffer.document
    event.current_buffer.cursor_position += (
        document.find_previous_word_beginning(count=1) or 0
    )


@bindings.add("escape", "right")
def _word_right(event):
    document = event.current_buffer.document
    event.current_buffer.cursor_position += (
        document.find_next_word_ending(count=1) or 0
    )


@bindings.add("escape", "enter")
def _newline(event):
    """Option-enter starts a new line instead of sending the message."""
    event.current_buffer.insert_text("\n")


SESSION = None


def read(prompt="❯ "):
    """Read one message. Raises EOFError on ctrl-d, like input() does."""
    global SESSION
    if SESSION is None:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        SESSION = PromptSession(
            history=FileHistory(str(HISTORY)),
            key_bindings=bindings,
            style=STYLE,
        )
    return SESSION.prompt(HTML(f"<prompt>{prompt}</prompt>"))
