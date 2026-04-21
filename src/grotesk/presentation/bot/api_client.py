from typing import Any

import httpx


class APIClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def register(self, email: str, password: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/auth/register",
                json={"email": email, "password": password},
            )
            response.raise_for_status()
            return response.json()["user_id"]

    async def login(self, email: str, password: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password},
            )
            response.raise_for_status()
            return response.json()["user_id"]

    async def get_balance(self, user_id: str) -> float:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/balance", params={"user_id": user_id})
            response.raise_for_status()
            return response.json()["balance"]

    async def top_up(self, user_id: str, amount: float) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/balance/top-up",
                params={"user_id": user_id},
                json={"amount": amount},
            )
            response.raise_for_status()
            return response.json()["request_id"]

    async def submit_transcription(self, user_id: str, media_asset_id: str, model_id: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/predict/transcription",
                params={"user_id": user_id},
                json={"media_asset_id": media_asset_id, "model_id": model_id},
            )
            response.raise_for_status()
            return response.json()["job_id"]

    async def submit_video_editing(self, user_id: str, media_asset_id: str, model_id: str, prompt_text: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/predict/video-editing",
                params={"user_id": user_id},
                json={"media_asset_id": media_asset_id, "model_id": model_id, "prompt_text": prompt_text},
            )
            response.raise_for_status()
            return response.json()["job_id"]

    async def get_transactions(self, user_id: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/history/transactions", params={"user_id": user_id})
            response.raise_for_status()
            return response.json()

    async def get_requests(self, user_id: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/history/requests", params={"user_id": user_id})
            response.raise_for_status()
            return response.json()
