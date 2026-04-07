"""Gmail label management endpoints: list, create, rename, delete."""

from fastapi import APIRouter, HTTPException
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field

import config
import gmail_client

log = config.get_logger(__name__)

router = APIRouter(prefix="/labels", tags=["labels"])


def _require_auth():
    if not gmail_client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class LabelUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@router.get("/", summary="List user-created Gmail labels")
async def list_labels():
    _require_auth()
    service = gmail_client.build_gmail_service()
    labels = gmail_client.get_labels(service)
    return [lbl for lbl in labels if lbl.get("type") == "user"]


@router.post("/", summary="Create a new Gmail label")
async def create_label(body: LabelCreate):
    _require_auth()
    service = gmail_client.build_gmail_service()
    try:
        label = gmail_client.create_label(service, body.name.strip())
        log.info("Created Gmail label: %s (id=%s)", label["name"], label["id"])
        return label
    except HttpError as e:
        if e.resp.status == 409:
            raise HTTPException(status_code=409, detail=f"Label '{body.name}' already exists")
        raise HTTPException(status_code=e.resp.status, detail=str(e))


@router.put("/{label_id}", summary="Rename a Gmail label")
async def update_label(label_id: str, body: LabelUpdate):
    _require_auth()
    service = gmail_client.build_gmail_service()
    try:
        label = gmail_client.update_label(service, label_id, body.name.strip())
        log.info("Renamed Gmail label %s -> %s", label_id, label["name"])
        return label
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="Label not found")
        if e.resp.status == 409:
            raise HTTPException(status_code=409, detail=f"Label '{body.name}' already exists")
        raise HTTPException(status_code=e.resp.status, detail=str(e))


@router.delete("/{label_id}", summary="Delete a Gmail label")
async def delete_label(label_id: str):
    _require_auth()
    service = gmail_client.build_gmail_service()
    try:
        gmail_client.delete_label(service, label_id)
        log.info("Deleted Gmail label: %s", label_id)
        return {"deleted": True, "id": label_id}
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="Label not found")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
