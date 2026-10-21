from dataclasses import dataclass, field
from enum import Enum


class CartStatus(str, Enum):
    OPEN = "open"
    CHECKED_OUT = "checked_out"


class CouponStatus(str, Enum):
    AVAILABLE = "available"
    REDEEMED = "redeemed"


@dataclass
class Product:
    id: str
    name: str
    price_paise: int
    stock: int


@dataclass
class Cart:
    id: str
    status: CartStatus = CartStatus.OPEN
    items: dict[str, int] = field(default_factory=dict)  # product_id -> quantity
    order_id: str | None = None


@dataclass
class OrderLine:
    product_id: str
    name: str
    unit_price_paise: int
    quantity: int

    @property
    def subtotal_paise(self) -> int:
        return self.unit_price_paise * self.quantity


@dataclass
class Order:
    id: str
    cart_id: str
    lines: list[OrderLine]
    subtotal_paise: int
    discount_paise: int
    total_paise: int
    coupon_code: str | None


@dataclass
class Coupon:
    code: str
    percent_off: int
    milestone: int
    status: CouponStatus = CouponStatus.AVAILABLE
