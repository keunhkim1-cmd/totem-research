import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.api_routes import ROUTES_BY_PATH, RouteHandler


class handler(RouteHandler):
    route = ROUTES_BY_PATH['/api/stock-code']
