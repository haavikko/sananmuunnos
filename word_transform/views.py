from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError

from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .transform import transform_words, WordTransformException, WordTransformLogicError


@csrf_exempt
@require_http_methods(["POST"])
def word_transform(request):
    '''
    Main end point of the application.

    :param request: must contain utf-8 encoded json string in the request.body
    :return: HttpResponse
    '''
    try:
        request_body_unicode = request.body.decode('utf-8', 'strict')
    except UnicodeDecodeError:
        return HttpResponseBadRequest('utf-8 formatted input string required')

    try:
        response_data = transform_words(request_body_unicode)
    except WordTransformLogicError as e:
        return HttpResponseServerError('Could not process the request')
    except WordTransformException as e:
        return HttpResponseBadRequest('Invalid request')
    except Exception as e:
        return HttpResponseServerError('Server error')

    return HttpResponse(response_data, content_type='application/json')
