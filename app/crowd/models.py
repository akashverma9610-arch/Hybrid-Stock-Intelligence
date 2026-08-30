from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

class CrowdCategory(StrEnum): SOCIAL="social"; NEWS="news"; RECOMMENDATION="recommendation"; SEARCH="search"; DISCUSSION="discussion"; POSITIONING="positioning"
@dataclass(frozen=True, slots=True)
class CrowdObservation:
    observation_id:str; instrument_id:str; category:CrowdCategory; source:str; tier:str; value:float; publication_timestamp:datetime; retrieval_timestamp:datetime; methodology:str; confidence:float|None; sample_size:int|None=None; duplicate_group:str|None=None
@dataclass(frozen=True, slots=True)
class NewsEvent:
    event_id:str; instrument_id:str; publication_timestamp:datetime; title:str; polarity:str; source_reference:str
@dataclass(frozen=True, slots=True)
class CrowdSnapshot:
    as_of_timestamp:datetime; observations:tuple[CrowdObservation,...]; events:tuple[NewsEvent,...]=()
