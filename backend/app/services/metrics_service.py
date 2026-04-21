from __future__ import annotations


def downsample_to_n(*, points: list[float], n: int) -> list[float]:
    if n <= 0:
        return []
    if len(points) <= n:
        return list(points)
    bucket_size = len(points) / n
    out: list[float] = []
    for i in range(n):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size)
        bucket = points[start:end] if end > start else [points[start]]
        out.append(sum(bucket) / len(bucket))
    return out
