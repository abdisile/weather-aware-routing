import logging

from django.conf import settings
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from routing.providers import AppServices, TripError
from routing.trip import build_trip, parse_request

logger = logging.getLogger(__name__)


class HealthView(APIView):
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class TripView(APIView):
    def post(self, request: Request) -> Response:
        try:
            trip_request = parse_request(request.data)
            services = AppServices(ors_api_key=settings.ORS_API_KEY)
            payload = build_trip(
                trip_request,
                geocoder=services,
                router=services,
                forecast=services.weather,
            )
        except TripError as exc:
            return Response({"error": str(exc)}, status=exc.status)
        except Exception:
            logger.exception("Trip scoring failed")
            return Response(
                {"error": "Something went wrong while scoring the trip."},
                status=500,
            )
        return Response(payload)
