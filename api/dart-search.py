from http.server import BaseHTTPRequestHandler
import urllib.parse, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.dart import search_disclosure
from lib.validation import (
    parse_int_range,
    validate_corp_code,
    validate_dart_pblntf_ty,
    validate_date_range,
)
from lib.http_utils import (
    api_error_payload,
    api_success_payload,
    log_exception,
    send_api_error,
    send_json_response,
    send_options_response,
)

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        send_options_response(self)

    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        corp_code = qs.get('corp_code', [''])[0].strip()
        bgn_de = qs.get('bgn_de', [''])[0].strip()
        end_de = qs.get('end_de', [''])[0].strip()
        page_no = qs.get('page_no', ['1'])[0].strip()
        page_count = qs.get('page_count', ['20'])[0].strip()
        pblntf_ty = qs.get('pblntf_ty', [''])[0].strip()

        try:
            corp_code = validate_corp_code(corp_code, required=False)
            bgn_de, end_de = validate_date_range(bgn_de, end_de)
            page_no = parse_int_range(page_no, 'page_no', 1, 1, 1000)
            page_count = parse_int_range(page_count, 'page_count', 20, 1, 100)
            pblntf_ty = validate_dart_pblntf_ty(pblntf_ty)
            data = search_disclosure(
                corp_code=corp_code,
                bgn_de=bgn_de,
                end_de=end_de,
                page_no=page_no,
                page_count=page_count,
                pblntf_ty=pblntf_ty,
            )
            dart_status = data.get('status')
            if dart_status and dart_status not in ('000', '013'):
                send_json_response(
                    self,
                    502,
                    api_error_payload(
                        'DART_API_ERROR',
                        data.get('message') or 'DART API 오류가 발생했습니다.',
                        details={'dartStatus': dart_status},
                    ),
                )
                return
            send_json_response(self, 200, api_success_payload(data))
        except ValueError as e:
            send_api_error(self, 400, 'VALIDATION_ERROR', str(e))
        except Exception:
            log_exception('api_request_failed', endpoint='dart-search')
            send_api_error(self, 500, 'INTERNAL_ERROR', '서버 오류가 발생했습니다.')
