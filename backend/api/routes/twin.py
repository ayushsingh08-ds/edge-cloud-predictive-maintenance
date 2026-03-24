"""Digital twin state endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from services.digital_twin import twin_repository


router = APIRouter(prefix="/twin", tags=["twin"])


@router.get("/state")
def get_twin_state() -> dict:
    return twin_repository.get_full_twin_state()


@router.get("/machines")
def get_twin_machines() -> dict:
    state = twin_repository.get_full_twin_state()
    return state.get("machines", {})


@router.get("/products")
def get_twin_products() -> dict:
    state = twin_repository.get_full_twin_state()
    return state.get("products", {})
