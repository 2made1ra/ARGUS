from pathlib import Path

from sage.llm import LMStudioClient
from sage.models import ProcessingResult
from sage.process import process_document


class SageProcessorAdapter:
    def __init__(
        self,
        *,
        work_dir: Path,
        llm_client: LMStudioClient | None = None,
    ) -> None:
        self._work_dir = work_dir
        self._llm_client = llm_client

    async def process(self, file_path: Path) -> ProcessingResult:
        return await process_document(
            src=file_path,
            work_dir=self._work_dir,
            llm_client=self._llm_client,
        )


__all__ = ["SageProcessorAdapter"]
