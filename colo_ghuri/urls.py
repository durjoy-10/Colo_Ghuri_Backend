from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

def health_check(request):
    return HttpResponse("OK", status=200)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health-check'),

    path('api/users/', include('users.urls')),
    path('api/destinations/', include('destinations.urls')),
    path('api/tours/', include('tours.urls')),
    path('api/trips/', include('trips.urls')),
    path('api/guides/', include('guides.urls')),

    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),

    # Chatbot API
    path('api/chatbot/', include('chatbot.urls')),
    
    
    path('api/engagement/', include('engagement.urls')),
    
    path('api/operations/', include('operations.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
