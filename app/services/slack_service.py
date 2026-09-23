import os
import logging
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class SlackService:
    @staticmethod
    def get_active_token() -> str:
        # Check live environment and settings
        return (
            os.getenv("SLACK_BOT_TOKEN")
            or os.getenv("SLACK_ACCESS_TOKEN")
            or settings.SLACK_BOT_TOKEN
            or settings.SLACK_ACCESS_TOKEN
            or ""
        )

    @staticmethod
    def get_default_channel() -> str:
        return os.getenv("SLACK_CHANNEL_ID") or settings.SLACK_CHANNEL_ID or ""

    @staticmethod
    async def post_message(
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Posts a rich message or Block Kit card to the specified Slack channel.
        Supports Webhook URL if no token is present.
        """
        token = SlackService.get_active_token()
        channel_id = channel or SlackService.get_default_channel()
        webhook_url = settings.SLACK_WEBHOOK_URL

        # 1. Try Token-based Web API
        if token and channel_id:
            payload: Dict[str, Any] = {
                "channel": channel_id,
                "text": text,
            }
            if blocks:
                payload["blocks"] = blocks

            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=payload,
                )
                data = res.json()
                if not data.get("ok"):
                    logger.error(f"Slack chat.postMessage failed: {data.get('error')}")
                    # If error is expired token and refresh token exists, attempt refresh
                    if data.get("error") in ("token_expired", "invalid_auth") and settings.SLACK_REFRESH_TOKEN:
                        refreshed = await SlackService.refresh_access_token()
                        if refreshed:
                            # Retry once with refreshed token
                            new_token = SlackService.get_active_token()
                            res = await client.post(
                                "https://slack.com/api/chat.postMessage",
                                headers={"Authorization": f"Bearer {new_token}", "Content-Type": "application/json"},
                                json=payload,
                            )
                            return res.json()
                    return {"ok": False, "error": data.get("error")}
                return data

        # 2. Try Webhook fallback
        if webhook_url:
            payload = {"text": text}
            if blocks:
                payload["blocks"] = blocks

            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(webhook_url, json=payload)
                if res.status_code == 200:
                    return {"ok": True, "method": "webhook"}
                return {"ok": False, "error": f"Webhook returned status {res.status_code}"}

        return {"ok": False, "error": "No Slack credentials configured in .env"}

    @staticmethod
    async def upload_file(
        file_bytes: bytes,
        filename: str,
        title: str,
        initial_comment: str = "",
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Uploads a file (such as .xlsx or .csv) to the designated Slack channel.
        First tries legacy files.upload; if deprecated/rejected, uses files.getUploadURLExternal flow.
        """
        token = SlackService.get_active_token()
        channel_id = channel or SlackService.get_default_channel()

        if not token or not channel_id:
            return {"ok": False, "error": "Missing SLACK_ACCESS_TOKEN or SLACK_CHANNEL_ID in .env"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Try modern files.upload_v2 flow (getUploadURLExternal -> upload -> completeUploadExternal)
            try:
                # Step A: Request Upload URL
                get_url_res = await client.get(
                    "https://slack.com/api/files.getUploadURLExternal",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"filename": filename, "length": len(file_bytes)},
                )
                url_data = get_url_res.json()
                if url_data.get("ok"):
                    upload_url = url_data["upload_url"]
                    file_id = url_data["file_id"]

                    # Step B: Upload file content to AWS/Slack upload URL
                    upload_res = await client.post(upload_url, content=file_bytes)
                    if upload_res.status_code == 200:
                        # Step C: Complete upload and share to channel
                        complete_res = await client.post(
                            "https://slack.com/api/files.completeUploadExternal",
                            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                            json={
                                "files": [{"id": file_id, "title": title}],
                                "channel_id": channel_id,
                                "initial_comment": initial_comment,
                            },
                        )
                        complete_data = complete_res.json()
                        if complete_data.get("ok"):
                            return complete_data
                        logger.warning(f"completeUploadExternal failed: {complete_data.get('error')}")
            except Exception as e:
                logger.warning(f"files.upload_v2 flow encountered exception: {e}")

            # 2. Fallback to classic files.upload endpoint
            try:
                legacy_res = await client.post(
                    "https://slack.com/api/files.upload",
                    headers={"Authorization": f"Bearer {token}"},
                    data={
                        "channels": channel_id,
                        "title": title,
                        "initial_comment": initial_comment,
                        "filename": filename,
                    },
                    files={"file": (filename, file_bytes, "application/octet-stream")},
                )
                legacy_data = legacy_res.json()
                if legacy_data.get("ok"):
                    return legacy_data
                logger.error(f"files.upload fallback also returned error: {legacy_data.get('error')}")
                return legacy_data
            except Exception as e:
                logger.error(f"files.upload error: {e}")
                return {"ok": False, "error": str(e)}

    @staticmethod
    async def refresh_access_token() -> bool:
        """
        Exchanges SLACK_REFRESH_TOKEN for a new SLACK_ACCESS_TOKEN if configured.
        """
        # Note: Slack OAuth token refresh requires client_id/client_secret or app configuration token
        logger.info("Attempting Slack token refresh...")
        return False
