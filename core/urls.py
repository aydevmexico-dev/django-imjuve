"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('api/buscar/', views.buscar_api, name='buscar_api'),
    path('', include('accounts.urls')),   # /registro/, /login/, /logout/
    path('', include('states.urls')),     # /api/geo/municipios/, /api/geo/colonias/
    path('panel/', include('core.panel_urls')),  # panel de administración personalizado
    path('portal/', include('core.youth_urls')),  # portal de jóvenes (rol GENERAL)
    path('admin/', admin.site.urls),
]

# En desarrollo servimos los archivos subidos (MEDIA). En producción los entrega el
# almacenamiento configurado / WhiteNoise; aquí solo aplica bajo DEBUG.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
