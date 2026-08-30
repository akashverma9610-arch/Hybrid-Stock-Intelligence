from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

from app.gates.engine import ExchangeCalendar
from app.portfolio.engine import PortfolioEngine
from app.portfolio.models import CashPosition, Portfolio, PortfolioStatus, PortfolioTransaction, TransactionType
from app.storage.governance_repository import StrategyGovernanceRepository

from .models import (
    ExtractedHoldingCandidate, ImportStatus, PortfolioImportConfirmation,
    PortfolioImportDraft, ReviewedHolding, SymbolResolutionStatus, UploadedScreenshot,
    resolved,
)


class PortfolioImportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PortfolioScreenshotExtractor(Protocol):
    """Provider-neutral, extraction-only adapter. It must not make recommendations."""

    def extract(self, images: tuple[UploadedScreenshot, ...], *, now: datetime) -> tuple[ExtractedHoldingCandidate, ...]: ...


class InstrumentResolver(Protocol):
    def resolve(self, symbol_or_name: str) -> tuple[SymbolResolutionStatus, str | None]: ...


class UnavailablePortfolioScreenshotExtractor:
    def extract(self, images: tuple[UploadedScreenshot, ...], *, now: datetime) -> tuple[ExtractedHoldingCandidate, ...]:
        raise PortfolioImportError("PROVIDER_UNAVAILABLE", "Screenshot extraction is not configured.")


class UnmatchedInstrumentResolver:
    def resolve(self, symbol_or_name: str) -> tuple[SymbolResolutionStatus, str | None]:
        return SymbolResolutionStatus.UNMATCHED, None


class MappingInstrumentResolver:
    """Deterministic resolver suitable for local composition and tests."""

    def __init__(self, mapping: dict[str, str | tuple[SymbolResolutionStatus, str | None]]) -> None:
        self._mapping = {key.upper(): value for key, value in mapping.items()}

    def resolve(self, symbol_or_name: str) -> tuple[SymbolResolutionStatus, str | None]:
        value = self._mapping.get(symbol_or_name.upper())
        if value is None:
            return SymbolResolutionStatus.UNMATCHED, None
        if isinstance(value, tuple):
            return value
        return SymbolResolutionStatus.MATCHED, value


class PortfolioImportPersister(Protocol):
    def persist_replace(self, *, import_id: str, rows: tuple[ReviewedHolding, ...], now: datetime) -> tuple[str, str]: ...


class UnavailablePortfolioImportPersister:
    def persist_replace(self, *, import_id: str, rows: tuple[ReviewedHolding, ...], now: datetime) -> tuple[str, str]:
        raise PortfolioImportError("PORTFOLIO_PERSISTENCE_UNAVAILABLE", "Portfolio persistence is not configured.")


class GovernancePortfolioImportPersister:
    """Uses the canonical append-only portfolio repository, never broker state."""

    def __init__(self, repository: StrategyGovernanceRepository, *, calendar: ExchangeCalendar | None = None) -> None:
        self._repository = repository
        self._engine = PortfolioEngine(calendar or ExchangeCalendar("nse-import", frozenset()))

    def persist_replace(self, *, import_id: str, rows: tuple[ReviewedHolding, ...], now: datetime) -> tuple[str, str]:
        portfolio_id = f"imported-{import_id}"
        portfolio = Portfolio(portfolio_id, "Imported portfolio", "INR", now, None, None, PortfolioStatus.ACTIVE, {"import_id": import_id, "source": "USER_CONFIRMED_SCREENSHOT"})
        self._repository.save_portfolio(portfolio)
        transactions = tuple(
            PortfolioTransaction(
                transaction_id=f"import-{import_id}-{row.row_id}", portfolio_id=portfolio_id,
                transaction_type=TransactionType.ADD, effective_at=now, known_at=now,
                source="USER_CONFIRMED_SCREENSHOT", provenance_reference=f"portfolio-import:{import_id}:{row.row_id}",
                instrument_id=row.instrument_id, quantity=row.quantity, price=row.average_price,
                gross_amount=(row.quantity or Decimal("0")) * (row.average_price or Decimal("0")),
                net_cash_impact=Decimal("0"),
            )
            for row in rows
        )
        for transaction in transactions:
            self._repository.append_portfolio_transaction(transaction)
        snapshot = self._engine.reconstruct(
            portfolio=portfolio, as_of_timestamp=now,
            initial_cash=CashPosition(Decimal("0"), "INR", Decimal("0"), now),
            transactions=transactions, actions=(), prices=(), analytics=(),
        )
        self._repository.save_portfolio_snapshot(snapshot)
        return portfolio_id, snapshot.snapshot_id


