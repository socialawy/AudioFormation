from pathlib import Path
from src.audioformation.utils.security import validate_path_within

p = Path("src/audioformation/utils/security.py")
r = Path("src/audioformation")

print(validate_path_within(p, r))

# Test with our new logic
def validate_new(path: Path, root: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
        return resolved_path.is_relative_to(resolved_root)
    except (TypeError, ValueError, RuntimeError):
        return False

print(validate_new(p, r))
