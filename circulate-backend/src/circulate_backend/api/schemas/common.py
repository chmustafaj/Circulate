from typing import Annotated

from pydantic import BaseModel, Field, StrictInt

# All financial values must be StrictInt cents (floats rejected by validation).
Cents = Annotated[StrictInt, Field(description="Amount in integer cents", examples=[1050])]


class HealthResponse(BaseModel):
    status: str

