"""
Management command to fix knowledge base article/revision content
that was stored as unicode-escaped or double-escaped HTML.

Usage:
    python manage.py fix_article_content
    python manage.py fix_article_content --dry-run
"""
import html
import re
from django.core.management.base import BaseCommand
from knowledge.models import Article, ArticleRevision


def normalize(content):
    content = (content or '').strip()
    if not content:
        return ''
    for _ in range(3):
        previous = content
        # Double-escaped unicode  e.g. \\u003C
        content = re.sub(r'\\\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), content)
        # Single-escaped unicode  e.g. \u003C
        content = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), content)
        # HTML entities  e.g. &lt; &gt;
        content = html.unescape(content)
        if content == previous:
            break
    return content


class Command(BaseCommand):
    help = 'Fix unicode-escaped HTML in knowledge base article and revision content'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without saving anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fixed_articles = 0
        fixed_revisions = 0

        for article in Article.objects.all():
            new_content = normalize(article.content)
            if new_content != article.content:
                if not dry_run:
                    article.content = new_content
                    article.save(update_fields=['content', 'updated_at'])
                fixed_articles += 1
                self.stdout.write(f"  {'[DRY RUN] ' if dry_run else ''}Fixed article #{article.pk}: {article.title[:60]}")

        for rev in ArticleRevision.objects.all():
            new_content = normalize(rev.content)
            if new_content != rev.content:
                if not dry_run:
                    rev.content = new_content
                    rev.save(update_fields=['content'])
                fixed_revisions += 1

        status = '[DRY RUN] Would fix' if dry_run else 'Fixed'
        self.stdout.write(self.style.SUCCESS(
            f"{status} {fixed_articles} articles and {fixed_revisions} revisions."
        ))
