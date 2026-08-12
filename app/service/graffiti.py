"""Service graffiti — 涂鸦墙 API"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/graffiti")

GRAFFITI_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "graffiti",
)


class GraffitiPayload(BaseModel):
    content: str


@router.get("")
async def get_graffiti():
    os.makedirs(GRAFFITI_DIR, exist_ok=True)
    f = os.path.join(GRAFFITI_DIR, "latest.json")
    if not os.path.exists(f):
        return {"content": ""}
    with open(f, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    return {"content": data.get("content", "")}


@router.post("")
async def post_graffiti(payload: GraffitiPayload):
    os.makedirs(GRAFFITI_DIR, exist_ok=True)
    f = os.path.join(GRAFFITI_DIR, "latest.json")
    with open(f, "w", encoding="utf-8") as fp:
        json.dump({"content": payload.content}, fp, ensure_ascii=False)
    return {"success": True}
