import html
import re
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Article, ArticleRevision, ArticleFeedback, ArticleAttachment
from tickets.models import Ticket

def _normalize_rich_text(content):
    content = (content or '').strip()
    if not content:
        return ''

    # Repeatedly decode common escaped representations produced by editors / JSON serialization.
    for _ in range(3):
        previous = content

        # Convert double-escaped unicode sequences first (e.g. \\u003Cdiv\\u003E)
        content = re.sub(r'\\\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), content)

        # Convert single-escaped unicode sequences (e.g. \u003Cdiv\u003E)
        content = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), content)

        # Decode HTML entities like &lt;div&gt;
        content = html.unescape(content)

        # If it still looks like a JSON string, try to decode once
        if (content.startswith('"') and content.endswith('"')) or '\\u' in content:
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass

        if content == previous:
            break

    return content


def _get_role(user):
    try:
        return user.profile.role
    except AttributeError:
        return 'associate'


def _can_delete_article(user, article):
    """Manager, Consultant, Senior can delete any article. Others only their own."""
    role = _get_role(user)
    if role in ('manager', 'consultant', 'senior'):
        return True
    return article.created_by == user


@login_required
def article_list(request):
    articles = Article.objects.only('id','title','category','tags','content','updated_at','created_at').all()
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category')
    if q:
        articles = articles.filter(title__icontains=q) | articles.filter(content__icontains=q) | articles.filter(tags__icontains=q)
    if category:
        articles = articles.filter(category=category)

    for article in articles:
        normalized = _normalize_rich_text(article.content)
        preview = re.sub(r'<[^>]+>', ' ', normalized)
        preview = html.unescape(preview)
        preview = re.sub(r'\s+', ' ', preview).strip()
        article.preview_text = preview

    return render(request, 'knowledge/article_list.html', {
        'articles': articles,
        'category_choices': Article.CATEGORY_CHOICES,
        'q': q,
        'selected_category': category,
    })


@login_required
def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)
    user_feedback = None
    try:
        user_feedback = ArticleFeedback.objects.get(article=article, user=request.user)
    except ArticleFeedback.DoesNotExist:
        pass
    can_delete = _can_delete_article(request.user, article)
    return render(request, 'knowledge/article_detail.html', {
        'article': article,
        'decoded_content': _normalize_rich_text(article.content),
        'user_feedback': user_feedback,
        'can_delete': can_delete,
    })


@login_required
def article_delete(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if not _can_delete_article(request.user, article):
        messages.error(request, 'You do not have permission to delete this article.')
        return redirect('article_detail', pk=pk)
    if request.method == 'POST':
        title = article.title
        article.delete()
        messages.success(request, f'Article "{title}" deleted.')
        return redirect('article_list')
    return render(request, 'knowledge/article_confirm_delete.html', {'article': article})


@login_required
def article_history(request, pk):
    article = get_object_or_404(Article, pk=pk)
    revisions = article.revisions.all()
    return render(request, 'knowledge/article_history.html', {
        'article': article,
        'revisions': revisions,
    })


@login_required
def revision_detail(request, pk, rev_pk):
    article = get_object_or_404(Article, pk=pk)
    revision = get_object_or_404(ArticleRevision, pk=rev_pk, article=article)
    return render(request, 'knowledge/revision_detail.html', {
        'article': article,
        'revision': revision,
        'decoded_revision_content': _normalize_rich_text(revision.content),
    })


@login_required
def create_article(request, ticket_id=None):
    ticket = None
    if ticket_id:
        ticket = get_object_or_404(Ticket, pk=ticket_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = _normalize_rich_text(request.POST.get('content', ''))
        category = request.POST.get('category', 'other')
        tags = request.POST.get('tags', '').strip()
        source_id = request.POST.get('source_ticket')

        if title and content:
            article = Article.objects.create(
                title=title,
                content=content,
                category=category,
                tags=tags,
                created_by=request.user,
                last_modified_by=request.user,
                source_ticket_id=source_id if source_id else None,
            )
            ArticleRevision.objects.create(
                article=article,
                title=title,
                content=content,
                tags=tags,
                category=category,
                edited_by=request.user,
                revision_note='Initial version',
            )
            for f in request.FILES.getlist('attachments'):
                ArticleAttachment.objects.create(
                    article=article,
                    file=f,
                    filename=f.name,
                    uploaded_by=request.user,
                )
            messages.success(request, f'Article "{article.title}" saved to knowledge base.')
            return redirect('article_detail', pk=article.pk)

    return render(request, 'knowledge/create_article.html', {
        'ticket': ticket,
        'category_choices': Article.CATEGORY_CHOICES,
    })


@login_required
def edit_article(request, pk):
    article = get_object_or_404(Article, pk=pk)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = _normalize_rich_text(request.POST.get('content', ''))
        category = request.POST.get('category', article.category)
        tags = request.POST.get('tags', '').strip()
        revision_note = request.POST.get('revision_note', '').strip()

        if title and content:
            ArticleRevision.objects.create(
                article=article,
                title=article.title,
                content=article.content,
                tags=article.tags,
                category=article.category,
                edited_by=request.user,
                revision_note=revision_note or 'No note provided',
            )
            article.title = title
            article.content = content
            article.category = category
            article.tags = tags
            article.last_modified_by = request.user
            article.save()
            for f in request.FILES.getlist('attachments'):
                ArticleAttachment.objects.create(
                    article=article,
                    file=f,
                    filename=f.name,
                    uploaded_by=request.user,
                )
            delete_ids = request.POST.getlist('delete_attachments')
            if delete_ids:
                ArticleAttachment.objects.filter(pk__in=delete_ids, article=article).delete()
            messages.success(request, 'Article updated successfully.')
            return redirect('article_detail', pk=article.pk)

    return render(request, 'knowledge/edit_article.html', {
        'article': article,
        'decoded_content': _normalize_rich_text(article.content),
        'category_choices': Article.CATEGORY_CHOICES,
        'attachments': article.attachments.all(),
    })


@login_required
@require_POST
def article_feedback(request, pk):
    article = get_object_or_404(Article, pk=pk)
    helpful = request.POST.get('helpful') == 'true'

    feedback, created = ArticleFeedback.objects.get_or_create(
        article=article,
        user=request.user,
        defaults={'helpful': helpful}
    )

    if not created:
        if feedback.helpful and not helpful:
            article.helpful_count = max(0, article.helpful_count - 1)
            article.not_helpful_count += 1
        elif not feedback.helpful and helpful:
            article.not_helpful_count = max(0, article.not_helpful_count - 1)
            article.helpful_count += 1
        feedback.helpful = helpful
        feedback.save()
    else:
        if helpful:
            article.helpful_count += 1
        else:
            article.not_helpful_count += 1

    article.save()
    return JsonResponse({
        'helpful': article.helpful_count,
        'not_helpful': article.not_helpful_count,
        'user_vote': helpful,
    })
