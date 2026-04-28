from math import ceil
from typing import Generic, Sequence, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class PageMeta(BaseModel):
    pg_no: int = Field(default=1, ge=1)
    pg_size: int = Field(default=20, ge=1, le=500)
    total_records: int = Field(default=0, ge=0)
    total_pg: int = Field(default=0, ge=0)


class PaginatedResponse(BaseModel, Generic[T]):
    page: PageMeta
    items: list[T]


def paginate(items: Sequence[T], pg_no: int = 1, pg_size: int = 20) -> PaginatedResponse[T]:
    total_records = len(items)
    total_pg = ceil(total_records / pg_size) if total_records else 0
    start_idx = (pg_no - 1) * pg_size
    end_idx = start_idx + pg_size
    return PaginatedResponse(
        page=PageMeta(pg_no=pg_no, pg_size=pg_size, total_records=total_records, total_pg=total_pg),
        items=list(items[start_idx:end_idx]),
    )
