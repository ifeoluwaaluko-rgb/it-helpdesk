"""
One-time fixer for knowledge article/revision content that was stored as unicode-escaped HTML.
Run: python fix_article_content.py
"""
import os
import django
import html

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'helpdesk.settings')
django.setup()

from knowledge.models import Article, ArticleRevision

def normalize(content):
    content = (content or '').strip()
    if not content:
        return ''
    if '\\u003C' in content or '\\u003E' in content or '\\u0026' in content:
        try:
            content = content.encode('utf-8').decode('unicode_escape')
        except Exception:
            pass
    try:
        content = html.unescape(content)
    except Exception:
        pass
    return content

fixed_articles = 0
for article in Article.objects.all():
    new_content = normalize(article.content)
    if new_content != article.content:
        article.content = new_content
        article.save(update_fields=['content', 'updated_at'])
        fixed_articles += 1

fixed_revisions = 0
for rev in ArticleRevision.objects.all():
    new_content = normalize(rev.content)
    if new_content != rev.content:
        rev.content = new_content
        rev.save(update_fields=['content'])
        fixed_revisions += 1

print(f"Fixed {fixed_articles} articles and {fixed_revisions} revisions.")
