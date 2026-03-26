from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from asgiref.sync import sync_to_async


async def home(request: HttpRequest) -> HttpResponse:
    return await sync_to_async(render, thread_sensitive=True)(request, "core/home.html")


async def healthcheck(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})
