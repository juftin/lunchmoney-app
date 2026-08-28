"""Package metadata exposed without importing the application stack.

``__application__`` identifies the distribution and ``__version__`` exposes
its installed version.
"""

from importlib.metadata import PackageNotFoundError, version

__application__ = "lunchmoney-app"

try:
    __version__ = version(__application__)
except PackageNotFoundError:
    __version__ = "0.10.2"
