from pydantic import BaseModel


class FlagResponse(BaseModel):
    """Returned after successfully flagging a report."""
    report_id: int
    flag_count: int
    hidden: bool  # True if the report was auto-hidden (flag_count >= 3)
