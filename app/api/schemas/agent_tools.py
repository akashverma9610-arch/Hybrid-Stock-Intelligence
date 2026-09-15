"""Small, explicit Agent HTTP projections; never domain or execution models."""
from datetime import UTC, datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.api.schemas.market import BreadthResponse, MarketExtremesResponse, MarketRegimeResponse, SectorResponse
from app.api.schemas.portfolio import PortfolioHoldingResponse, PortfolioResponse

Readiness = Literal["READY", "PARTIAL", "BLOCKED", "NOT_EXPOSED"]
CanonicalSecurity = Annotated[str, Field(pattern=r"^NSE:[A-Z]{2}[A-Z0-9]{9}[0-9]$", max_length=16)]
T = TypeVar("T")


class ToolEnvelope(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")
    status: Readiness
    as_of: datetime | None = None
    data: T | None = None
    evidence_refs: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    authority: Literal["RESEARCH_READ_ONLY"] = "RESEARCH_READ_ONLY"
    actionability: Literal["WATCH_ONLY"] = "WATCH_ONLY"
    execution_status: Literal["NON_EXECUTABLE"] = "NON_EXECUTABLE"


class ToolCapability(BaseModel):
    tool_id: str
    readiness: Readiness
    authority: Literal["RESEARCH_READ_ONLY"] = "RESEARCH_READ_ONLY"
    supported_scope: str
    blockers: tuple[str, ...]
    read_only: Literal[True] = True
    exposed: bool
    description: str


class DiagnosticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    canonical_security_id: CanonicalSecurity
    as_of: AwareDatetime
    temporal_mode: Literal["CURRENT_DESCRIPTIVE", "STRICT_HISTORICAL_PIT"]

    @field_validator("as_of")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class DiagnosticRuleResponse(BaseModel):
    rule_id: int = Field(ge=1, le=61)
    result_id: str
    result: str
    eligibility: str
    evidence_refs: tuple[str, ...]
    observation_refs: tuple[str, ...]


class DiagnosticsResponse(BaseModel):
    canonical_security_id: str
    temporal_mode: Literal["CURRENT_DESCRIPTIVE"] = "CURRENT_DESCRIPTIVE"
    strict_historical_pit: Literal["NOT_READY"] = "NOT_READY"
    completeness: str
    evaluated_count: int
    missing_count: int
    strategy_id: str
    strategy_version: str
    strategy_fingerprint: str
    input_fingerprint: str
    rules: tuple[DiagnosticRuleResponse, ...]


class MarketContextResponse(BaseModel):
    regime: MarketRegimeResponse | None = None
    breadth: BreadthResponse | None = None
    extremes: MarketExtremesResponse | None = None
    sectors: tuple[SectorResponse, ...] = ()


class PortfolioStateResponse(BaseModel):
    snapshot_id: str
    summary: PortfolioResponse
    holdings: tuple[PortfolioHoldingResponse, ...]
