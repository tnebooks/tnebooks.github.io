from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
import re
from datetime import date

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Boundary(Contract):
    page: int
    box: list[float]
    @model_validator(mode='after')
    def valid(self):
        if len(self.box)!=4 or not (0<=self.box[0]<self.box[2]<=1 and 0<=self.box[1]<self.box[3]<=1):
            raise ValueError('Invalid normalized crop coordinates')
        return self

class LessonSpec(Contract):
    id: str
    title: str
    slug: str
    weight: int
    pdf_start: int
    pdf_end: int
    printed_pages: list[str] = Field(default_factory=list)
    boundaries: list[Boundary] = Field(default_factory=list)
    @model_validator(mode='after')
    def valid(self):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',self.slug): raise ValueError('Unsafe lesson slug')
        if not self.id or self.weight<1 or not 1<=self.pdf_start<=self.pdf_end: raise ValueError('Invalid lesson range/identity')
        if len({b.page for b in self.boundaries})!=len(self.boundaries) or any(not self.pdf_start<=b.page<=self.pdf_end for b in self.boundaries): raise ValueError('Invalid boundary page')
        return self

class RateCard(Contract):
    effective_date: date
    currency: str = Field(default='USD',pattern=r'^[A-Z]{3}$')
    input_per_million: float = Field(ge=0,allow_inf_nan=False)
    cached_per_million: float = Field(ge=0,allow_inf_nan=False)
    output_per_million: float = Field(ge=0,allow_inf_nan=False)

class BookManifest(Contract):
    schema_version: int = 1
    book_id: str
    pdf: Path
    output: Path
    medium: Literal['en','ta']
    class_name: str
    subject: str
    edition: str
    term: str | None = None
    volume: str | None = None
    model: str | None = None
    pdf_sha256: str = ''
    page_count: int = 0
    lessons: list[LessonSpec] = Field(default_factory=list)
    excluded_sections: list[str] = Field(default_factory=list)
    glossary: list[str] = Field(default_factory=list)
    prices: RateCard | None = None
    @model_validator(mode='after')
    def valid(self):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',self.book_id): raise ValueError('Unsafe book ID')
        for key in ['id','slug','weight']:
            if len({getattr(x,key) for x in self.lessons})!=len(self.lessons): raise ValueError('Duplicate lesson identity')
        for a in self.lessons:
            if self.page_count and a.pdf_end>self.page_count: raise ValueError('Page beyond PDF')
            for b in self.lessons:
                if a is b: continue
                for page in range(max(a.pdf_start,b.pdf_start),min(a.pdf_end,b.pdf_end)+1):
                    ba=next((x.box for x in a.boundaries if x.page==page),None); bb=next((x.box for x in b.boundaries if x.page==page),None)
                    if not ba or not bb or (max(ba[0],bb[0])<min(ba[2],bb[2]) and max(ba[1],bb[1])<min(ba[3],bb[3])): raise ValueError('Shared page needs disjoint boundaries')
        return self

class RunLimits(Contract):
    page_window: int = Field(default=2,ge=1,le=4)
    timeout: float = Field(default=120,gt=0)
    max_output_tokens: int = Field(default=8192,ge=512)
    retries: int = Field(default=2,ge=0,le=2)
    repairs: int = Field(default=2,ge=0,le=2)
    max_calls_per_lesson: int = Field(default=100,ge=1)
    token_limit: int | None = Field(default=None,gt=0)
    max_seconds: float | None = Field(default=None,gt=0)

class SourcePage(Contract):
    page: int
    width: float
    height: float
    text: str
    image: Path
    checksum: str
    warnings: list[str] = Field(default_factory=list)

class SourceItem(Contract):
    id: str
    kind: Literal['heading','prose','table','figure','equation','activity','example','sidebar','exercise','caption']
    page: int
    box: list[float] | None
    text: str
    caption: str
    exercise_id: str | None
    order: int
    flags: list[str]

class ItemInventory(Contract):
    items: list[SourceItem]
    language: Literal['en','ta','unknown']
    issues: list[str]

class LessonEvidence(Contract):
    lesson: LessonSpec
    medium: Literal['en','ta']
    pages: list[SourcePage]
    items: list[SourceItem]
    fingerprint: str

class AssetSpec(Contract):
    item_id: str
    page: int
    box: list[float]
    caption: str

class AssetRecord(Contract):
    item_id: str
    page: int
    box: list[float]
    caption: str
    path: str
    sha256: str
    width: int
    height: int
    flags: list[str] = Field(default_factory=list)
    local_file: Path | None = None

class ExistingLesson(Contract):
    path: Path
    front_matter: str
    body: str
    sha256: str
    assets: dict[str,str]
    sections: dict[str,str]
    managed_aids: str = ''
    aids_modified: bool = False

class SectionEdit(Contract):
    anchor: str
    expected_sha256: str | None
    markdown: str
    after_anchor: str | None
    item_ids: list[str]

class StudyAid(Contract):
    id: str
    markdown: str
    source_item_ids: list[str]

class LessonDraft(Contract):
    edits: list[SectionEdit]
    assets: list[AssetSpec]
    aids: list[StudyAid]
    notes: list[str]

class Finding(Contract):
    item_id: str | None
    section: str | None
    message: str
    blocking: bool

class ReviewResult(Contract):
    covered_ids: list[str]
    findings: list[Finding]
    verified_aid_ids: list[str]
    teacher_approved: bool = False

class ValidationResult(Contract):
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    site_status: str = 'not-required'
    @property
    def passing(self): return not self.errors

class ApiUsage(Contract):
    response_id: str
    request_id: str | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None

class RunState(Contract):
    id: str
    book: BookManifest
    limits: RunLimits
    mode: Literal['run','audit']
    lessons: dict[str,dict] = Field(default_factory=dict)
    usage: list[ApiUsage] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    resources: dict = Field(default_factory=dict)
    started: float
    elapsed: float = 0
    selected_ids: list[str] = Field(default_factory=list)
    status: str = 'running'
