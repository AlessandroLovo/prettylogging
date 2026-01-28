from .core import FileLogger as FileLogger
from .core import TelegramLogger as TelegramLogger
from .core import exec_time as exec_time
from .core import indent_logger as indent_logger
from .core import now as now
from .core import pretty_time as pretty_time

# TODO: add more exports if needed

# version helper
try:
    # print("Fetching version info...")
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("prettylogging")
    except PackageNotFoundError:
        __version__ = "0.0.0"
except Exception:
    __version__ = "0.0.0"
