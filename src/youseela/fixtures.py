"""Deterministic, clearly synthetic data for frontend development and load tests."""

from datetime import date

from youseela.contracts import AreaInput, Business, Dataset, Evidence, NumericalIndicators


def make_fixture(count: int = 3) -> Dataset:
    if count < 1 or count > 10000:
        raise ValueError("Fixture size must be between 1 and 10000")
    areas: list[AreaInput] = []
    evidence: list[Evidence] = []
    businesses: list[Business] = []
    for index in range(count):
        area_id = f"fixture-{index:04d}"
        lon, lat = -118.38 + (index % 20)*.01, 33.93 + (index//20)*.01
        geometry = {"type": "Polygon", "coordinates": [[[lon,lat],[lon+.009,lat],[lon+.009,lat+.009],[lon,lat+.009],[lon,lat]]]}
        base = dict(area_id=area_id, source_url="https://example.org/synthetic-evidence", source_date=date(2026,1,1),
                    attribution="Synthetic fixture — not real neighborhood evidence", license="Synthetic test data", reviewed=True, data_kind="fixture")
        evidence.append(Evidence(id=f"{area_id}-acs", kind="census", mode="both", **base))
        evidence.append(Evidence(id=f"{area_id}-project", kind="project", mode="both",
                                 applies_to_site_ids=[f"{area_id}-{mode}-site-{site}" for mode in ["housing", "commercial"] for site in range(3)], **base))
        for mode in ["housing", "commercial"]:
            if index % 3 == 2 or (index % 3 == 1 and mode == "housing"):
                continue
            for site in range(3):
                observations = [{"frontage_id":f"{area_id}-{mode}-{site}-{front}",
                                 "redevelopment":"present" if front == 0 else "absent",
                                 "corroboration_ids":[f"{area_id}-project"] if front == 0 else [],
                                 "description":"Synthetic observation for development only"} for front in range(2)]
                evidence.append(Evidence(id=f"{area_id}-{mode}-{site}", kind="image", mode=mode,
                                         site_id=f"{area_id}-{mode}-site-{site}", latitude=lat+.002+site*.001,
                                         longitude=lon+.002, observations=observations, **base))
        areas.append(AreaInput(id=area_id, name=f"Synthetic area {index+1} — fixture", geometry=geometry,
                               indicators=NumericalIndicators(rent_burden_share=.4+(index%4)*.1,
                                                              renter_share=.6, affordability_pressure=.5,
                                                              evidence_ids=[f"{area_id}-acs"], periods=["Synthetic period"])))
        businesses.append(Business(id=f"business-{index}", name=f"Synthetic business {index+1}", area_id=area_id,
                                   latitude=lat+.002, longitude=lon+.002, description="Fixture, not an actual business",
                                   recommendation_reason="Synthetic area context for UI development",
                                   source_url="https://example.org", verified_at=date(2026,1,1),
                                   website_url="https://example.org", directions_url="https://example.org", data_kind="fixture"))
    return Dataset(data_kind="fixture", areas=areas, evidence=evidence, businesses=businesses)
