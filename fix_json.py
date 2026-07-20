#!/usr/bin/env python3
"""Fix JSON metadata in DB and files - handles missing closing backticks."""

import sqlite3
import re
import os

DB_PATH = "/Users/twinssn/Projects/5000/data/mc_chains.db"

def fix_json_in_text(text):
    """Remove JSON metadata blocks from text."""
    cleaned = text
    
    # Pattern 1: ```json ... ``` (with closing backticks)
    cleaned = re.sub(r'```json\s*\n?\{.*?\}\s*\n?```', '', cleaned, flags=re.DOTALL)
    
    # Pattern 2: ```json ... } (without closing backticks)
    cleaned = re.sub(r'```json\s*\n?\{.*?\}\s*$', '', cleaned, flags=re.DOTALL)
    
    # Pattern 3: raw JSON at end (no code fence)
    cleaned = re.sub(r'\n\{\s*\n\s*"image_type"\s*:.*?\}\s*$', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'\n\{\s*\n\s*"chart_type"\s*:.*?\}\s*$', '', cleaned, flags=re.DOTALL)
    
    # Clean up multiple blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    posts = conn.execute('''
        SELECT id, chain_id, step, title, draft_md, hugo_file_path
        FROM chain_posts
        WHERE draft_md LIKE '%image_type%'
        OR draft_md LIKE '%chart_type%'
        ORDER BY id
    ''').fetchall()
    
    print(f"Found {len(posts)} posts with JSON metadata")
    
    fixed_count = 0
    for p in posts:
        draft = p['draft_md'] or ''
        original_len = len(draft)
        
        cleaned = fix_json_in_text(draft)
        
        if cleaned != draft:
            conn.execute('UPDATE chain_posts SET draft_md = ? WHERE id = ?', (cleaned, p['id']))
            fixed_count += 1
            print(f"  Fixed Post #{p['id']} ({p['title'][:30]}...) - {original_len} -> {len(cleaned)}")
        
        # Fix file on disk too
        hugo_path = p['hugo_file_path']
        if hugo_path and os.path.exists(hugo_path):
            with open(hugo_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            file_cleaned = fix_json_in_text(file_content)
            
            if file_cleaned != file_content:
                with open(hugo_path, 'w', encoding='utf-8') as f:
                    f.write(file_cleaned)
                print(f"    -> File fixed: {hugo_path}")
    
    conn.commit()
    conn.close()
    print(f"\nDone: {fixed_count} posts fixed")

if __name__ == "__main__":
    main()