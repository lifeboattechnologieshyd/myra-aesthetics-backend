
from rest_framework.response import Response


class CustomResponse:

    @staticmethod
    def success(message="Success.", data=None):

        return Response({
            "success": True,
            "message": message,
            "data": data
        })

    @staticmethod
    def error(message="Something went wrong.", errors=None):

        return Response({
            "success": False,
            "message": message,
            "data": None,
            "errors": errors
        }, status=400)
