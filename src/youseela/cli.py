"""Person A commands. All outputs are files; paid inference is opt-in."""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from youseela.contracts import Bundle, Business, Dataset, Evidence, Resource
from youseela.export import build_bundle, write_bundle
from youseela.fixtures import make_fixture
from youseela.prepare import prepare_dataset
from youseela.scoring import load_config
from youseela.sources.census import fetch_county, read_rows
from youseela.sources.geography import discover_inglewood


def write_json(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    fixture = sub.add_parser("fixture", help="Generate labeled synthetic frontend data")
    fixture.add_argument("--output", type=Path, default=Path("data/fixtures/bundle.json"))
    fixture.add_argument("--count", type=int, default=3)
    validate = sub.add_parser("validate", help="Check public bundle schema and references")
    validate.add_argument("bundle", type=Path)
    schema = sub.add_parser("schema", help="Export the shared public JSON Schema")
    schema.add_argument("--output", type=Path, default=Path("contracts/bundle.schema.json"))
    web = sub.add_parser("web-export", help="Adapt a validated pipeline bundle for the React explorer")
    web.add_argument("--input", type=Path, default=Path("data/exports/demo.json"))
    web.add_argument("--output", type=Path, default=Path("web/public/data/demo.json"))
    build = sub.add_parser("build", help="Score a curated input dataset and export a public bundle")
    build.add_argument("--input", type=Path, default=Path("data/curated/dataset.json"))
    build.add_argument("--config", type=Path, default=Path("config/assessment.json"))
    build.add_argument("--output", type=Path, default=Path("data/exports/demo.json"))
    build.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    build.add_argument("--context", type=Path, default=Path("data/curated/context.json"),
                       help="Unscored neighborhood-change context to attach when the file exists")
    context = sub.add_parser("context", help="Derive assessor, business-pattern and UDP benchmark context per tract")
    context.add_argument("--geography", type=Path, default=Path("data/curated/areas.geojson"))
    context.add_argument("--raw", type=Path, default=Path("data/raw/context"))
    context.add_argument("--prior-roll", type=int, default=2020)
    context.add_argument("--latest-roll", type=int, default=2025)
    context.add_argument("--prior-zbp", type=int, default=2019)
    context.add_argument("--latest-zbp", type=int, default=2023)
    context.add_argument("--output", type=Path, default=Path("data/curated/context.json"))
    context.add_argument("--benchmark", type=Path, default=Path("artifacts/context-benchmark.json"))
    census = sub.add_parser("census", help="Fetch ACS county records; requires CENSUS_API_KEY")
    census.add_argument("--year", type=int, required=True)
    census.add_argument("--output", type=Path, required=True)
    geo = sub.add_parser("geography", help="Discover official full tracts intersecting Inglewood")
    geo.add_argument("--output", type=Path, default=Path("data/curated/areas.geojson"))
    prepare = sub.add_parser("prepare", help="Join raw ACS rows to geographic inventory")
    prepare.add_argument("--geography", type=Path, default=Path("data/curated/areas.geojson"))
    prepare.add_argument("--latest", type=Path, required=True)
    prepare.add_argument("--prior", type=Path, required=True)
    prepare.add_argument("--latest-year", type=int, default=2024)
    prepare.add_argument("--prior-year", type=int, default=2021)
    prepare.add_argument("--area-ids", nargs="+")
    prepare.add_argument("--geography-verified", action="store_true", help="Only after checking tract equivalence across vintages")
    prepare.add_argument("--output", type=Path, default=Path("data/curated/dataset.json"))
    prepare.add_argument("--businesses", type=Path, default=Path("data/curated/businesses.json"))
    prepare.add_argument("--resources", type=Path, default=Path("data/curated/resources.json"))
    prepare.add_argument("--evidence", type=Path, default=Path("data/curated/evidence.json"))
    sub.add_parser("env-status", help="Report whether required settings exist, never their values")
    images = sub.add_parser("images", help="Discover Mapillary metadata in a small bounding box")
    images.add_argument("--bbox", required=True, help="west,south,east,north (use --bbox=-118.36,33.95,-118.355,33.955)")
    images.add_argument("--limit", type=int, default=50)
    images.add_argument("--captured-after", type=date.fromisoformat)
    images.add_argument("--output", type=Path, default=Path("data/raw/images/discovery.json"))
    vision = sub.add_parser("vision", help="Analyze permitted local images; requires configured provider and budget")
    vision.add_argument("--manifest", type=Path, required=True)
    vision.add_argument("--state", type=Path, default=Path("data/raw/vision"))
    vision.add_argument("--output", type=Path, default=Path("data/raw/vision/drafts.json"))
    return root


def run(args: argparse.Namespace) -> None:
    if args.command == "fixture":
        bundle = build_bundle(make_fixture(args.count), load_config(), date.today())
        write_bundle(bundle, args.output)
        print(f"Wrote FIXTURE bundle ({len(bundle.areas)} synthetic areas) to {args.output}")
    elif args.command == "validate":
        bundle = Bundle.model_validate_json(args.bundle.read_text())
        print(f"Valid {bundle.data_kind} bundle: {len(bundle.areas)} areas, {len(bundle.evidence)} evidence records")
    elif args.command == "schema":
        write_json(Bundle.model_json_schema(), args.output)
        print(f"Wrote schema to {args.output}")
    elif args.command == "web-export":
        from youseela.web_export import to_web_bundle
        bundle = Bundle.model_validate_json(args.input.read_text())
        write_json(to_web_bundle(bundle), args.output)
        print(f"Exported {bundle.data_kind} explorer data -> {args.output}")
    elif args.command == "build":
        dataset = Dataset.model_validate_json(args.input.read_text())
        if args.context.exists():
            from youseela.context import ContextFile, attach
            dataset = attach(dataset, ContextFile.model_validate_json(args.context.read_text()))
            print(f"Attached unscored context from {args.context}")
        bundle = build_bundle(dataset, load_config(args.config), args.as_of)
        write_bundle(bundle, args.output)
        rated = sum(a.housing.status == "rated" for a in bundle.areas) + sum(a.commercial.status == "rated" for a in bundle.areas)
        print(f"Wrote {bundle.data_kind} bundle: {len(bundle.areas)} areas, {rated} rated mode assessments -> {args.output}")
    elif args.command == "census":
        rows = fetch_county(args.year, os.environ.get("CENSUS_API_KEY", ""))
        write_json(rows, args.output)
        print(f"Fetched {len(rows)} county tracts for ACS {args.year} -> {args.output}")
    elif args.command == "geography":
        collection = discover_inglewood()
        write_json(collection, args.output)
        print(f"Fetched {len(collection['features'])} full tracts intersecting Inglewood -> {args.output}")
    elif args.command == "prepare":
        dataset = prepare_dataset(json.loads(args.geography.read_text()), read_rows(args.latest), read_rows(args.prior),
                                  args.latest_year, args.prior_year, args.area_ids, args.geography_verified)
        selected = {area.id for area in dataset.areas}
        if args.businesses.exists():
            businesses = [Business.model_validate(item) for item in json.loads(args.businesses.read_text())]
            dataset.businesses = [item for item in businesses if item.area_id in selected]
            print(f"Included {len(dataset.businesses)}/{len(businesses)} curated businesses within selected areas")
        if args.resources.exists():
            dataset.resources = [Resource.model_validate(item) for item in json.loads(args.resources.read_text())]
        if args.evidence.exists():
            extra = [Evidence.model_validate(item) for item in json.loads(args.evidence.read_text())]
            dataset.evidence.extend(item for item in extra if item.area_id in selected)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(dataset.model_dump_json(indent=2)+"\n")
        print(f"Prepared {len(dataset.areas)} real areas; imagery still needs curation -> {args.output}")
    elif args.command == "context":
        from youseela.context import benchmark, collect
        result = collect(json.loads(args.geography.read_text()), args.raw, args.prior_roll, args.latest_roll,
                         args.prior_zbp, args.latest_zbp)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.model_dump_json(indent=2)+"\n")
        write_json({"generated_at": result.generated_at.isoformat(), **benchmark(result.areas)}, args.benchmark)
        labeled = sum(1 for item in result.areas.values() if item.reference_typology)
        print(f"Wrote context for {len(result.areas)} tracts ({labeled} with UDP reference) -> {args.output}; benchmark -> {args.benchmark}")
    elif args.command == "env-status":
        keys = ["CENSUS_API_KEY", "MAPILLARY_ACCESS_TOKEN", "VISION_PROVIDER", "VISION_MODEL", "VISION_API_KEY"]
        print(json.dumps({key:bool(os.environ.get(key)) for key in keys}, indent=2))
    elif args.command == "images":
        from youseela.sources.imagery import discover_images
        bounds = tuple(float(v) for v in args.bbox.split(","))
        if len(bounds) != 4:
            raise ValueError("bbox needs four coordinates")
        result = discover_images(bounds, os.environ.get("MAPILLARY_ACCESS_TOKEN", ""), args.limit,
                                 captured_after=args.captured_after)
        write_json(result, args.output)
        print(f"Discovered {len(result['images'])} images; has_more={result['has_more']}. Metadata needs review: {args.output}")
    elif args.command == "vision":
        from youseela.vision.provider import ImageJob, VisionSettings, extract_image
        settings = VisionSettings.from_env()
        jobs = [ImageJob.model_validate(item) for item in json.loads(args.manifest.read_text())]
        results = []
        for job in jobs:
            if not job.image_path.is_absolute():
                job.image_path = args.manifest.parent / job.image_path
            results.append(extract_image(job, settings, args.state).model_dump(mode="json"))
            # Save progress after every image, so a later failure does not lose drafts.
            write_json(results, args.output)
        print(f"Saved {len(results)} UNREVIEWED image drafts to {args.output}; review and corroborate before build")


def main() -> None:
    load_dotenv(override=False)
    args = parser().parse_args()
    try:
        run(args)
    except ValidationError as error:
        # Pydantic's full error can contain input values, including mistyped secrets.
        print("Validation failed: " + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in error.errors()), file=sys.stderr)
        raise SystemExit(2) from None
    except httpx.HTTPError:
        print("Source request failed; check connectivity, credentials and dataset availability.", file=sys.stderr)
        raise SystemExit(2) from None
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
