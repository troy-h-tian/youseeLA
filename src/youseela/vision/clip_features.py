"""Local frozen CLIP embeddings and auditable temporal difference features."""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

from youseela.contracts import ClipPairFeature, Mode, Record

CLIP_REVISION = 'd05afc436d78f1c48dc0dbf8e5980a9d471f35f6'


class ClipJob(Record):
    id: str
    area_id: str
    mode: Mode
    site_id: str
    earlier_image_id: str
    later_image_id: str
    earlier_path: Path
    later_path: Path
    analysis_permitted: bool


def embedding_difference(earlier: list[float], later: list[float]) -> tuple[float, float]:
    if not earlier or len(earlier) != len(later) or not all(math.isfinite(v) for v in [*earlier,*later]):
        raise ValueError('Embeddings must have equal nonzero dimensions and finite values')
    norm_a = math.sqrt(sum(v*v for v in earlier))
    norm_b = math.sqrt(sum(v*v for v in later))
    if not norm_a or not norm_b:
        raise ValueError('Zero embeddings cannot be normalized')
    similarity = max(-1.0,min(1.0,sum(a*b for a,b in zip(earlier,later))/(norm_a*norm_b)))
    return similarity, (1-similarity)/2


def extract_pairs(jobs: list[ClipJob], cache_dir: Path, model_name: str = 'ViT-B/32') -> tuple[list[ClipPairFeature], dict[str, Any]]:
    # Lazy imports keep ordinary builds/tests independent of the optional ML installation.
    import clip
    import torch
    from PIL import Image
    if any(not job.analysis_permitted for job in jobs):
        raise ValueError('Explicit analysis permission is required for every image pair')
    cache_dir.mkdir(parents=True,exist_ok=True)
    model = None
    preprocess = None
    vectors: dict[str,list[float]] = {}
    hashes: dict[str,str] = {}
    start = time.perf_counter()
    cache_hits = 0
    encoded = 0
    for job in jobs:
        for path in (job.earlier_path, job.later_path):
            key = str(path)
            if key in vectors:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes[key] = digest
            cache_key = hashlib.sha256(f'{CLIP_REVISION}:{model_name}:{digest}:rgb-standard-preprocess'.encode()).hexdigest()
            cache = cache_dir/(cache_key+'.json')
            if cache.exists():
                vectors[key] = json.loads(cache.read_text())
                embedding_difference(vectors[key],vectors[key])
                cache_hits += 1
                continue
            if model is None:
                model, preprocess = clip.load(model_name,device='cpu',download_root=str(cache_dir/'weights'))
                model.eval()
            with Image.open(path) as image:
                tensor = preprocess(image.convert('RGB')).unsqueeze(0)
            with torch.inference_mode():
                vector = model.encode_image(tensor).float()[0]
                vector /= vector.norm()
            vectors[key] = vector.tolist()
            cache.write_text(json.dumps(vectors[key],allow_nan=False)+'\n')
            encoded += 1
    results: list[ClipPairFeature] = []
    for job in jobs:
        old,new = str(job.earlier_path),str(job.later_path)
        similarity,difference = embedding_difference(vectors[old],vectors[new])
        results.append(ClipPairFeature(id=job.id,area_id=job.area_id,mode=job.mode,site_id=job.site_id,
                                       earlier_image_id=job.earlier_image_id,later_image_id=job.later_image_id,
                                       cosine_similarity=similarity,visual_difference=difference,
                                       model=model_name,model_revision=CLIP_REVISION,
                                       image_sha256=[hashes[old],hashes[new]]))
    return results, {'model':model_name,'revision':CLIP_REVISION,'device':'cpu',
                     'torch_version':torch.__version__,'pairs':len(results),'images_encoded':encoded,
                     'image_cache_hits':cache_hits,'elapsed_seconds':time.perf_counter()-start,
                     'api_cost_usd':0,'accuracy_measured':False,
                     'identical_image_difference':embedding_difference(next(iter(vectors.values())),next(iter(vectors.values())))[1] if vectors else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('data/curated/clip-features.json'))
    parser.add_argument('--report',type=Path,default=Path('artifacts/clip-inference.json'))
    parser.add_argument('--cache',type=Path,default=Path('data/raw/clip-cache'))
    args = parser.parse_args()
    jobs = [ClipJob.model_validate(item) for item in json.loads(args.manifest.read_text())]
    result,report = extract_pairs(jobs,args.cache)
    for path,data in [(args.output,[item.model_dump(mode='json') for item in result]),(args.report,report)]:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(f'Encoded {len(result)} real CLIP pairs; {report["images_encoded"]} new images; {report["image_cache_hits"]} cache hits; no paid API calls')


if __name__ == '__main__':
    main()
