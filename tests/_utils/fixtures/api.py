"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import asyncio
from typing import Self

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, Response


class TaskAsyncClient:
    _async_client: httpx.AsyncClient

    def __init__(self, app: FastAPI):
        self._async_client = httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        )

    async def __aenter__(self) -> Self:
        await self._async_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._async_client.__aexit__(exc_type, exc_val, exc_tb)

    def get(self, *args, **kwargs) -> asyncio.Task[Response]:
        return asyncio.create_task(self._async_client.get(*args, **kwargs))

    def post(self, *args, **kwargs) -> asyncio.Task[Response]:
        return asyncio.create_task(self._async_client.post(*args, **kwargs))


# @pytest.fixture
# def fast_api(container, config):
#
#     yield app


@pytest.fixture
def client(application):
    with TestClient(application) as client:
        yield client


@pytest.fixture
async def async_client(application):
    async with TaskAsyncClient(application) as c:
        yield c
