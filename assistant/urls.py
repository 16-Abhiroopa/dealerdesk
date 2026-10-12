from django.urls import path
from assistant.views import ChatAssistantView, ChatSessionHistoryView

urlpatterns = [
    path("assistant/chat/", ChatAssistantView.as_view(), name="assistant-chat"),
    path("assistant/history/", ChatSessionHistoryView.as_view(), name="assistant-history"),
]
