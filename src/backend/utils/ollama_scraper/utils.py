# utils.py
from urllib.parse import urlencode

BASE_URL = "https://ollama.com/search"

def build_url(query=None, categories=None, order="newest", page=1):
    params = {}

    if query:
        params["q"] = query

    if categories:
        params["c"] = categories

    if order:
        params["o"] = order

    if page > 1:
        params["p"] = page  # pagination param (may change!)

    return BASE_URL + "?" + urlencode(params, doseq=True)