from pydantic import BaseModel


class ForecastOut(BaseModel):
    predicted_total_month_spend: float
    predicted_remaining_spend: float
    target_budget: float
    projected_overspend: float
    risk: str
    method: str


class VelocityOut(BaseModel):
    current_velocity: float
    required_velocity: float
    deviation_pct: float
    label: str
