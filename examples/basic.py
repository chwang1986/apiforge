"""Basic example: expose simple tool APIs with ApiForge."""

from src.server import ApiForge

forge = ApiForge(
    name="MyToolService",
    description="A demo API tool service built with ApiForge",
)


@forge.tool
def echo(message: str) -> str:
    """Echo the input message back.

    Args:
        message: The text to echo.

    Returns:
        The same message.
    """
    return message


@forge.tool
def add(a: float, b: float) -> float:
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    return a + b


@forge.tool
def reverse(text: str) -> str:
    """Reverse a string.

    Args:
        text: The string to reverse.

    Returns:
        The reversed string.
    """
    return text[::-1]


if __name__ == "__main__":
    forge.run(host="0.0.0.0", port=8000, reload=False)
