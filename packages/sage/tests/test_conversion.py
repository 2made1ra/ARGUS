import asyncio
import shutil
from pathlib import Path

import pytest
from sage.conversion.libreoffice import ConversionError, ensure_pdf


class FakeProcess:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout, self.stderr

    def kill(self) -> None:
        self.killed = True


def test_ensure_pdf_returns_pdf_without_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "contract.pdf"

    async def fail_create_subprocess_exec(*args: object, **kwargs: object) -> None:
        raise AssertionError("PDF inputs must not call soffice")

    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        fail_create_subprocess_exec,
    )

    assert asyncio.run(ensure_pdf(src, tmp_path)) == src


def test_ensure_pdf_converts_office_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "contract.docx"
    produced = tmp_path / "contract.pdf"
    produced.touch()
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def fake_create_subprocess_exec(
        *args: object,
        **kwargs: object,
    ) -> FakeProcess:
        calls.append((args, kwargs))
        return FakeProcess()

    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    assert asyncio.run(ensure_pdf(src, tmp_path)) == produced
    assert calls == [
        (
            (
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp_path),
                str(src),
            ),
            {
                "stdout": asyncio.subprocess.PIPE,
                "stderr": asyncio.subprocess.PIPE,
            },
        )
    ]


def test_ensure_pdf_raises_conversion_error_on_nonzero_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "contract.doc"

    async def fake_create_subprocess_exec(
        *args: object,
        **kwargs: object,
    ) -> FakeProcess:
        return FakeProcess(returncode=1, stderr=b"cannot convert")

    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    with pytest.raises(ConversionError, match="cannot convert"):
        asyncio.run(ensure_pdf(src, tmp_path))


def test_ensure_pdf_raises_conversion_error_on_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "contract.odt"
    proc = FakeProcess()

    async def fake_create_subprocess_exec(
        *args: object,
        **kwargs: object,
    ) -> FakeProcess:
        return proc

    async def fake_wait_for(awaitable: object, timeout: float) -> None:
        assert timeout == 120
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    with pytest.raises(ConversionError, match="timed out"):
        asyncio.run(ensure_pdf(src, tmp_path))

    assert proc.killed is True


@pytest.mark.skipif(not shutil.which("soffice"), reason="soffice is not installed")
def test_ensure_pdf_smoke_with_real_soffice(tmp_path: Path) -> None:
    src = tmp_path / "contract.rtf"
    src.write_text(r"{\rtf1\ansi Contract smoke test}", encoding="utf-8")

    produced = asyncio.run(ensure_pdf(src, tmp_path))

    assert produced == tmp_path / "contract.pdf"
    assert produced.exists()
