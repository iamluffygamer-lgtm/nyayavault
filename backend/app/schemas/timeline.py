from datetime import datetime
from pydantic import BaseModel

class TimelineEvent(BaseModel):
    id: str
    timestamp: datetime
    actor_name: str
    action: str
    summary: str
    icon_hint: str
