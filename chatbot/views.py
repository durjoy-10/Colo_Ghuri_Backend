from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from .serializers import ChatbotMessageSerializer
from .services.hybrid_agent import HybridColoGhuriChatbotAgent


class ChatbotMessageView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = ChatbotMessageSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'reply': 'Sorry, I could not understand the request format.',
                    'errors': serializer.errors,
                    'cards': [],
                    'quick_replies': [],
                    'requires_confirmation': False,
                    'pending_action': None,
                    'nlu': None
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        message = serializer.validated_data.get('message', '')
        confirmed_action = serializer.validated_data.get('confirmed_action')

        agent = HybridColoGhuriChatbotAgent(user=request.user, request=request)
        result = agent.handle(message=message, confirmed_action=confirmed_action)

        return Response(result, status=status.HTTP_200_OK)