#!/usr/bin/env python3
"""
Fix residual HTML comment markers in published Hugo files.
Removes <!-- thumbnail: ... --> and <!-- image: ... --> comments.
"""

import sqlite3
import os
import re
from pathlib import Path

# Configuration
DB_PATH = "/Users/twinssn/Projects/5000/data/mc_chains.db"
HUGO_SITES = {
    "rotcha": "/Users/twinssn/Projects/rotcha-blog",
    "informationhot": "/Users/twinssn/Projects/informationhot-hugo",
    "techpawz": "/Users/twinssn/Projects/techpawz-hugo",
}

def get_published_posts():
    """Get all published posts with their file paths."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, chain_id, step, title, hugo_file_path, published_url
        FROM chain_posts
        WHERE status = 'published' 
        AND hugo_file_path IS NOT NULL 
        AND hugo_file_path != ''
        ORDER BY id, step
    """)
    
    posts = []
    for row in cursor.fetchall():
        posts.append(dict(row))
    
    conn.close()
    return posts

def has_markers(file_path):
    """Check if file contains the target markers."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            has_html = bool(re.search(r'<!--\s*(thumbnail|image)\s*:.*?-->', content))
            has_json = bool(re.search(r'```json\s*\n?\{.*?"image_type".*?\}', content, re.DOTALL))
            has_raw_json = bool(re.search(r'\n\{\s*\n\s*"image_type"\s*:.*?\}', content, re.DOTALL))
            has_cta = bool(re.search(r'<div[^>]*>.*?더\s*(?:깊이|자세히)\s*알아보기.*?</div>', content, re.DOTALL))
            return has_html or has_json or has_raw_json or has_cta
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

def remove_markers(file_path):
    """Remove the target markers from file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        cleaned = content

        # 1. HTML 주석 제거
        cleaned = re.sub(r'<!--\s*thumbnail\s*:.*?-->', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<!--\s*image\s*:.*?-->', '', cleaned, flags=re.DOTALL)

        # 2. 코드 펜스 JSON 메타데이터 제거
        def _strip_meta_json(m):
            block = m.group(0)
            if '"image_type"' in block or '"chart_type"' in block or '"image_keyword"' in block:
                return ''
            return block
        cleaned = re.sub(r'```json\s*\n?\{.*?\}\s*\n?```', _strip_meta_json, cleaned, flags=re.DOTALL)

        # 3. raw JSON 메타데이터 제거 (코드 펜스 없이 본문 끝)
        cleaned = re.sub(r'\n\{\s*\n\s*"image_type"\s*:.*?\}\s*$', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'\n\{\s*\n\s*"chart_type"\s*:.*?\}\s*$', '', cleaned, flags=re.DOTALL)

        # 4. CTA 블록 제거
        cleaned = re.sub(r'<div[^>]*>.*?더\s*(?:깊이|자세히)\s*알아보기.*?</div>', '', cleaned, flags=re.DOTALL)

        # 5. 연속 빈 줄 정리
        lines = cleaned.split('\n')
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            is_empty = line.strip() == ''
            if not (is_empty and prev_empty):
                cleaned_lines.append(line)
            prev_empty = is_empty

        cleaned = '\n'.join(cleaned_lines)

        if cleaned != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(cleaned)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    print("Finding published posts...")
    posts = get_published_posts()
    
    print(f"Found {len(posts)} published posts to check")
    
    fixed_count = 0
    checked_count = 0
    
    for post in posts:
        post_id = post['id']
        file_path = post['hugo_file_path']
        
        if not file_path or not os.path.exists(file_path):
            continue
            
        checked_count += 1
        
        if has_markers(file_path):
            print(f"Found markers in Post #{post_id} (Step {post['step']}): {file_path}")
            if remove_markers(file_path):
                print(f"  ✓ Fixed: Removed markers")
                fixed_count += 1
            else:
                print(f"  ✗ Failed to fix")
        # else:
        #     print(f"No markers in Post #{post_id}")
    
    print(f"\nSummary:")
    print(f"  Checked: {checked_count} files")
    print(f"  Fixed: {fixed_count} files")
    
    if fixed_count > 0:
        print("\nNow rebuilding affected Hugo sites...")
        # Rebuild each site that had fixes
        for site_name, site_path in HUGO_SITES.items():
            # Check if any files in this site were fixed
            site_fixed = False
            for post in posts:
                if post['hugo_file_path'] and post['hugo_file_path'].startswith(site_path):
                    # We'd need to track which were actually fixed - for simplicity, rebuild all that had markers
                    pass
            
            # For now, let's rebuild all three to be safe
            print(f"  Rebuilding {site_name}...")
            result = os.system(f"cd '{site_path}' && /opt/homebrew/bin/hugo --gc --minify")
            if result == 0:
                print(f"  ✓ {site_name} rebuilt successfully")
            else:
                print(f"  ✗ {site_name} rebuild failed (exit code {result})")
        
        print("\nDeployment note: After rebuilding, you'll need to run:")
        print("  wrangler pages deploy ./public --project-name [project-name]")
        print("For each site in their respective directories.")
    else:
        print("No files needed fixing.")

if __name__ == "__main__":
    main()