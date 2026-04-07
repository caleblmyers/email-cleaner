"""Category management endpoints: list, create, update, delete."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

import config
import database

log = config.get_logger(__name__)

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="Category name")
    description: str = Field(default="", max_length=500, description="Comma-separated descriptor items")
    color: str = Field(default="#718096", max_length=20, description="CSS color value")


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    color: Optional[str] = Field(default=None, max_length=20)
    sort_order: Optional[int] = Field(default=None, ge=0)


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
        # Check for name conflict
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
        cat = database.update_category(conn, category_id, **fields)

        # If name changed, update emails that reference the old name
        if body.name is not None and body.name.strip() != old["name"]:
            conn.execute(
                "UPDATE emails SET category = ? WHERE category = ?",
                (body.name.strip(), old["name"]),
            )
            conn.commit()
            log.info("Renamed category '%s' -> '%s'", old["name"], body.name)

        return cat
    finally:
        conn.close()


@router.delete("/{category_id}", summary="Delete a category")
async def delete_category(category_id: int):
    conn = database.get_connection()
    try:
        # Prevent deleting Uncategorized
        row = conn.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Category not found")
        if row["name"] == "Uncategorized":
            raise HTTPException(status_code=400, detail="Cannot delete the 'Uncategorized' category")

        deleted = database.delete_category(conn, category_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Category not found")
        log.info("Deleted category: %s (emails reassigned to Uncategorized)", row["name"])
        return {"deleted": True, "name": row["name"]}
    finally:
        conn.close()
