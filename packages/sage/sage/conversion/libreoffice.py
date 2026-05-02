import asyncio
from pathlib import Path

CONVERSION_TIMEOUT_SECONDS = 120
OFFICE_SUFFIXES = {".doc", ".docx", ".rtf", ".odt"}


class ConversionError(Exception):
    pass


async def ensure_pdf(src: Path, work_dir: Path) -> Path:
    """Return `src` if it is a PDF, otherwise convert it to PDF with LibreOffice."""
    if src.suffix.lower() == ".pdf":
        return src

    suffix = src.suffix.lower()
    if suffix not in OFFICE_SUFFIXES:
        raise ConversionError(f"Unsupported file type: {suffix}")

    work_dir.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "soffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(work_dir),
        str(src),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        _, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=CONVERSION_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        proc.kill()
        await proc.communicate()
        raise ConversionError(
            f"soffice conversion timed out after {CONVERSION_TIMEOUT_SECONDS} seconds"
        ) from exc

    decoded_stderr = stderr.decode(errors="ignore") if stderr else ""
    if proc.returncode != 0:
        raise ConversionError(decoded_stderr)

    produced = work_dir / f"{src.stem}.pdf"
    if not produced.exists():
        raise ConversionError(f"converted PDF not found at {produced}")

    return produced
