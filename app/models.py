from pydantic import BaseModel, Field


class AddItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class UpdateItemRequest(BaseModel):
    quantity: int = Field(gt=0)


class CheckoutRequest(BaseModel):
    coupon_code: str | None = None
