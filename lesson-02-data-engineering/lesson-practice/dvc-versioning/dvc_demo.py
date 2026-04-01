import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime

STORAGE_DIR = Path("dvc_storage")
TRACKING_DIR = Path("dvc_tracking")


def init():
    STORAGE_DIR.mkdir(exist_ok=True)
    TRACKING_DIR.mkdir(exist_ok=True)
    print("Initialized DVC-like storage")


def hash_file(file_path: Path) -> str:
    return hashlib.md5(file_path.read_bytes()).hexdigest()


def add(file_path: str) -> str:
    file_path = Path(file_path)
    file_hash = hash_file(file_path)

    stored = STORAGE_DIR / file_hash
    shutil.copy2(file_path, stored)

    meta = {
        "original_name": file_path.name,
        "hash": file_hash,
        "size_bytes": file_path.stat().st_size,
        "added_at": datetime.now().isoformat(),
    }
    tracking_file = TRACKING_DIR / f"{file_path.name}.dvc"
    tracking_file.write_text(json.dumps(meta, indent=2))

    print(f"  add: {file_path.name} -> {file_hash[:8]}... ({meta['size_bytes']:,} bytes)")
    print(f"  tracking: {tracking_file.name} (this goes to git)")
    print(f"  storage:  {stored.name} (this goes to remote storage)")
    return file_hash


def checkout(dvc_file: str):
    meta = json.loads(Path(dvc_file).read_text())
    stored = STORAGE_DIR / meta["hash"]

    if not stored.exists():
        print(f"  ERROR: {meta['hash'][:8]}... not in storage. Run 'dvc pull' first.")
        return

    shutil.copy2(stored, meta["original_name"])
    print(f"  checkout: {meta['original_name']} restored from {meta['hash'][:8]}...")


def log():
    print(f"\n{'File':<25} {'Hash':<12} {'Size':<12} {'Date'}")
    print("-" * 65)
    for f in sorted(TRACKING_DIR.glob("*.dvc")):
        meta = json.loads(f.read_text())
        print(f"  {meta['original_name']:<23} {meta['hash'][:10]:<12} "
              f"{meta['size_bytes']:>8,} B   {meta['added_at'][:19]}")


if __name__ == "__main__":
    shutil.rmtree(STORAGE_DIR, ignore_errors=True)
    shutil.rmtree(TRACKING_DIR, ignore_errors=True)

    # Step 1: Init
    print("=" * 50)
    print("STEP 1: Init")
    print("=" * 50)
    init()

    # Step 2: Create dataset v1
    print(f"\n{'=' * 50}")
    print("STEP 2: Dataset v1 — initial data")
    print("=" * 50)
    dataset = Path("dataset.csv")
    dataset.write_text("id,name,value\n1,Alice,100\n2,Bob,200\n3,Charlie,300\n")
    add("dataset.csv")

    # Step 3: Update dataset v2
    print(f"\n{'=' * 50}")
    print("STEP 3: Dataset v2 — added rows + fix")
    print("=" * 50)
    dataset.write_text("id,name,value\n1,Alice,150\n2,Bob,200\n3,Charlie,300\n4,Diana,400\n5,Eve,500\n")
    add("dataset.csv")

    # Step 4: Model file
    print(f"\n{'=' * 50}")
    print("STEP 4: Track model.pkl (large file)")
    print("=" * 50)
    model = Path("model.pkl")
    model.write_bytes(b"\x80\x05" + b"\x00" * 1000 + b"fake model weights v1")
    add("model.pkl")

    # Step 5: Show versions
    print(f"\n{'=' * 50}")
    print("STEP 5: Version log")
    print("=" * 50)
    log()

    # Step 6: Demonstrate checkout
    print(f"\n{'=' * 50}")
    print("STEP 6: Checkout — restore from hash")
    print("=" * 50)
    dataset.unlink()
    print(f"  Deleted {dataset.name}")
    checkout("dvc_tracking/dataset.csv.dvc")
    print(f"  Restored content: {dataset.read_text()[:80]}...")

    # Step 7: What goes where
    print(f"\n{'=' * 50}")
    print("STEP 7: Git vs DVC storage")
    print("=" * 50)
    print(f"\n  Git repo (small .dvc files):")
    for f in sorted(TRACKING_DIR.glob("*.dvc")):
        print(f"    {f.name:<25} {f.stat().st_size:>6} bytes")

    print(f"\n  DVC storage (actual data):")
    for f in sorted(STORAGE_DIR.iterdir()):
        print(f"    {f.name:<35} {f.stat().st_size:>6} bytes")

    print(f"\n  -> .dvc files go to Git (tiny)")
    print(f"  -> actual data goes to S3/GCS/Azure (large)")
    print(f"  -> git commit tracks WHICH version, DVC stores the DATA")

    # Cleanup
    shutil.rmtree(STORAGE_DIR)
    shutil.rmtree(TRACKING_DIR)
    dataset.unlink(missing_ok=True)
    model.unlink(missing_ok=True)
