def reverse_string(text: str) -> str:
    """
    与えられた文字列を逆順にして返します。
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    return text[::-1]
