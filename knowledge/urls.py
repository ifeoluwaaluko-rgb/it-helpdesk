from django.urls import path
from . import views

urlpatterns = [
    path('knowledge/', views.article_list, name='article_list'),
    path('knowledge/create/', views.create_article, name='create_article'),
    path('knowledge/<int:pk>/', views.article_detail, name='article_detail'),
    path('knowledge/<int:pk>/edit/', views.edit_article, name='edit_article'),
    path('knowledge/<int:pk>/delete/', views.article_delete, name='article_delete'),
    path('knowledge/<int:pk>/history/', views.article_history, name='article_history'),
    path('knowledge/<int:pk>/history/<int:rev_pk>/', views.revision_detail, name='revision_detail'),
    path('knowledge/<int:pk>/feedback/', views.article_feedback, name='article_feedback'),
    path('knowledge/create/<int:ticket_id>/', views.create_article, name='create_article_from_ticket'),
]
