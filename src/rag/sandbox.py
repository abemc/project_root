
# src/rag/sandbox.py
"""Secure sandbox for executing dynamically generated Python code.

The sandbox uses the `RestrictedPython` library to compile and execute code in a
restricted environment. Only a whitelist of built‑ins and modules is exposed.
The execution result (stdout) is returned as a string; any exception is caught
and reported.

Usage:
    from src.rag.sandbox import Sandbox
    sandbox = Sandbox()
    output = sandbox.execute("print('hello')")
"""

import builtins
import io
import contextlib
from types import SimpleNamespace

# RestrictedPython imports – will be available in the runtime environment.
# If the library is not installed, the import will raise at import time.
from RestrictedPython import compile_restricted
from RestrictedPython import safe_globals, utility_builtins

class SandboxExecutionError(RuntimeError):
    """Custom exception for sandbox execution failures."""
    pass

class Sandbox:
    """A lightweight sandbox based on RestrictedPython.

    The sandbox permits only a limited set of built‑ins and a whitelist of
    external modules (`pandas`, `numpy`). Access to `os`, `sys`, `subprocess`,
    `open` etc. is blocked.
    """

    def __init__(self):
        # Base safe globals from RestrictedPython
        self._globals = safe_globals.copy()
        # Add utility builtins (e.g., `enumerate`, `range`)
        self._globals.update(utility_builtins)
        # Whitelisted modules – they will be injected as globals.
        self._allowed_modules = {
            "pd": __import__("pandas"),
            "np": __import__("numpy"),
        }
        self._globals.update(self._allowed_modules)
        # Remove potentially unsafe built‑ins.
        for unsafe in ["open", "eval", "exec", "compile", "__import__", "input", "globals", "locals", "vars"]:
            self._globals.pop(unsafe, None)

    def execute(self, code: str) -> str:
        """Execute *code* in the restricted environment.

        Returns the captured stdout. If an exception occurs, a descriptive
        string is returned instead of propagating the exception.
        """
        # Compile the code with RestrictedPython
        try:
            byte_code = compile_restricted(code, filename="<sandbox>", mode="exec")
        except Exception as e:
            raise SandboxExecutionError(f"Compilation failed: {e}")

        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                # Execute the compiled code.
                exec(byte_code, self._globals, {})
        except Exception as e:
            # Return the error as a string – the caller can decide how to handle.
            return f"実行エラー: {e}"
        # Return captured output (may be empty).
        return stdout.getvalue()
