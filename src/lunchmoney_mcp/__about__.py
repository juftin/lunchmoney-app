"""Package metadata exposed without importing the application stack.

``__application__`` identifies the distribution and ``__version__`` exposes
its installed version.
"""

from importlib.metadata import version

__application__ = "lunchmoney-mcp"

__version__ = version(__application__)
