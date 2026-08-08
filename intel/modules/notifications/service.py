"""Dedupe-safe notifications for NEW internship links (ranked digest)."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from pymongo.errors import DuplicateKeyError

from intel.config import get_settings
from intel.modules.jobs.repository import JobRepository, notifications_col
from intel.modules.matching.ranker import rank_jobs, score_job

logger = logging.getLogger("internship_platform.notify")


def _dedupe_key(channel: str, job_id: str, event: str = "new") -> str:
    return hashlib.sha256(f"{channel}:{job_id}:{event}".encode()).hexdigest()


class NotificationService:
    def __init__(self, jobs: JobRepository | None = None):
        self.jobs = jobs or JobRepository()

    def _channels(self) -> list[tuple[str, str | None]]:
        s = get_settings()
        channels: list[tuple[str, str | None]] = [("dashboard", None)]
        if s.telegram_bot_token and s.telegram_chat_id:
            channels.append(("telegram", None))
        if s.discord_webhook_url:
            channels.append(("discord", s.discord_webhook_url))
        if s.slack_webhook_url:
            channels.append(("slack", s.slack_webhook_url))
        return channels

    async def notify_new_jobs(self, *, require_link_ok: bool = True) -> int:
        """Notify for filter_pass open jobs not yet notified, highest preference first."""
        filt: dict[str, Any] = {
            "filter_pass": True,
            "status": "open",
        }
        if require_link_ok:
            filt["link_ok"] = True

        cursor = self.jobs.col.find(filt).sort("first_seen_at", -1).limit(200)
        docs = list(cursor)
        ranked = rank_jobs(docs)
        sent = 0
        for doc, rank in ranked:
            job_id = str(doc["_id"])
            # Persist soft rank for dashboard / digests
            try:
                self.jobs.col.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "match_score": rank.score,
                            "match_reasons": rank.reasons,
                        }
                    },
                )
            except Exception:
                pass
            lines = self._format(doc, rank.score, rank.reasons)
            for channel, webhook in self._channels():
                key = _dedupe_key(channel, job_id)
                try:
                    notifications_col().insert_one(
                        {
                            "dedupe_key": key,
                            "channel": channel,
                            "job_id": job_id,
                            "payload": {
                                "title": doc["title"],
                                "company": doc["company_name"],
                                "apply_url": doc["apply_url"],
                                "match_score": rank.score,
                                "match_reasons": rank.reasons,
                            },
                            "sent_at": datetime.now(timezone.utc),
                            "status": "pending",
                        }
                    )
                except DuplicateKeyError:
                    continue

                ok = await self._dispatch(channel, webhook, lines, doc)
                notifications_col().update_one(
                    {"dedupe_key": key},
                    {"$set": {"status": "sent" if ok else "failed"}},
                )
                if ok and channel != "dashboard":
                    sent += 1
                elif channel == "dashboard":
                    sent += 1
        return sent

    def build_ranked_digest(
        self,
        *,
        limit: int = 25,
        require_link_ok: bool = False,
    ) -> list[dict[str, Any]]:
        """Return ranked filter_pass jobs as digest payload (email / dashboard)."""
        filt: dict[str, Any] = {"filter_pass": True, "status": "open"}
        if require_link_ok:
            filt["link_ok"] = True
        docs = list(self.jobs.col.find(filt).sort("first_seen_at", -1).limit(200))
        ranked = rank_jobs(docs)[:limit]
        out: list[dict[str, Any]] = []
        for doc, rank in ranked:
            out.append(
                {
                    "id": str(doc["_id"]),
                    "company": doc["company_name"],
                    "title": doc["title"],
                    "apply_url": doc["apply_url"],
                    "location": doc.get("location_text"),
                    "role_family": doc.get("role_family"),
                    "match_score": rank.score,
                    "why_matched": rank.reasons,
                    "filter_reasons": doc.get("filter_reasons") or [],
                }
            )
        return out

    def _format(
        self,
        doc: dict[str, Any],
        score: float | None = None,
        reasons: list[str] | None = None,
    ) -> str:
        tags = []
        if doc.get("is_india"):
            tags.append("India")
        if doc.get("is_remote"):
            tags.append("Remote")
        if doc.get("grad_year_eligibility") == "2028":
            tags.append("2028")
        if doc.get("season_tag") == "summer_2027":
            tags.append("Summer2027")
        if score is None:
            rank = score_job(doc)
            score, reasons = rank.score, rank.reasons
        tags.append(f"score {score:.0f}")
        tag_s = f" [{', '.join(tags)}]" if tags else ""
        why = ""
        if reasons:
            why = "\nWhy: " + "; ".join(reasons[:3])
        return (
            f"🆕 {doc['company_name']} — {doc['title']}{tag_s}\n"
            f"{doc['apply_url']}{why}"
        )

    async def _dispatch(
        self,
        channel: str,
        webhook: str | None,
        text: str,
        doc: dict[str, Any],
    ) -> bool:
        if channel == "dashboard":
            return True
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if channel == "discord" and webhook:
                    await client.post(webhook, json={"content": text[:1900]})
                    return True
                if channel == "slack" and webhook:
                    await client.post(webhook, json={"text": text})
                    return True
                if channel == "telegram":
                    s = get_settings()
                    url = f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage"
                    await client.post(
                        url,
                        json={"chat_id": s.telegram_chat_id, "text": text},
                    )
                    return True
        except Exception as e:
            logger.warning("Notify failed channel=%s err=%s", channel, e)
            return False
        return False
