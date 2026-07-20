import os, re

sites = {
    'rotcha': '/Users/twinssn/Projects/rotcha-blog/content/posts',
    'informationhot': '/Users/twinssn/Projects/informationhot-hugo/content/posts',
    'techpawz': '/Users/twinssn/Projects/techpawz-hugo/content/posts',
}

FM_END = '---'

def split_frontmatter(content):
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            return content[:end+3], content[end+3:]
    return '', content

issues = []

for site, base in sites.items():
    for root, dirs, files in os.walk(base):
        if 'index.md' in files:
            path = os.path.join(root, 'index.md')
            rel = os.path.relpath(path, base)
            with open(path, encoding='utf-8') as f:
                content = f.read()
            _, body = split_frontmatter(content)
            lines = body.split('\n')

            for i, line in enumerate(lines):
                stripped = line.strip()
                # malformed table: dash line without a proper header row above it
                if re.match(r'^[\-\|:\s]+$', stripped) and len(stripped) > 5:
                    if i > 0:
                        prev = lines[i-1].strip()
                        if not prev.startswith('|') or re.match(r'^[\-\|:\s]+$', prev):
                            issues.append((site, rel, i+1, 'malformed-table', stripped[:80]))

            # stray featureimage in body
            for m in re.finditer(r'^featureimage:\s*["\']*\s*["\']', body, re.MULTILINE):
                lineno = body[:m.start()].count('\n') + 1
                issues.append((site, rel, lineno, 'stray-featureimage', m.group()[:50]))

            # bare [text] with no URL
            for m in re.finditer(r'\[([^\]]+)\](?!\(|\'|")', body):
                text = m.group(1)
                if 'http' not in text and len(text) > 3:
                    lineno = body[:m.start()].count('\n') + 1
                    issues.append((site, rel, lineno, 'bare-link', text[:60]))

            # unclosed code fences
            if body.count('```') % 2 != 0:
                issues.append((site, rel, '-', 'unclosed-code-fence', ''))

print(f'Total issues: {len(issues)}\n')
for site, rel, line, kind, detail in issues:
    print(f'[{site}] {rel} L{line}: {kind} | {detail}')
