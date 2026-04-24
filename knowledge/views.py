import html
import re
import json
from html.parser import HTMLParser
from urllib.parse import urlparse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Article, ArticleRevision, ArticleFeedback, ArticleAttachment
from .forms import ArticleCreateForm, ArticleEditForm, validate_knowledge_attachments
from tickets.permissions import can_delete_edit, can_manage_knowledge, get_role
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
            except Exception:
                pass

        if content == previous:
            break

    return content


def _get_role(user):
    return get_role(user)


class _SafeHtmlSanitizer(HTMLParser):
    ALLOWED_TAGS = {
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li',
        'h2', 'h3', 'blockquote', 'code', 'pre', 'a', 'img',
    }
    VOID_TAGS = {'br', 'img'}
    ALLOWED_ATTRS = {
        'a': {'href', 'title', 'target', 'rel'},
        'img': {'src', 'alt'},
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.ALLOWED_TAGS:
            return
        cleaned = []
        for key, value in attrs:
            if key not in self.ALLOWED_ATTRS.get(tag, set()):
                continue
            value = self._clean_attr(tag, key, value)
            if value is None:
                continue
            cleaned.append((key, value))
        attr_text = ''.join(f' {key}="{html.escape(value, quote=True)}"' for key, value in cleaned)
        self.parts.append(f'<{tag}{attr_text}>')

    def handle_endtag(self, tag):
        if tag in self.ALLOWED_TAGS and tag not in self.VOID_TAGS:
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        self.parts.append(html.escape(data))

    def handle_entityref(self, name):
        self.parts.append(f'&{name};')

    def handle_charref(self, name):
        self.parts.append(f'&#{name};')

    def _clean_attr(self, tag, key, value):
        value = (value or '').strip()
        if not value:
            return None
        if tag == 'a' and key == 'href':
            parsed = urlparse(value)
            if parsed.scheme and parsed.scheme not in {'http', 'https', 'mailto'}:
                return None
        if tag == 'img' and key == 'src':
            if value.startswith('/media/'):
                return value
            if re.match(r'^data:image\/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+$', value):
                return value
            return None
        if tag == 'a' and key == 'target':
            return '_blank' if value == '_blank' else None
        if tag == 'a' and key == 'rel':
            return 'noopener noreferrer'
        return value


def _sanitize_rich_text(content):
    parser = _SafeHtmlSanitizer()
    parser.feed(content or '')
    parser.close()
    return ''.join(parser.parts)


def _can_delete_article(user, article):
    """Manager, Consultant, Senior can delete any article. Others only their own."""
    if can_delete_edit(user):
        return True
    return article.created_by == user


@login_required
def article_list(request):
    articles = Article.objects.all()
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
        'can_create': can_manage_knowledge(request.user),
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
        'decoded_content': _sanitize_rich_text(_normalize_rich_text(article.content)),
        'user_feedback': user_feedback,
        'can_delete': can_delete,
        'can_edit': can_manage_knowledge(request.user),
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
        'decoded_revision_content': _sanitize_rich_text(_normalize_rich_text(revision.content)),
    })


@login_required
def create_article(request, ticket_id=None):
    if not can_manage_knowledge(request.user):
        messages.error(request, 'Only helpdesk staff can create knowledge articles.')
        return redirect('article_list')

    ticket = None
    if ticket_id:
        ticket = get_object_or_404(Ticket, pk=ticket_id)

    initial = {
        'title': ticket.title if ticket else '',
        'category': ticket.category if ticket else 'other',
        'content': f"<p><strong>Problem:</strong> {ticket.description}</p><p><strong>Solution:</strong></p>" if ticket else '',
        'source_ticket': ticket.pk if ticket else '',
    }
    form = ArticleCreateForm(request.POST or None, initial=initial)

    if request.method == 'POST':
        if form.is_valid():
            try:
                attachments = request.FILES.getlist('attachments')
                validate_knowledge_attachments(attachments)
                safe_content = _sanitize_rich_text(_normalize_rich_text(form.cleaned_data['content']))
                article = Article.objects.create(
                    title=form.cleaned_data['title'],
                    content=safe_content,
                    category=form.cleaned_data['category'],
                    tags=form.cleaned_data['tags'],
                    created_by=request.user,
                    last_modified_by=request.user,
                    source_ticket_id=form.cleaned_data.get('source_ticket') or None,
                )
                ArticleRevision.objects.create(
                    article=article,
                    title=form.cleaned_data['title'],
                    content=safe_content,
                    tags=form.cleaned_data['tags'],
                    category=form.cleaned_data['category'],
                    edited_by=request.user,
                    revision_note='Initial version',
                )
                for uploaded in attachments:
                    ArticleAttachment.objects.create(
                        article=article,
                        file=uploaded,
                        filename=uploaded.name,
                        uploaded_by=request.user,
                    )
                messages.success(request, f'Article "{article.title}" saved to knowledge base.')
                return redirect('article_detail', pk=article.pk)
            except Exception as exc:
                messages.error(request, f'Could not save article: {exc}')
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

    return render(request, 'knowledge/create_article.html', {
        'ticket': ticket,
        'form': form,
        'editor_content': form['content'].value() or '',
        'category_choices': Article.CATEGORY_CHOICES,
    })


@login_required
def edit_article(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if not can_manage_knowledge(request.user):
        messages.error(request, 'Only helpdesk staff can edit knowledge articles.')
        return redirect('article_detail', pk=pk)

    attachments = article.attachments.all()
    initial = {
        'title': article.title,
        'content': article.content,
        'category': article.category,
        'tags': article.tags,
        'revision_note': '',
        'delete_attachments': [],
    }
    form = ArticleEditForm(request.POST or None, attachments=attachments, initial=initial)

    if request.method == 'POST':
        if form.is_valid():
            try:
                uploaded_files = request.FILES.getlist('attachments')
                validate_knowledge_attachments(uploaded_files)
                content = _sanitize_rich_text(_normalize_rich_text(form.cleaned_data['content']))
                ArticleRevision.objects.create(
                    article=article,
                    title=article.title,
                    content=article.content,
                    tags=article.tags,
                    category=article.category,
                    edited_by=request.user,
                    revision_note=form.cleaned_data['revision_note'] or 'No note provided',
                )
                article.title = form.cleaned_data['title']
                article.content = content
                article.category = form.cleaned_data['category']
                article.tags = form.cleaned_data['tags']
                article.last_modified_by = request.user
                article.save()
                for uploaded in uploaded_files:
                    ArticleAttachment.objects.create(
                        article=article,
                        file=uploaded,
                        filename=uploaded.name,
                        uploaded_by=request.user,
                    )
                delete_ids = form.cleaned_data.get('delete_attachments') or []
                if delete_ids:
                    ArticleAttachment.objects.filter(pk__in=delete_ids, article=article).delete()
                messages.success(request, 'Article updated successfully.')
                return redirect('article_detail', pk=article.pk)
            except Exception as exc:
                messages.error(request, f'Could not update article: {exc}')
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

    return render(request, 'knowledge/edit_article.html', {
        'article': article,
        'form': form,
        'editor_content': form['content'].value() or article.content,
        'category_choices': Article.CATEGORY_CHOICES,
        'attachments': attachments,
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
