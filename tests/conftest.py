"""Keep the test process independent from local private configuration."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


# This file is loaded before test modules import rivalradar.config. Disable .env
# discovery and replace the only required endpoint identifier with a public dummy.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for name in (
    "ARK_API_KEY",
    "TAVILY_API_KEY",
    "EXA_API_KEY",
    "DATABASE_URL",
    "RIVALRADAR_DB",
    "RIVALRADAR_RUN_BUDGET_S",
):
    os.environ.pop(name, None)

os.environ["ARK_BASE_URL"] = "https://example.invalid/v1"
os.environ["DOUBAO_MODEL"] = "ep-test-dummy-placeholder"
os.environ["RIVALRADAR_DB"] = os.environ.get("RIVALRADAR_TEST_DB") or str(
    Path(tempfile.gettempdir()) / f"rivalradar-pytest-{os.getpid()}.db"
)
