from django.urls import path
from .views import ChatbotMessageView

urlpatterns = [
    path('message/', ChatbotMessageView.as_view(), name='chatbot-message'),
]