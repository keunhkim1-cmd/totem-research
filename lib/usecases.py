"""Shared endpoint use cases.

API handlers and the local development server should stay as transport shims:
parse HTTP, call one of these functions, then shape the HTTP response.
"""
from lib.dart import search_disclosure
from lib.dart_base import DART_SEARCH_OK_STATUSES, raise_for_status
from lib.financial_api_security import validate_params
from lib.krx import search_kind
from lib.naver import (
    calc_thresholds,
    caution_search,
    fetch_prices,
    fetch_stock_overview,
    stock_code,
)
from lib.validation import (
    normalize_query,
    parse_int_range,
    validate_corp_code,
    validate_dart_pblntf_ty,
    validate_date_range,
    validate_stock_code,
)


def warning_search_payload(raw_name: str) -> dict:
    name = normalize_query(raw_name)
    return {'results': search_kind(name), 'query': name}


def caution_search_payload(raw_name: str) -> dict:
    name = normalize_query(raw_name)
    return caution_search(name)


def stock_code_payload(raw_name: str) -> dict:
    name = normalize_query(raw_name)
    return {'items': stock_code(name)}


def stock_price_payload(raw_code: str) -> dict:
    code = validate_stock_code(raw_code)
    prices = fetch_prices(code, count=20)
    thresholds = calc_thresholds(prices)
    payload = {'prices': prices[-16:], 'thresholds': thresholds}
    if 'error' in thresholds:
        payload['warnings'] = [{
            'code': 'INSUFFICIENT_PRICE_DATA',
            'message': thresholds['error'],
        }]
    return payload


def stock_overview_payload(raw_code: str) -> dict:
    code = validate_stock_code(raw_code)
    return fetch_stock_overview(code)


def dart_search_payload(
    *,
    corp_code: str = '',
    bgn_de: str = '',
    end_de: str = '',
    page_no: str = '1',
    page_count: str = '20',
    pblntf_ty: str = '',
) -> dict:
    valid_corp_code = validate_corp_code(corp_code, required=False)
    valid_bgn_de, valid_end_de = validate_date_range(bgn_de, end_de)
    valid_page_no = parse_int_range(page_no, 'page_no', 1, 1, 1000)
    valid_page_count = parse_int_range(page_count, 'page_count', 20, 1, 100)
    valid_pblntf_ty = validate_dart_pblntf_ty(pblntf_ty)
    data = search_disclosure(
        corp_code=valid_corp_code,
        bgn_de=valid_bgn_de,
        end_de=valid_end_de,
        page_no=valid_page_no,
        page_count=valid_page_count,
        pblntf_ty=valid_pblntf_ty,
    )
    raise_for_status(data, ok_statuses=DART_SEARCH_OK_STATUSES)
    return data


def financial_model_payload(
    *,
    corp_code: str,
    fs_div: str = 'CFS',
    years: str = '5',
) -> dict:
    valid_corp_code, valid_fs_div, valid_years = validate_params(
        corp_code,
        fs_div,
        years,
    )
    from lib.financial_model import build_model

    return build_model(valid_corp_code, fs_div=valid_fs_div, years=valid_years)
