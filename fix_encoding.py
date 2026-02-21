import sys
import os

files_to_process = [
    (r"e:\co\Doxascope\EXPERIENCE\public\content\novel\ar\Prologue.md", r"e:\co\Audio-Formation\PROJECTS\DOXASCOPE-PILOT\01_TEXT\chapters\prologue_ar_utf8.txt"),
    (r"e:\co\Doxascope\EXPERIENCE\public\content\novel\en\Prologue.md", r"e:\co\Audio-Formation\PROJECTS\DOXASCOPE-PILOT\01_TEXT\chapters\prologue_en_utf8.txt"),
    (r"e:\co\Doxascope\EXPERIENCE\public\content\novel\ar\chapters\Chapter-1\Chapter01_Scene01.md", r"e:\co\Audio-Formation\PROJECTS\DOXASCOPE-PILOT\01_TEXT\chapters\ch01_s01_ar_utf8.txt")
]

for src, dst in files_to_process:
    with open(src, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Strip markdown headers/frontmatter - very naive approach for pilot
    lines = content.split('\n')
    extracted = []
    in_frontmatter = False
    for line in lines:
        if line.startswith('---'):
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter and not line.startswith('> **'):
            extracted.append(line)
            
    clean_text = '\n'.join(extracted).strip()
    
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(clean_text)
        
print("Successfully extracted and wrote UTF-8 text files.")
