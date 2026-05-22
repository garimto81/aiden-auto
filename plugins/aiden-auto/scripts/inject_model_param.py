#!/usr/bin/env python3
"""Phase 1D - Agent() 호출에 model=plan["<base>"] 일괄 주입.

Usage:
  python inject_model_param.py          # dry-run
  python inject_model_param.py --apply  # actually modify
"""

import re
import sys
from pathlib import Path

REF_DIR = Path(r"C:\claude\plugins\aiden-auto\references")


def find_agent_calls(content):
    """Find all Agent(...) calls with balanced parens. Returns [(start, end, block)]."""
    results = []
    for match in re.finditer(r'Agent\s*\(', content):
        start = match.start()
        i = match.end()
        depth = 1
        while i < len(content) and depth > 0:
            ch = content[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            i += 1
        end = i
        results.append((start, end, content[start:end]))
    return results


def get_base_name(subagent_type):
    """Strip -high/-low/-medium tier suffix."""
    return re.sub(r'-(high|low|medium)$', '', subagent_type)


def inject_model_param(content):
    """Inject model=plan["..."] into Agent() calls missing it."""
    agent_calls = find_agent_calls(content)
    if not agent_calls:
        return content, 0

    injections = 0
    # Process in reverse so earlier offsets stay valid
    for start, end, block in reversed(agent_calls):
        st_match = re.search(r'subagent_type\s*=\s*"([^"]+)"', block)
        if not st_match:
            continue

        subagent_type = st_match.group(1)

        # Skip if already has model=
        if re.search(r'\bmodel\s*=', block):
            continue

        base = get_base_name(subagent_type)

        # Locate end of 'subagent_type="..."(,)?' inside the block
        st_end_match = re.search(r'subagent_type\s*=\s*"[^"]+"\s*,?', block)
        if not st_end_match:
            continue

        insert_offset = st_end_match.end()

        # Inspect what comes after to preserve indentation/newline
        after_st = block[insert_offset:]
        indent_match = re.match(r'\s*\n([ \t]*)', after_st)
        if indent_match:
            indent = indent_match.group(1)
            injection = f'\n{indent}model=plan["{base}"],'
        else:
            injection = f' model=plan["{base}"],'

        absolute_insert = start + insert_offset
        content = content[:absolute_insert] + injection + content[absolute_insert:]
        injections += 1

    return content, injections


def main():
    apply = '--apply' in sys.argv

    files_changed = 0
    total_injections = 0
    file_details = []

    for md_file in sorted(REF_DIR.rglob('*.md')):
        original = md_file.read_text(encoding='utf-8')
        modified, injections = inject_model_param(original)

        if injections > 0:
            files_changed += 1
            total_injections += injections
            file_details.append((str(md_file.relative_to(REF_DIR)), injections))

            if apply:
                md_file.write_text(modified, encoding='utf-8')

    mode = 'APPLY' if apply else 'DRY-RUN'
    print(f'[{mode}] Files changed: {files_changed}')
    print(f'[{mode}] Total injections: {total_injections}')
    print('')
    print('Per-file injection count:')
    for name, count in sorted(file_details, key=lambda x: -x[1]):
        print(f'  {name}: {count}')


if __name__ == '__main__':
    main()
