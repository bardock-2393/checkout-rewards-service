from fastapi import APIRouter, Request

from app.models import AddItemRequest, UpdateItemRequest
from app.services import cart_service

router = APIRouter(prefix="/carts", tags=["carts"])


@router.post("")
def create_cart(request: Request):
    store = request.app.state.store
    cart = cart_service.create_cart(store)
    return {"cart_id": cart.id}


@router.get("/{cart_id}")
def view_cart(cart_id: str, request: Request):
    store = request.app.state.store
    return cart_service.view_cart(store, cart_id)


@router.post("/{cart_id}/items")
def add_item(cart_id: str, body: AddItemRequest, request: Request):
    store = request.app.state.store
    cart_service.add_item(store, cart_id, body.product_id, body.quantity)
    return cart_service.view_cart(store, cart_id)


@router.patch("/{cart_id}/items/{product_id}")
def update_item(cart_id: str, product_id: str, body: UpdateItemRequest, request: Request):
    store = request.app.state.store
    cart_service.update_item(store, cart_id, product_id, body.quantity)
    return cart_service.view_cart(store, cart_id)


@router.delete("/{cart_id}/items/{product_id}")
def remove_item(cart_id: str, product_id: str, request: Request):
    store = request.app.state.store
    cart_service.remove_item(store, cart_id, product_id)
    return cart_service.view_cart(store, cart_id)
