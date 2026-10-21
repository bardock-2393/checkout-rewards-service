import uuid

from app.domain import Coupon, CouponStatus
from app.errors import CouponAlreadyRedeemedError, InvalidCouponError, MilestoneNotReachedError
from app.store import InMemoryStore


def discount_for(subtotal_paise: int, percent_off: int) -> int:
    """Floor-rounded so a discount never exceeds the subtotal or goes negative."""
    return (subtotal_paise * percent_off) // 100


async def generate_coupon(store: InMemoryStore) -> Coupon:
    """
    Admin-triggered. At most one coupon is issued per call, for the highest
    milestone reached so far that hasn't already been rewarded - if the
    admin is late to call this, a backlog of skipped milestones does not
    flood out multiple coupons at once.
    """
    async with store.global_lock:
        eligible_milestone = store.successful_order_count // store.coupon_every_n_orders
        if eligible_milestone <= store.last_rewarded_milestone:
            raise MilestoneNotReachedError(
                f"next coupon unlocks after order {(store.last_rewarded_milestone + 1) * store.coupon_every_n_orders}"
            )

        coupon = Coupon(
            code=uuid.uuid4().hex[:8].upper(),
            percent_off=store.coupon_percent_off,
            milestone=eligible_milestone,
        )
        store.coupons[coupon.code] = coupon
        store.last_rewarded_milestone = eligible_milestone
        return coupon


def validate_coupon(store: InMemoryStore, code: str) -> Coupon:
    """Caller must already hold store.global_lock."""
    coupon = store.coupons.get(code)
    if coupon is None:
        raise InvalidCouponError(f"coupon {code} does not exist")
    if coupon.status is not CouponStatus.AVAILABLE:
        raise CouponAlreadyRedeemedError(f"coupon {code} has already been redeemed")
    return coupon


def redeem(coupon: Coupon) -> None:
    """Caller must already hold store.global_lock and have committed the order."""
    coupon.status = CouponStatus.REDEEMED
