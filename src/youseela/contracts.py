"""The shared public data contract. Missing evidence is never a zero score."""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Mode = Literal["housing", "commercial"]
UnitValue = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


def public_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A public HTTP(S) URL without credentials is required")
    sensitive = {"key", "api_key", "apikey", "access_token", "token", "signature", "authorization"}
    if any(key.lower() in sensitive for key, _ in parse_qsl(parsed.query)):
        raise ValueError("Public source URLs must not contain credentials or signed tokens")
    return value


class FrontageObservation(Record):
    frontage_id: str = Field(min_length=1)
    redevelopment: Literal["present", "absent", "unclear"]
    corroboration_ids: list[str] = Field(default_factory=list)
    description: str = Field(min_length=1)


class Evidence(Record):
    id: str = Field(min_length=1)
    area_id: str = Field(min_length=1)
    kind: Literal["census", "image", "project"]
    mode: Literal["housing", "commercial", "both"]
    source_url: str
    source_date: date
    attribution: str = Field(min_length=1)
    license: str = Field(min_length=1)
    reviewed: bool = False
    data_kind: Literal["real", "fixture"] = "real"
    site_id: str | None = None
    applies_to_site_ids: list[str] = Field(default_factory=list)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    observations: list[FrontageObservation] = Field(default_factory=list)
    note: str = ""

    _url = field_validator("source_url")(public_url)

    @model_validator(mode="after")
    def image_location(self) -> "Evidence":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or neither")
        if self.kind == "image" and (not self.site_id or self.latitude is None or self.longitude is None):
            raise ValueError("Images require a site id and location")
        return self


class PressureRange(Record):
    lower: UnitValue
    upper: UnitValue

    @model_validator(mode="after")
    def ordered(self) -> "PressureRange":
        if self.lower > self.upper:
            raise ValueError("Range lower bound must not exceed upper bound")
        return self


class ScoreRange(Record):
    lower: float = Field(ge=0, le=100)
    upper: float = Field(ge=0, le=100)
    explanation: str = "Sensitivity to rent/income estimates within reported margins of error; not a confidence interval. Rent burden, imagery, and weights are held fixed."


class NumericalIndicators(Record):
    rent_burden_share: UnitValue | None = None
    renter_share: UnitValue | None = None
    affordability_pressure: UnitValue | None = None
    affordability_pressure_range: PressureRange | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    periods: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def pressure_inside_range(self) -> "NumericalIndicators":
        bounds = self.affordability_pressure_range
        if bounds and (self.affordability_pressure is None or not bounds.lower <= self.affordability_pressure <= bounds.upper):
            raise ValueError("Pressure point estimate must be within its sensitivity range")
        return self


class Contribution(Record):
    feature: str
    label: str
    value: UnitValue
    weight: UnitValue
    points: float = Field(ge=0, le=100)
    evidence_ids: list[str]
    explanation: str


class Coverage(Record):
    images: int = 0
    sites: int = 0
    frontages: int = 0
    redevelopment_frontages: int = 0
    earliest_capture: date | None = None
    latest_capture: date | None = None


class Assessment(Record):
    mode: Mode
    status: Literal["rated", "insufficient_evidence"]
    score: float | None = Field(default=None, ge=0, le=100)
    score_range: ScoreRange | None = None
    tier: Literal["lower", "moderate", "higher"] | None = None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    contributions: list[Contribution] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    configuration_version: str = "experimental-v1"
    coverage: Coverage = Field(default_factory=Coverage)

    @model_validator(mode="after")
    def coherent_status(self) -> "Assessment":
        if self.score_range and (self.score is None or not self.score_range.lower <= self.score <= self.score_range.upper):
            raise ValueError("Score must lie within its sensitivity range")
        if self.status == "insufficient_evidence":
            if self.score is not None or self.tier is not None or self.contributions:
                raise ValueError("Insufficient evidence must have null score/tier and no contributions")
            if not self.reasons:
                raise ValueError("An unrated assessment must explain missing evidence")
        elif self.score is None or self.tier is None:
            raise ValueError("A rated assessment needs a score and tier")
        elif abs(sum(c.points for c in self.contributions) - self.score) > 0.01:
            raise ValueError("Contributions must sum to the score")
        return self


class AreaInput(Record):
    id: str
    name: str
    geometry: dict[str, Any]
    indicators: NumericalIndicators
    boundary_source_url: str | None = None
    boundary_vintage: str | None = None

    @field_validator("boundary_source_url")
    @classmethod
    def boundary_source(cls, value: str | None) -> str | None:
        return public_url(value) if value else None


class Area(AreaInput):
    housing: Assessment
    commercial: Assessment


class Business(Record):
    id: str
    name: str
    area_id: str
    address: str = ""
    location_source_url: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    description: str
    recommendation_reason: str
    source_url: str
    verified_at: date
    website_url: str
    directions_url: str
    data_kind: Literal["real", "fixture"] = "real"

    _urls = field_validator("source_url", "website_url", "directions_url")(public_url)

    @field_validator("location_source_url")
    @classmethod
    def location_source(cls, value: str | None) -> str | None:
        return public_url(value) if value else None


class Resource(Record):
    id: str
    name: str
    concern: str
    jurisdiction: str
    description: str
    source_url: str
    verified_at: date
    data_kind: Literal["real", "fixture"] = "real"

    _url = field_validator("source_url")(public_url)


class Dataset(Record):
    data_kind: Literal["real", "fixture"]
    areas: list[AreaInput]
    evidence: list[Evidence]
    businesses: list[Business] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)


class Bundle(Record):
    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    assessed_as_of: date
    data_kind: Literal["real", "fixture"]
    methodology: dict[str, Any]
    areas: list[Area]
    evidence: list[Evidence]
    businesses: list[Business]
    resources: list[Resource]

    @model_validator(mode="after")
    def check_references(self) -> "Bundle":
        for records in [self.areas, self.evidence, self.businesses, self.resources]:
            if len({r.id for r in records}) != len(records):
                raise ValueError("Duplicate record ids are not allowed")
        areas = {a.id for a in self.areas}
        evidence = {e.id: e for e in self.evidence}
        for item in [*self.evidence, *self.businesses]:
            if item.area_id not in areas:
                raise ValueError("Record points to an unknown area")
        for area in self.areas:
            refs = set(area.indicators.evidence_ids)
            for mode in [area.housing, area.commercial]:
                refs.update(mode.evidence_ids)
                for contribution in mode.contributions:
                    refs.update(contribution.evidence_ids)
            if any(ref not in evidence or evidence[ref].area_id != area.id for ref in refs):
                raise ValueError("Assessment has dangling or wrong-area evidence references")
        for item in self.evidence:
            if not item.reviewed:
                raise ValueError("Public evidence must be human-reviewed")
            for obs in item.observations:
                if any(ref not in evidence or evidence[ref].area_id != item.area_id for ref in obs.corroboration_ids):
                    raise ValueError("Observation has dangling corroboration")
        if self.data_kind == "real" and any(r.data_kind != "real" for r in [*self.evidence, *self.businesses, *self.resources]):
            raise ValueError("Fixture evidence cannot be labeled real")
        return self
