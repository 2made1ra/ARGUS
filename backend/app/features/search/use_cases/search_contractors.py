from __future__ import annotations

from uuid import UUID

from app.core.domain.ids import ContractorEntityId
from app.features.contractors.ports import ContractorRepository
from app.features.ingest.ports import EmbeddingService
from app.features.search.dto import ContractorSearchResult, SearchGroup
from app.features.search.ports import VectorSearch

_QDRANT_GROUP_LIMIT = 200
_QDRANT_GROUP_SIZE = 3
_SNIPPET_LENGTH = 240


class SearchContractorsUseCase:
    def __init__(
        self,
        *,
        embeddings: EmbeddingService,
        vectors: VectorSearch,
        contractors: ContractorRepository,
    ) -> None:
        self._embeddings = embeddings
        self._vectors = vectors
        self._contractors = contractors

    async def execute(
        self,
        *,
        query: str,
        limit: int = 20,
    ) -> list[ContractorSearchResult]:
        [query_vector] = await self._embeddings.embed([query])
        groups = await self._vectors.search(
            query_vector=query_vector,
            limit=_QDRANT_GROUP_LIMIT,
            group_by="contractor_entity_id",
            group_size=_QDRANT_GROUP_SIZE,
        )

        search_groups = [group for group in groups if isinstance(group, SearchGroup)]
        contractor_ids = [_contractor_id_from_group(group) for group in search_groups]
        contractors = await self._contractors.get_many(contractor_ids)

        results: list[ContractorSearchResult] = []
        for group in search_groups:
            contractor_id = _contractor_id_from_group(group)
            contractor = contractors.get(contractor_id)
            if contractor is None or not group.hits:
                continue

            top_hit = max(group.hits, key=lambda hit: hit.score)
            results.append(
                ContractorSearchResult(
                    contractor_id=contractor_id,
                    name=contractor.display_name,
                    score=top_hit.score,
                    matched_chunks_count=len(group.hits),
                    top_snippet=str(top_hit.payload["text"])[0:_SNIPPET_LENGTH],
                ),
            )

        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]


def _contractor_id_from_group(group: SearchGroup) -> ContractorEntityId:
    return ContractorEntityId(UUID(group.group_key))


__all__ = ["SearchContractorsUseCase"]
