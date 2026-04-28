import requests
from bs4 import BeautifulSoup
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum


class SortOption(str, Enum):
    POPULAR = "popular"
    NEWEST = "newest"


class Capability(str, Enum):
    CLOUD = "cloud"
    EMBEDDING = "embedding"
    VISION = "vision"
    TOOLS = "tools"
    THINKING = "thinking"


BASE_URL = "https://ollama.com"
SEARCH_URL = "https://ollama.com/search?page={}&o="

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# -----------------------------------
# STEP 1: SCRAPE MODEL LIST (RICH DATA)
# -----------------------------------
def get_models_from_page(page, query=None, sort=SortOption.POPULAR, capabilities=None):
    url = build_search_url(page, query, sort, capabilities)

    print(f"[DEBUG] URL: {url}")

    res = requests.get(url, headers=HEADERS)

    if res.status_code != 200:
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    model_elements = soup.select("li[x-test-model]")

    if not model_elements:
        return []

    models = []

    for li in model_elements:
        try:
            name_tag = li.select_one("[x-test-search-response-title]")
            desc_tag = li.select_one("div.mb-1 p")

            pulls_tag = li.select_one("[x-test-pull-count]")
            tag_count_tag = li.select_one("[x-test-tag-count]")
            updated_tag = li.select_one("[x-test-updated]")

            capabilities_list = [
                cap.text.strip()
                for cap in li.select("[x-test-capability]")
            ]

            sizes = [
                size.text.strip()
                for size in li.select("[x-test-size]")
            ]

            models.append({
                "name": name_tag.text.strip() if name_tag else None,
                "description": desc_tag.text.strip() if desc_tag else None,
                "capabilities": capabilities_list,
                "sizes": sizes,
                "pulls": pulls_tag.text.strip() if pulls_tag else None,
                "tag_count": tag_count_tag.text.strip() if tag_count_tag else None,
                "updated": updated_tag.text.strip() if updated_tag else None,
            })

        except Exception:
            continue

    return models


# -----------------------------------
# STEP 2: PAGINATION + DEDUP
# -----------------------------------
def get_all_models(
    max_pages=100,
    query=None,
    sort=SortOption.POPULAR,
    capabilities=None
):
    all_models = {}

    for page in range(1, max_pages + 1):
        print(f"[INFO] Scraping page {page}")

        models = get_models_from_page(page, query, sort, capabilities)

        if not models:
            print("[INFO] No more pages. Stopping.")
            break

        for model in models:
            name = model.get("name")
            if not name:
                continue

            all_models[name] = model

        time.sleep(0.3)

    return list(all_models.values())

# -----------------------------------
# STEP 3: SCRAPE TAG DETAILS (CLEAN)
# -----------------------------------
def build_search_url(page, query=None, sort=SortOption.POPULAR, capabilities=None):
    base = f"https://ollama.com/search?page={page}"

    params = []

    if query:
        params.append(f"q={query}")

    if sort:
        params.append(f"o={sort.value}")

    if capabilities:
        for cap in capabilities:
            params.append(f"c={cap.value}")

    if params:
        base += "&" + "&".join(params)

    return base


def get_model_tags(model_name):
    url = f"{BASE_URL}/library/{model_name}/tags"

    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")

        tags = []

        rows = soup.select("div.group")

        for row in rows:
            try:
                tag_a = row.select_one("span.col-span-6 a")
                if not tag_a:
                    continue

                tag_name = tag_a.text.strip()

                size = None
                context = None
                input_type = None

                size_el = row.select_one("p.col-span-2")
                context_els = row.select("p.col-span-2")
                input_el = row.select_one("div.col-span-2")

                if size_el:
                    size = size_el.text.strip()

                if len(context_els) > 1:
                    context = context_els[1].text.strip()
                    context = context.replace("context window", "").strip()

                if input_el:
                    input_type = input_el.text.strip()

                tags.append({
                    "tag": tag_name,
                    "size": size,
                    "context": context,
                    "input": input_type
                })

            except Exception:
                continue

        return tags

    except Exception as e:
        print(f"[ERROR] {model_name}: {e}")
        return []


# -----------------------------------
# STEP 4: MERGE EVERYTHING
# -----------------------------------
def build_dataset(
    max_pages=100,
    query=None,
    sort=SortOption.POPULAR,
    capabilities=None
):
    models = get_all_models(
        max_pages=max_pages,
        query=query,
        sort=sort,
        capabilities=capabilities
    )

    print(f"\n[INFO] Total models: {len(models)}\n")

    final_data = {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {
            executor.submit(get_model_tags, m["name"]): m
            for m in models
        }

        for future in as_completed(future_map):
            model = future_map[future]
            name = model["name"]

            try:
                tags = future.result()

                # clean input formatting
                for t in tags:
                    if isinstance(t.get("input"), str):
                        t["input"] = [i.strip() for i in t["input"].split(",")]

                final_data[name] = {
                    "meta": model,
                    "tags": tags
                }

                print(f"[INFO] Processed {name}")

            except Exception as e:
                print(f"[ERROR] {name}: {e}")

    return final_data


# -----------------------------------
# MAIN
# -----------------------------------


if __name__ == "__main__":
    data = build_dataset(
        query="llama",
        sort=SortOption.NEWEST,
        capabilities=[
            # Capability.CLOUD,
            # Capability.EMBEDDING,
            # Capability.VISION,
            # Capability.TOOLS,
            # Capability.THINKING
        ]
    )
    with open("ollama_full_dataset.json", "w") as f:
        json.dump(data, f, indent=2)

    print("\n✅ Done! Saved to ollama_full_dataset.json")