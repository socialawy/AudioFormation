import sys
from pathlib import Path

# Add the src directory to Python path so we can import audioformation
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from audioformation.utils.arabic import diacritize_file

staging_dir = Path("PROJECTS/DOXASCOPE_PILOT_01/01_TEXT/staging")

print(f"Searching for .txt files in {staging_dir}")
txt_files = list(staging_dir.glob("ar_prologue_p*.txt"))
print(f"Found {len(txt_files)} files. Starting diacritization pass...")

success_count = 0
for txt_file in sorted(txt_files):
    # We only want to process the raw, un-diacritized ones (ignore any already processed ones)
    if ".diacritized." in txt_file.name:
        continue
        
    print(f"Processing: {txt_file.name}")
    try:
        result = diacritize_file(txt_file, engine="mishkal")
        print(f"  -> Level before: {result.level_before:.1%}")
        print(f"  -> Level after:  {result.level_after:.1%}")
        if result.warnings:
            for w in result.warnings:
                print(f"  -> WARNING: {w}")
        success_count += 1
    except Exception as e:
        print(f"  -> Error processing {txt_file.name}: {e}")

print(f"\nSuccessfully generated {success_count} .diacritized.txt files!")
