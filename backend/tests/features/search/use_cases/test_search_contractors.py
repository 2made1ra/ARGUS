from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.domain.ids import ContractorEntityId
from app.features.contractors.entities.contractor import Contractor
from app.features.ingest.entities.document import Document
from app.features.search.dto import SearchGroup, SearchHit
from app.features.search.use_cases.search_contractors import SearchContractorsUseCase


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1, 0.2, 0.3]]


class FakeVectorSearch:
    def __init__(self, groups: list[SearchGroup]) -> None:
        self.groups = groups
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        *,
        query_vector: list[float],
        limit: int,
        filter: dict[str, Any] | None = None,
        group_by: str | None = None,
        group_size: int = 3,
    ) -> list[SearchGroup]:
        self.calls.append(
            {
                "query_vector": query_vector,
                "limit": limit,
                "filter": filter,
                "group_by": group_by,
                "group_size": group_size,
            },
        )
        return self.groups


class FakeContractorRepository:
    def __init__(self, contractors: dict[ContractorEntityId, Contractor]) -> None:
        self.contractors = contractors
        self.get_many_calls: list[list[ContractorEntityId]] = []
        self.get_calls: list[ContractorEntityId] = []

    async def get_many(
        self,
        ids: list[ContractorEntityId],
    ) -> dict[ContractorEntityId, Contractor]:
        self.get_many_calls.append(ids)
        return {
            contractor_id: self.contractors[contractor_id]
            for contractor_id in ids
            if contractor_id in self.contractors
        }

    async def add(self, contractor: Contractor) -> None:
        raise NotImplementedError

    async def get(self, id: ContractorEntityId) -> Contractor:
        self.get_calls.append(id)
        raise NotImplementedError

    async def find_by_inn(self, inn: str) -> Contractor | None:
        raise NotImplementedError

    async def find_by_normalized_key(self, key: str) -> Contractor | None:
        raise NotImplementedError

    async def find_all_for_fuzzy(self) -> list[Contractor]:
        raise NotImplementedError

    async def count_documents_for(self, id: ContractorEntityId) -> int:
        raise NotImplementedError

    async def list_for_contractor(
        self,
        id: ContractorEntityId,
        *,
        limit: int,
        offset: int,
    ) -> list[Document]:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_search_contractors_groups_hits_and_loads_contractors_in_batch() -> None:
    contractor_a = ContractorEntityId(uuid4())
    contractor_b = ContractorEntityId(uuid4())
    contractor_c = ContractorEntityId(uuid4())
    groups = [
        _group(
            contractor_a,
            [
                _hit(score=0.61, text="lower score"),
                _hit(score=0.94, text="A" * 300),
            ],
        ),
        _group(contractor_b, [_hit(score=0.72, text="middle")]),
        _group(contractor_c, [_hit(score=0.99, text="top")]),
    ]
    embeddings = FakeEmbeddingService()
    vectors = FakeVectorSearch(groups)
    contractors = FakeContractorRepository(
        {
            contractor_a: _contractor(contractor_a, "ООО Альфа"),
            contractor_b: _contractor(contractor_b, "ООО Бета"),
            contractor_c: _contractor(contractor_c, "ООО Гамма"),
        },
    )
    use_case = SearchContractorsUseCase(
        embeddings=embeddings,
        vectors=vectors,
        contractors=contractors,
    )

    results = await use_case.execute(query="охрана объекта", limit=2)

    assert embeddings.calls == [["охрана объекта"]]
    assert vectors.calls == [
        {
            "query_vector": [0.1, 0.2, 0.3],
            "limit": 200,
            "filter": None,
            "group_by": "contractor_entity_id",
            "group_size": 3,
        },
    ]
    assert contractors.get_many_calls == [[contractor_a, contractor_b, contractor_c]]
    assert contractors.get_calls == []
    assert [(result.contractor_id, result.name, result.score) for result in results] == [
        (contractor_c, "ООО Гамма", 0.99),
        (contractor_a, "ООО Альфа", 0.94),
    ]
    assert results[1].matched_chunks_count == 2
    assert results[1].top_snippet == "A" * 240


@pytest.mark.asyncio
async def test_search_contractors_skips_groups_without_contractor_metadata() -> None:
    existing_contractor_id = ContractorEntityId(uuid4())
    missing_contractor_id = ContractorEntityId(uuid4())
    embeddings = FakeEmbeddingService()
    vectors = FakeVectorSearch(
        [
            _group(missing_contractor_id, [_hit(score=0.95, text="missing")]),
            _group(existing_contractor_id, [_hit(score=0.82, text="existing")]),
        ],
    )
    contractors = FakeContractorRepository(
        {
            existing_contractor_id: _contractor(
                existing_contractor_id,
                "ООО Существующий",
            ),
        },
    )
    use_case = SearchContractorsUseCase(
        embeddings=embeddings,
        vectors=vectors,
        contractors=contractors,
    )

    results = await use_case.execute(query="поставка")

    assert len(results) == 1
    assert results[0].contractor_id == existing_contractor_id
    assert results[0].name == "ООО Существующий"
    assert contractors.get_many_calls == [
        [missing_contractor_id, existing_contractor_id],
    ]
    assert contractors.get_calls == []


def _group(contractor_id: ContractorEntityId, hits: list[SearchHit]) -> SearchGroup:
    return SearchGroup(group_key=str(contractor_id), hits=hits)


def _hit(*, score: float, text: str) -> SearchHit:
    return SearchHit(id=UUID(str(uuid4())), score=score, payload={"text": text})


def _contractor(contractor_id: ContractorEntityId, display_name: str) -> Contractor:
    return Contractor(
        id=contractor_id,
        display_name=display_name,
        normalized_key=display_name.casefold(),
        inn=None,
        kpp=None,
        created_at=datetime.now(UTC),
    )
