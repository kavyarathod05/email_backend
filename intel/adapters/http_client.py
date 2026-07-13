"""Shared async HTTP helper for ATS providers."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("internship_platform.http")

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
USER_AGENT = "InternshipLinkIntel/0.1 (+local; ATS board poller)"


async def get_json(url: str, *, params: dict | None = None) -> dict | list | None:
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    ) as client:
        resp = await client.get(url, params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def post_json(url: str, *, json_body: dict | None = None) -> dict | list | None:
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        follow_redirects=True,
    ) as client:
        resp = await client.post(url, json=json_body or {})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def head_ok(url: str) -> bool:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=8.0),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.head(url)
            if resp.status_code in (405, 403, 401):
                resp = await client.get(url)
            return 200 <= resp.status_code < 400
    except Exception as e:
        logger.debug("link check failed url=%s err=%s", url, e)
        return False
