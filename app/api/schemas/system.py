from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class FeatureCapabilityResponse(BaseModel):
    enabled: bool
    maturity: str
    status: str
    production_blocking: bool


class SystemStatusResponse(BaseModel):
    application_status: Literal["ok"]
    application_name: str
    environment: str
    api_version: str
    feature_capabilities: dict[str, FeatureCapabilityResponse]


class SystemVersionResponse(BaseModel):
    application_name: str
    api_version: str
    application_version: str
    environment: str
