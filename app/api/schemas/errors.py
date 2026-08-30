from pydantic import BaseModel, Field


class APIErrorDetail(BaseModel):
    code: str = Field(examples=["INTERNAL_ERROR"])
    message: str = Field(examples=["An unexpected error occurred."])
    request_id: str


class APIErrorResponse(BaseModel):
    error: APIErrorDetail
