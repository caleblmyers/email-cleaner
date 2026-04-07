"""Category management endpoints: list, create, update, delete."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

import config
import database

log = config.get_logger(__name__)

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(default="")
    color: str = Field(default="#718096")


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: Optional[str] = Field(default=None)
    color: Optional[str] = Field(default=None)


class ItemAction(BaseModel):
    item: str = Field(min_length=1)


@router.get("/", summary="List all categories")
async def list_categories():
    conn = database.get_connection()
    try:
        return database.get_categories(conn)
    finally:
        conn.close()


@router.post("/", summary="Create a new category")
async def create_category(body: CategoryCreate):
    conn = database.get_connection()
    try:
        existing = database.get_category_names(conn)
        if body.name.strip() in existing:
            raise HTTPException(status_code=409, detail=f"Category '{body.name}' already exists")
        cat = database.create_category(conn, body.name, body.description, body.color)
        log.info("Created category: %s", body.name)
        return cat
    finally:
        conn.close()


@router.put("/{category_id}", summary="Update a category")
async def update_category(category_id: int, body: CategoryUpdate):
    conn = database.get_connection()
    try:
        if body.name is not None:
            existing = conn.execute(
                "SELECT id FROM categories WHERE name = ? AND id != ?",
                (body.name.strip(), category_id),
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail=f"Category '{body.name}' already exists")

        old = conn.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="Category not found")

        fields = body.model_dump(exclude_none=True)
        if fields:
            database.update_category(conn, category_id, **{k: v.strip() if isinstance(v, str) else v for k, v in fields.items()})

        if body.name is not None and body.name.strip() != old["name"]:
            conn.execute("UPDATE emails SET category = ? WHERE category = ?", (body.name.strip(), old["name"]))
            conn.commit()
            log.info("Renamed category '%s' -> '%s'", old["name"], body.name)

        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@router.delete("/{category_id}", summary="Delete a category")
async def delete_category(category_id: int):
    conn = database.get_connection()
    try:
        row = conn.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Category not found")
        if row["name"] == "Uncategorized":
            raise HTTPException(status_code=400, detail="Cannot delete the 'Uncategorized' category")

        database.delete_category(conn, category_id)
        log.info("Deleted category: %s", row["name"])
        return {"deleted": True, "name": row["name"]}
    finally:
        conn.close()


@router.put("/{category_id}/add-item", summary="Add a descriptor item")
async def add_item(category_id: int, body: ItemAction):
    conn = database.get_connection()
    try:
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Category not found")
        cat = dict(row)
        items = [s.strip() for s in cat["description"].split(",") if s.strip()] if cat["description"] else []
        new_item = body.item.strip()
        if new_item and new_item not in items:
            items.append(new_item)
        database.update_category(conn, category_id, description=", ".join(items))
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.put("/{category_id}/remove-item", summary="Remove a descriptor item")
async def remove_item(category_id: int, body: ItemAction):
    conn = database.get_connection()
    try:
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Category not found")
        cat = dict(row)
        items = [s.strip() for s in cat["description"].split(",") if s.strip()] if cat["description"] else []
        items = [i for i in items if i != body.item.strip()]
        database.update_category(conn, category_id, description=", ".join(items))
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()
