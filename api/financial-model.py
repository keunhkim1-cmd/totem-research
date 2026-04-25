import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.api_routes import ROUTES_BY_PATH, make_handler

handler = make_handler(ROUTES_BY_PATH['/api/financial-model'])
