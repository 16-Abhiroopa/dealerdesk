from django.urls import path
from assistant.views import ChatAssistantView

urlpatterns = [
    path("assistant/chat/", ChatAssistantView.as_view(), name="assistant-chat"),
]
