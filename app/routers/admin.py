from fastapi import APIRouter, Request

from app.services import coupon_service, report_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/coupons/generate")
async def generate_coupon(request: Request):
    store = request.app.state.store
    coupon = await coupon_service.generate_coupon(store)
    return {
        "code": coupon.code,
        "percent_off": coupon.percent_off,
        "milestone": coupon.milestone,
    }


@router.get("/report")
def report(request: Request):
    store = request.app.state.store
    return report_service.build_report(store)
