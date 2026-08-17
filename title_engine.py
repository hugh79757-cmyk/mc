import re
BAD = ('-hugo','site:','blog:','project:','hook:','fact sheet:','return exactly')
def normalize_title(s):
    s = re.sub(r'\s+', ' ', (s or '').strip())
    s = re.sub(r'\s*[-|]\s*', ' - ', s)
    return s.strip(' -:,.?')
def title_issues(title, keyword=''):
    s = normalize_title(title); lo = s.lower(); out = []
    if not s: out.append('empty_title')
    if len(s) < 12: out.append('too_short')
    if len(s) > 60: out.append('too_long')
    if any(x in lo for x in BAD): out.append('blocked_pattern')
    if keyword and keyword not in s: out.append('missing_topic')
    return out
def score_title(title, keyword):
    s = normalize_title(title); issues = title_issues(s, keyword)
    if not s or len(s) < 12 or len(s) > 60: return -100, issues
    score = 50 + (30 if keyword and keyword in s else 0)
    if re.search(r'(recommend|compare|choice|price|use|battery|ingredient|effect)', s, re.I): score += 10
    score -= 20 * len(issues)
    return score, issues
def choose_best(candidates, keyword, fallback=''):
    best, bs, bi = normalize_title(fallback), -100, ['no_valid_candidate']
    for c in candidates:
        sc, issues = score_title(c, keyword)
        if sc > bs and not issues:
            best, bs, bi = normalize_title(c), sc, issues
    return best, bs, bi
