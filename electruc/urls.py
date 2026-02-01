"""electruc URL Configuration."""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from portal.forms import ElectrucAuthenticationForm
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("portal.urls")),
    path("connexion/", auth_views.LoginView.as_view(authentication_form=ElectrucAuthenticationForm), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
]

# Serve uploaded files in development only.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
