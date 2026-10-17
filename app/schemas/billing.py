from pydantic import BaseModel


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    stripe_customer_id: str
