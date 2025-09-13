#!/usr/bin/env bash
uvicorn functions.main:fastapi_app --host 0.0.0.0 --port $PORT