class PortfolioImportService:
    """Transient draft lifecycle; raw images and OCR text are never retained."""

    def __init__(self, *, extractor: PortfolioScreenshotExtractor | None = None, resolver: InstrumentResolver | None = None,
                 persister: PortfolioImportPersister | None = None, clock=lambda: datetime.now(UTC), draft_ttl: timedelta = timedelta(minutes=15)) -> None:
        self._extractor = extractor or UnavailablePortfolioScreenshotExtractor()
        self._resolver = resolver or UnmatchedInstrumentResolver()
        self._persister = persister or UnavailablePortfolioImportPersister()
        self._clock = clock
        self._draft_ttl = draft_ttl
        self._drafts: dict[str, PortfolioImportDraft] = {}

    def create_draft(self, images: tuple[UploadedScreenshot, ...]) -> PortfolioImportDraft:
        now = self._clock()
        candidates = self._extractor.extract(images, now=now)
        normalized = tuple(self._resolve(candidate) for candidate in candidates)
        normalized = self._mark_duplicates(normalized)
        warnings = tuple(sorted({warning for candidate in normalized for warning in candidate.field_warnings}))
        if not normalized:
            warnings = tuple(sorted(set(warnings + ("NO_TEXT_DETECTED",))))
        import_id = f"portfolio-import-{uuid4().hex}"
        draft = PortfolioImportDraft(import_id, ImportStatus.DRAFT, now, now + self._draft_ttl, len(images), warnings, normalized)
        self._drafts[import_id] = draft
        return draft

    def get_draft(self, import_id: str) -> PortfolioImportDraft:
        draft = self._drafts.get(import_id)
        if draft is None:
            raise PortfolioImportError("IMPORT_NOT_FOUND", "Screenshot import was not found.")
        return self._expire_if_needed(draft)

    def cancel(self, import_id: str) -> PortfolioImportDraft:
        draft = self.get_draft(import_id)
        if draft.status is not ImportStatus.DRAFT:
            raise PortfolioImportError("IMPORT_NOT_ACTIVE", "Screenshot import is no longer active.")
        cancelled = replace(draft, status=ImportStatus.CANCELLED, holdings=())
        self._drafts[import_id] = cancelled
        return cancelled

    def confirm(self, import_id: str, rows: tuple[ReviewedHolding, ...], *, mode: str) -> PortfolioImportConfirmation:
        draft = self.get_draft(import_id)
        if draft.status is ImportStatus.EXPIRED:
            raise PortfolioImportError("IMPORT_EXPIRED", "Screenshot import has expired.")
        if draft.status is not ImportStatus.DRAFT:
            raise PortfolioImportError("IMPORT_NOT_ACTIVE", "Screenshot import is no longer active.")
        if mode != "REPLACE":
            raise PortfolioImportError("MERGE_UNAVAILABLE", "Merge is not available for screenshot imports; explicitly choose REPLACE.")
        selected = tuple(row for row in rows if row.include)
        if not selected:
            raise PortfolioImportError("VALIDATION_ERROR", "At least one reviewed holding is required.")
        self._validate_rows(draft, selected)
        now = self._clock()
        portfolio_id, snapshot_id = self._persister.persist_replace(import_id=import_id, rows=selected, now=now)
        self._drafts[import_id] = replace(draft, status=ImportStatus.CONFIRMED, holdings=())
        return PortfolioImportConfirmation(ImportStatus.CONFIRMED, portfolio_id, snapshot_id, len(selected),
            ("SCREENSHOT_CURRENT_PRICE_IS_INFORMATIONAL_ONLY", "ANALYSIS_REQUIRES_BACKEND_CYCLE"), now)

    def _expire_if_needed(self, draft: PortfolioImportDraft) -> PortfolioImportDraft:
        if draft.status is ImportStatus.DRAFT and self._clock() >= draft.expires_at:
            draft = replace(draft, status=ImportStatus.EXPIRED, holdings=())
            self._drafts[draft.import_id] = draft
        return draft

    def _resolve(self, candidate: ExtractedHoldingCandidate) -> ExtractedHoldingCandidate:
        query = candidate.symbol or candidate.instrument_name
        if not query:
            return candidate
        status, instrument_id = self._resolver.resolve(query)
        warnings = candidate.field_warnings
        if status is SymbolResolutionStatus.AMBIGUOUS:
            warnings = tuple(sorted(set(warnings + ("AMBIGUOUS_SYMBOL",))))
        elif status is SymbolResolutionStatus.UNMATCHED:
            warnings = tuple(sorted(set(warnings + ("UNMATCHED_SYMBOL",))))
        return resolved(replace(candidate, field_warnings=warnings), instrument_id=instrument_id, status=status)

    @staticmethod
    def _mark_duplicates(candidates: tuple[ExtractedHoldingCandidate, ...]) -> tuple[ExtractedHoldingCandidate, ...]:
        seen: set[tuple[str | None, Decimal | None, Decimal | None]] = set()
        result: list[ExtractedHoldingCandidate] = []
        for candidate in candidates:
            key = (candidate.symbol or candidate.instrument_name, candidate.quantity, candidate.average_price)
            if key[0] is not None and key in seen:
                result.append(replace(candidate, field_warnings=tuple(sorted(set(candidate.field_warnings + ("POSSIBLE_DUPLICATE",))))) )
            else:
                result.append(candidate)
                if key[0] is not None:
                    seen.add(key)
        return tuple(result)

    @staticmethod
    def _validate_rows(draft: PortfolioImportDraft, rows: tuple[ReviewedHolding, ...]) -> None:
        draft_ids = {candidate.row_id for candidate in draft.holdings}
        for row in rows:
            if row.row_id not in draft_ids:
                raise PortfolioImportError("VALIDATION_ERROR", "Reviewed row is not part of this import draft.")
            if not row.instrument_id:
                raise PortfolioImportError("VALIDATION_ERROR", "Each imported holding needs a resolved instrument.")
            if row.quantity is None or row.quantity <= 0:
                raise PortfolioImportError("VALIDATION_ERROR", "Holding quantity must be greater than zero.")
            if row.average_price is None or row.average_price < 0:
                raise PortfolioImportError("VALIDATION_ERROR", "Average price must be zero or greater.")
