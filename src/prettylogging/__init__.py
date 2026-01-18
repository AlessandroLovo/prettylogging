from .core import *


# version helper
try:
    # print("Fetching version info...")
    from importlib.metadata import version, PackageNotFoundError
    try:
        __version__ = version("prettylogging")
    except PackageNotFoundError:
        __version__ = "0.0.0"
except Exception:
    __version__ = "0.0.0"
