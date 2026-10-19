from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import path, re_path
from django.views.static import serve

from routing.views import HealthView, TripView

urlpatterns = [
    path("api/health/", HealthView.as_view()),
    path("api/trips/", TripView.as_view()),
]


def _frontend(request, path=""):
    document_root = settings.FRONTEND_DIST
    target = document_root / path
    if path and target.is_file():
        return serve(request, path, document_root=document_root)
    return serve(request, "index.html", document_root=document_root)


def _dev_app(request):
    return HttpResponseRedirect("http://localhost:5173/")


if settings.FRONTEND_DIST.exists():
    urlpatterns.append(re_path(r"^(?P<path>.*)$", _frontend))
elif settings.DEBUG:
    urlpatterns.append(path("", _dev_app))
