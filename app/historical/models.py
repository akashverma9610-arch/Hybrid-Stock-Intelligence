from dataclasses import dataclass
from datetime import datetime
from enum import Enum
class Eligibility(str,Enum): ELIGIBLE='ELIGIBLE';INELIGIBLE_FUTURE_EVENT='INELIGIBLE_FUTURE_EVENT';INELIGIBLE_FUTURE_PUBLICATION='INELIGIBLE_FUTURE_PUBLICATION';INELIGIBLE_FUTURE_RETRIEVAL='INELIGIBLE_FUTURE_RETRIEVAL';INELIGIBLE_NOT_EFFECTIVE='INELIGIBLE_NOT_EFFECTIVE';INVALID='INVALID';INSUFFICIENT_METADATA='INSUFFICIENT_METADATA'
class SurvivorshipStatus(str,Enum): POINT_IN_TIME_UNIVERSE='POINT_IN_TIME_UNIVERSE';STATIC_UNIVERSE='STATIC_UNIVERSE';SURVIVORSHIP_LIMITED='SURVIVORSHIP_LIMITED';UNKNOWN='UNKNOWN'
class DatasetQuality(str,Enum): HIGH_QUALITY='HIGH_QUALITY';MODERATE_QUALITY='MODERATE_QUALITY';LOW_QUALITY='LOW_QUALITY';RESEARCH_ONLY='RESEARCH_ONLY'
class PartitionType(str,Enum): TRAIN='TRAIN';VALIDATION='VALIDATION';TEST='TEST'
class InstrumentLifecycle(str,Enum): ACTIVE='ACTIVE';SUSPENDED='SUSPENDED';DELISTED='DELISTED';MERGED='MERGED';INACTIVE='INACTIVE'
class GapType(str,Enum): MISSING_MARKET_BAR='MISSING_MARKET_BAR';MISSING_FINANCIAL_DATA='MISSING_FINANCIAL_DATA';MISSING_RESEARCH='MISSING_RESEARCH';MISSING_SURVEILLANCE='MISSING_SURVEILLANCE';MISSING_EARNINGS_SCHEDULE='MISSING_EARNINGS_SCHEDULE';MISSING_UNIVERSE_MEMBERSHIP='MISSING_UNIVERSE_MEMBERSHIP';MISSING_BENCHMARK_DATA='MISSING_BENCHMARK_DATA';UNKNOWN_SECTOR='UNKNOWN_SECTOR'
@dataclass(frozen=True,slots=True)
class HistoricalFact: fact_id:str;kind:str;event_at:datetime|None;publication_at:datetime|None;retrieved_at:datetime|None;effective_from:datetime|None=None;effective_to:datetime|None=None;valid:bool=True
@dataclass(frozen=True,slots=True)
class UniverseMembership: membership_id:str;instrument_id:str;universe_id:str;effective_from:datetime;effective_to:datetime|None;known_at:datetime;source:str;provenance:str;status:InstrumentLifecycle
@dataclass(frozen=True,slots=True)
class HistoricalDatasetManifest: dataset_id:str;dataset_version:str;created_at:datetime;coverage_start:datetime;coverage_end:datetime;calendar_reference:str;universe_reference:str;references:dict;source_metadata:dict;quality:DatasetQuality;known_gaps:tuple[GapType,...];adjustment_methodology:str;survivorship:SurvivorshipStatus;point_in_time_capability:str;warnings:tuple[str,...];fingerprint:str
@dataclass(frozen=True,slots=True)
class HistoricalPartition: partition_id:str;dataset_id:str;partition_type:PartitionType;start:datetime;end:datetime;purge_days:int;embargo_days:int;purpose:str;created_at:datetime
