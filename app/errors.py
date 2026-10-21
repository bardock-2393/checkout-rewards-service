from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "ERROR"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ValidationError(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class CartAlreadyCheckedOutError(AppError):
    status_code = 409
    code = "CART_ALREADY_CHECKED_OUT"


class OutOfStockError(AppError):
    status_code = 409
    code = "OUT_OF_STOCK"


class InvalidCouponError(AppError):
    status_code = 400
    code = "INVALID_COUPON"


class CouponAlreadyRedeemedError(AppError):
    status_code = 409
    code = "COUPON_ALREADY_REDEEMED"


class MilestoneNotReachedError(AppError):
    status_code = 409
    code = "MILESTONE_NOT_REACHED"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message},
        )
