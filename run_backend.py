"""Pornește backend-ul: python run_backend.py"""
import asyncio

import uvicorn

import common as common  # noqa: F401  (setează event loop-ul corect pe Windows)

if __name__ == "__main__":
    config = uvicorn.Config("backend_main:app", host="127.0.0.1", port=8000, log_level="info")
    try:
        asyncio.run(uvicorn.Server(config).serve())
    except KeyboardInterrupt:
        pass
