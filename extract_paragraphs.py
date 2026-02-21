import os

source_file = r"e:\co\Audio-Formation\PROJECTS\DOXASCOPE-PILOT\01_TEXT\chapters\prologue_ar_utf8.txt"
staging_dir = r"e:\co\Audio-Formation\PROJECTS\DOXASCOPE_PILOT_01\01_TEXT\staging"

os.makedirs(staging_dir, exist_ok=True)

with open(source_file, 'r', encoding='utf-8') as f:
    text = f.read()

paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

for i, p in enumerate(paragraphs, start=1):
    file_path = os.path.join(staging_dir, f"ar_prologue_p{i:02d}.txt")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(p)
        
print(f"Successfully extracted {len(paragraphs)} paragraphs into {staging_dir}")
