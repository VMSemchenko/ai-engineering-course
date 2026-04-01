import logging
import tempfile
from pathlib import Path
from unstructured.partition.auto import partition

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def extract_text(path: str) -> str:
    elements = partition(filename=path)
    return "\n\n".join(str(el) for el in elements if str(el).strip())


def safe_extract(path: str) -> str | None:
    try:
        return extract_text(path)
    except FileNotFoundError:
        logging.error(f"FILE_NOT_FOUND file={path}")
        return None
    except MemoryError:
        logging.error(f"OOM file={path}")
        return None
    except Exception as e:
        error_name = type(e).__name__
        logging.error(f"{error_name} file={path} error={e}")
        return None


def process_folder(folder: str) -> dict:
    folder = Path(folder)
    results = {"ok": [], "failed": []}

    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        text = safe_extract(str(f))
        if text is not None:
            results["ok"].append({"file": f.name, "chars": len(text)})
        else:
            results["failed"].append(f.name)

    return results


if __name__ == "__main__":
    # Create test files: good, empty, corrupted, missing extension
    tmp = Path(tempfile.mkdtemp())

    (tmp / "good.html").write_text("<html><body><h1>Hello</h1><p>World</p></body></html>")
    (tmp / "empty.pdf").write_bytes(b"")
    (tmp / "corrupted.pdf").write_bytes(b"%PDF-1.4\ntruncated garbage here")
    (tmp / "binary.pdf").write_bytes(b"\x00\x01\x02\xff" * 100)

    print(f"Test files in: {tmp}\n")

    # Process without wrapper — would crash on first bad file
    print("=" * 50)
    print("WITHOUT safe_extract (crashes):")
    print("=" * 50)
    for f in sorted(tmp.iterdir()):
        try:
            text = extract_text(str(f))
            print(f"  OK   {f.name}: {len(text)} chars")
        except Exception as e:
            print(f"  CRASH {f.name}: {type(e).__name__}: {e}"[:100])

    # Process with wrapper — never crashes
    print(f"\n{'=' * 50}")
    print("WITH safe_extract (never crashes):")
    print("=" * 50)
    results = process_folder(str(tmp))

    print(f"\n  OK: {len(results['ok'])} files")
    for r in results["ok"]:
        print(f"    {r['file']}: {r['chars']} chars")

    print(f"  FAILED: {len(results['failed'])} files")
    for name in results["failed"]:
        print(f"    {name}")
