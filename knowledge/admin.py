from django.contrib import admin
from .models import Article, ArticleRevision, ArticleFeedback


class RevisionInline(admin.TabularInline):
    model = ArticleRevision
    extra = 0
    readonly_fields = ['edited_by', 'edited_at', 'revision_note']


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'created_by', 'last_modified_by', 'created_at', 'helpful_count', 'not_helpful_count']
    list_filter = ['category']
    search_fields = ['title', 'content', 'tags']
    inlines = [RevisionInline]


@admin.register(ArticleRevision)
class RevisionAdmin(admin.ModelAdmin):
    list_display = ['article', 'edited_by', 'edited_at', 'revision_note']
    readonly_fields = ['edited_at']
