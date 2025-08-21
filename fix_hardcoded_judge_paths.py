#!/usr/bin/env python3
"""
Script to systematically fix hardcoded judge cache paths in tests.
This prevents future architecture changes from breaking tests.
"""

import re
from pathlib import Path


def fix_hardcoded_paths():
    """Fix all hardcoded judge cache paths in test files."""
    test_files = [
        "tests/test_cache_id_consistency.py",
        "tests/test_cross_stage_cache_consistency.py",
        "tests/test_ethical_tournaments.py",
        "tests/test_pipeline_resume_behavior.py",
        "tests/test_streamlit_app.py",
        "tests/test_tournament_generation_fix.py",
        "tests/test_tournament_hang.py",
        "tests/test_tournament_pipeline_bug.py",
    ]

    patterns_to_fix = [
        # Pattern: Path("data/tournaments")
        (r'Path\("data/tournaments"\)', "get_judge_cache_dir()"),
        # Pattern: "data/tournaments/"
        (r'"data/tournaments/"', 'str(get_judge_cache_dir()) + "/"'),
        # Pattern: data/tournaments/ in f-strings
        (r"data/tournaments/", "{get_judge_cache_dir()}/"),
        # Pattern: list(Path("data/tournaments").
        (r'list\(Path\("data/tournaments"\)', "list(get_judge_cache_dir()"),
    ]

    for test_file in test_files:
        if not Path(test_file).exists():
            print(f"⚠️ File not found: {test_file}")
            continue

        print(f"🔧 Fixing {test_file}")

        with open(test_file) as f:
            content = f.read()

        # Add import if not present
        if "from .test_utils_judge_cache import get_judge_cache_dir" not in content:
            # Find the imports section
            lines = content.split("\n")
            import_inserted = False

            for i, line in enumerate(lines):
                if line.startswith("import ") or line.startswith("from "):
                    # Insert after existing imports
                    continue
                elif not import_inserted and (line.startswith("class ") or line.startswith("def ")):
                    # Insert before first class/function
                    lines.insert(i, "from .test_utils_judge_cache import get_judge_cache_dir")
                    lines.insert(i, "")
                    import_inserted = True
                    break

            if not import_inserted:
                # Insert at beginning after docstring
                for i, line in enumerate(lines):
                    if '"""' in line and i > 0:
                        # Find end of docstring
                        if line.count('"""') == 2:
                            lines.insert(i + 1, "")
                            lines.insert(i + 2, "from .test_utils_judge_cache import get_judge_cache_dir")
                            break
                        else:
                            # Multi-line docstring
                            for j in range(i + 1, len(lines)):
                                if '"""' in lines[j]:
                                    lines.insert(j + 1, "")
                                    lines.insert(j + 2, "from .test_utils_judge_cache import get_judge_cache_dir")
                                    import_inserted = True
                                    break
                        break

            content = "\n".join(lines)

        # Apply pattern fixes
        original_content = content
        for pattern, replacement in patterns_to_fix:
            # Only replace patterns that don't involve tournaments.json
            matches = re.findall(pattern, content)
            for match in matches:
                if "tournaments.json" not in match:
                    content = re.sub(pattern, replacement, content)

        # Write back if changed
        if content != original_content:
            with open(test_file, "w") as f:
                f.write(content)
            print(f"✅ Fixed {test_file}")
        else:
            print(f"ℹ️ No changes needed for {test_file}")


if __name__ == "__main__":
    fix_hardcoded_paths()
