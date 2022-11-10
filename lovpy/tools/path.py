import pathlib


def is_relative_to(relative: pathlib.Path, base: pathlib.Path) -> bool:
    """Checks whether a path is relative to another path.

    In python versions >= 3.9 `is_relative_to()` function has been added to pathlib.
    However, in order to support older versions of python, this alternative
    implementation is provided.

    :param relative: The path that will be checked against the base path.
    :param base: The base path.

    returns: True if `relative` is relative to `base`, otherwise False.
    """
    return str(relative).startswith(str(base))
