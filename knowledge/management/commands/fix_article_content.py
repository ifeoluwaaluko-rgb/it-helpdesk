
import html
import re

from django.core.management.base import BaseCommand

from knowledge.models import Article, ArticleRevision


def normalize(content):
    content = (content or '').strip()
    if not content:
        return ''
    if '\\u003C' in content or '\\u003E' in content or '\\u0026' in content:
        try:
            content = content.encode('utf-8').decode('unicode_escape')
        except UnicodeDecodeError:
            pass
    return html.unescape(content)


class Command(BaseCommand):
    help = 'Normalize escaped article and revision rich-text content.'

    def handle(self, *args, **options):
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

        self.stdout.write(self.style.SUCCESS(f"Fixed {fixed_articles} articles and {fixed_revisions} revisions."))
