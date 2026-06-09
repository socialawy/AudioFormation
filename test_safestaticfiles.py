from pathlib import Path


def test_path(path):
    if path is None:
        print("Path is None: BLOCKED")
        return

    p = Path(str(path).lower())

    is_hidden = any(
        part.startswith(".") and part not in (".", "..") for part in p.parts
    )
    if "00_config" in p.parts or is_hidden:
        print(f"{path}: BLOCKED")
    else:
        print(f"{path}: ALLOWED")


test_path("00_CONFIG/secrets.json")
test_path("my_project/.env")
test_path(".git/config")
test_path("my_project/.hidden_dir/file.txt")
test_path("valid_file.txt")
test_path(None)
