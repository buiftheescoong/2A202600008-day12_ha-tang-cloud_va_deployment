import ast
import operator
import os
import sys
import time
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient
from app.config import settings



# Thư mục lưu kết quả các tool
_RESULT_DIR = Path("tool_results")
_RESULT_DIR.mkdir(exist_ok=True)

tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)


# @tool
# def get_weather(location: str) -> dict:
#     """
#     Lấy thông tin thời tiết hiện tại và dự báo cho một địa điểm.

#     Args:
#         location: Tên thành phố hoặc địa điểm (e.g., "Tokyo", "Ho Chi Minh City")

#     Returns:
#         dict chứa thông tin thời tiết:
#             - location: tên địa điểm
#             - temperature_c: nhiệt độ hiện tại (°C)
#             - feels_like_c: nhiệt độ cảm nhận (°C)
#             - humidity_pct: độ ẩm (%)
#             - description: mô tả thời tiết (e.g., "clear sky")
#             - wind_speed_ms: tốc độ gió (m/s)
#             - forecast: danh sách dự báo 5 ngày tới (mỗi ngày: date, temp_min_c, temp_max_c, description)
#     """
#     api_key = os.environ.get("OPENWEATHER_API_KEY", "")
#     if not api_key:
#         raise EnvironmentError(
#             "Thiếu API key. Hãy set biến môi trường OPENWEATHER_API_KEY."
#         )

#     base_url = "https://api.openweathermap.org/data/2.5"
#     encoded_location = urllib.parse.quote(location)

#     # --- Thời tiết hiện tại ---
#     current_url = (
#         f"{base_url}/weather"
#         f"?q={encoded_location}"
#         f"&appid={api_key}"
#         f"&units=metric"
#         f"&lang=vi"
#     )
#     with urllib.request.urlopen(current_url, timeout=10) as response:
#         current_data = json.loads(response.read().decode())

#     current = {
#         "location": current_data["name"],
#         "temperature_c": current_data["main"]["temp"],
#         "feels_like_c": current_data["main"]["feels_like"],
#         "humidity_pct": current_data["main"]["humidity"],
#         "description": current_data["weather"][0]["description"],
#         "wind_speed_ms": current_data["wind"]["speed"],
#     }

#     # --- Dự báo 5 ngày (mỗi 3 giờ → lấy mốc 12:00 hàng ngày) ---
#     forecast_url = (
#         f"{base_url}/forecast"
#         f"?q={encoded_location}"
#         f"&appid={api_key}"
#         f"&units=metric"
#         f"&lang=vi"
#     )
#     with urllib.request.urlopen(forecast_url, timeout=10) as response:
#         forecast_data = json.loads(response.read().decode())

#     seen_dates = set()
#     forecast = []
#     for item in forecast_data["list"]:
#         date = item["dt_txt"].split(" ")[0]          # "YYYY-MM-DD"
#         time_part = item["dt_txt"].split(" ")[1]     # "HH:MM:SS"
#         if time_part == "12:00:00" and date not in seen_dates:
#             seen_dates.add(date)
#             forecast.append({
#                 "date": date,
#                 "temp_min_c": item["main"]["temp_min"],
#                 "temp_max_c": item["main"]["temp_max"],
#                 "description": item["weather"][0]["description"],
#             })
#         if len(forecast) >= 5:
#             break

#     result = {**current, "forecast": forecast}

#     # Ghi ra file JSON vào folder "tool result"
#     output_path = _RESULT_DIR / "weather_result.json"
#     with open(output_path, "w", encoding="utf-8") as f:
#         json.dump(result, f, ensure_ascii=False, indent=2)
#     print(f"[OK] Đã lưu kết quả vào: {output_path}")

#     return result

@tool
def get_exchange_rate(from_currency: str, to_currency: str) -> dict:
    """
    Lấy tỷ giá hối đoái giữa hai đồng tiền và lưu kết quả ra file JSON.

    Args:
        from_currency: Mã tiền gốc theo chuẩn ISO 4217 (e.g., "VND", "USD")
        to_currency:   Mã tiền đích theo chuẩn ISO 4217 (e.g., "JPY", "EUR")

    Returns:
        dict chứa thông tin tỷ giá:
            - from_currency: mã tiền gốc
            - to_currency:   mã tiền đích
            - rate:          tỷ giá (1 from_currency = rate to_currency)
            - last_updated:  thời điểm cập nhật tỷ giá (UTC)

    Side effect:
        Ghi kết quả ra file exchange_rate_result.json trong thư mục hiện tại.
    """
    api_key = settings.EXCHANGERATE_API_KEY
    if not api_key or api_key == "your_exchangerate_api_key_here":
        raise EnvironmentError(
            "Thiếu API key. Hãy set EXCHANGERATE_API_KEY trong file .env."
        )

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    # ExchangeRate-API: lấy toàn bộ tỷ giá theo đồng gốc
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{from_currency}"

    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read().decode())

    if data.get("result") != "success":
        raise ValueError(f"API trả lỗi: {data.get('error-type', 'unknown')}")

    rate = data["conversion_rates"].get(to_currency)
    if rate is None:
        raise ValueError(f"Không tìm thấy mã tiền tệ: {to_currency}")

    result = {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate": rate,
        "last_updated": data["time_last_update_utc"],
    }

    # Ghi ra file JSON vào folder "tool result"
    output_path = _RESULT_DIR / "exchange_rate_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] Đã lưu kết quả vào: {output_path}")

    return result

@tool
def web_search(query: str, source: str = "duckduckgo", max_results: int = 5) -> dict:
    """
    Tìm kiếm thông tin trên DuckDuckGo hoặc Wikipedia. Không cần API key.

    Args:
        query:       Câu truy vấn tìm kiếm (e.g., "visa requirements Japan Vietnam")
        source:      Nguồn tìm kiếm: "duckduckgo" hoặc "wikipedia" (mặc định: "duckduckgo")
        max_results: Số kết quả tối đa trả về (chỉ áp dụng cho duckduckgo, mặc định: 5)

    Returns:
        dict chứa kết quả tìm kiếm:
            - query:   câu truy vấn gốc
            - source:  nguồn dữ liệu ("duckduckgo" hoặc "wikipedia")
            - results: danh sách kết quả
                DuckDuckGo → mỗi item: {title, url, snippet}
                Wikipedia  → mỗi item: {title, url, summary}

    Side effect:
        Ghi kết quả ra file search_result.json trong folder "tool result".
    """
    source = source.lower()
    if source not in ("duckduckgo", "wikipedia"):
        raise ValueError("source phải là 'duckduckgo' hoặc 'wikipedia'")

    headers = {"User-Agent": "Mozilla/5.0 (compatible; TravelBot/1.0)"}

    if source == "duckduckgo":
        # DuckDuckGo Instant Answer API (JSON, miễn phí, không cần key)
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        })
        url = f"https://api.duckduckgo.com/?{params}"
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        results = []

        # RelatedTopics: kết quả liên quan chính
        for item in data.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            # Bỏ qua nhóm topic (có key "Topics" thay vì "Text")
            if "Topics" in item:
                for sub in item["Topics"]:
                    if len(results) >= max_results:
                        break
                    if sub.get("Text"):
                        results.append({
                            "title": sub.get("Text", "").split(" - ")[0],
                            "url": sub.get("FirstURL", ""),
                            "snippet": sub.get("Text", ""),
                        })
            elif item.get("Text"):
                results.append({
                    "title": item.get("Text", "").split(" - ")[0],
                    "url": item.get("FirstURL", ""),
                    "snippet": item.get("Text", ""),
                })

        # Abstract: tóm tắt chính (nếu có) — thêm vào đầu danh sách
        if data.get("AbstractText"):
            results.insert(0, {
                "title": data.get("Heading", query),
                "url": data.get("AbstractURL", ""),
                "snippet": data["AbstractText"],
            })
            results = results[:max_results]

    else:  # wikipedia
        # Wikipedia REST API — trả về tóm tắt bài viết
        params = urllib.parse.urlencode({"q": query, "limit": max_results})
        search_url = f"https://en.wikipedia.org/w/rest.php/v1/search/page?{params}"
        req = urllib.request.Request(search_url, headers=headers)

        with urllib.request.urlopen(req, timeout=10) as response:
            search_data = json.loads(response.read().decode())

        results = []
        for page in search_data.get("pages", [])[:max_results]:
            title = page.get("title", "")
            page_key = page.get("key", title.replace(" ", "_"))

            # Lấy tóm tắt từng bài
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_key)}"
            try:
                req2 = urllib.request.Request(summary_url, headers=headers)
                with urllib.request.urlopen(req2, timeout=10) as r:
                    summary_data = json.loads(r.read().decode())
                summary = summary_data.get("extract", "")
            except Exception:
                summary = page.get("excerpt", "")

            results.append({
                "title": title,
                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(page_key)}",
                "summary": summary,
            })

    output = {
        "query": query,
        "source": source,
        "results": results,
    }

    # Ghi ra file JSON vào folder "tool result"
    output_path = _RESULT_DIR / "search_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] Đã lưu kết quả vào: {output_path}")

    return output


# Các phép toán được phép — không cho phép gọi hàm tùy ý
_ALLOWED_OPS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.Mod:  operator.mod,
    ast.USub: operator.neg,   # số âm: -5
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    """Duyệt AST và tính giá trị, chỉ cho phép các phép toán số học."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op_fn = _ALLOWED_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Phép toán không được hỗ trợ: {type(node.op).__name__}")
        left  = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ZeroDivisionError("Không thể chia cho 0")
        return op_fn(left, right)
    if isinstance(node, ast.UnaryOp):
        op_fn = _ALLOWED_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Toán tử không được hỗ trợ: {type(node.op).__name__}")
        return op_fn(_safe_eval(node.operand))
    raise ValueError(f"Biểu thức không hợp lệ: {ast.dump(node)}")


@tool
def calculator(expression: str) -> dict:
    """
    Tính toán biểu thức số học một cách an toàn (không dùng eval).
    Hỗ trợ: + - * / ** % và số âm.

    Args:
        expression: Biểu thức toán học dạng chuỗi.
                    e.g., "3_000_000 + 5_000_000"
                          "(3000000 + 5000000) * 0.00627"
                          "15000000 / 0.00627"

    Returns:
        dict chứa kết quả tính toán:
            - expression: biểu thức gốc
            - result:     kết quả (float)
            - result_int: kết quả làm tròn (int), tiện hiển thị tiền tệ

    Side effect:
        Ghi kết quả ra file calculator_result.json trong folder "tool result".
    """
    # Chuẩn hóa: bỏ dấu _ ngăn cách hàng nghìn, bỏ khoảng trắng thừa
    cleaned = expression.replace("_", "").replace(",", "").strip()

    try:
        tree = ast.parse(cleaned, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Biểu thức sai cú pháp: {e}")

    result = _safe_eval(tree)

    output = {
        "expression": expression,
        "result":     round(result, 6),
        "result_int": round(result),
    }

    # Ghi ra file JSON vào folder "tool result"
    output_path = _RESULT_DIR / "calculator_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] Đã lưu kết quả vào: {output_path}")

    return output



@tool
def search_flights_serpapi(
    origin: str,
    destination: str,
    depart_date: str,
    days_range: int = 1,
    return_date: str | None = None,
    adults: int = 1,
    currency: str = "VND",
    stops: int | None = None,
) -> dict:
    """
    Tìm thông tin các chuyến bay qua SerpApi (Google Flights).

    Args:
        origin:       Mã sân bay IATA điểm đi       (e.g., "HAN", "SGN")
        destination:  Mã sân bay IATA điểm đến      (e.g., "NRT", "HND")
        depart_date:  Ngày đi đầu tiên "YYYY-MM-DD"
        days_range:   Số ngày tìm kể từ depart_date (mặc định: 1)
        return_date:  Ngày về "YYYY-MM-DD" — None = một chiều (mặc định: None)
        adults:       Số người lớn                  (mặc định: 1)
        currency:     Mã tiền tệ                    (mặc định: "VND")
        stops:        Lọc điểm dừng: 0=bay thẳng, 1=≤1 điểm dừng, None=tất cả

    Returns:
        dict chứa:
            - origin / destination : mã sân bay
            - trip_type            : "one_way" hoặc "round_trip"
            - search_dates         : danh sách ngày đã tìm
            - total_found          : tổng chuyến tìm được
            - flights              : danh sách chuyến sắp xếp giá tăng dần
                  mỗi item: date, price, currency, airline, flight_number,
                             depart_time, arrive_time, duration_min,
                             direct, stops, layovers, carbon_emissions_g
            - cheapest             : chuyến rẻ nhất (hoặc None)
            - price_insights       : gợi ý mức giá từ Google (nếu có)

    Side effect:
        Ghi kết quả ra file google_flights_result.json trong folder "tool result".
    """
    api_key = settings.SERPAPI_KEY
    if not api_key or api_key == "your_serpapi_key_here":
        raise EnvironmentError(
            "Thiếu SERPAPI_KEY. Đăng ký tại https://serpapi.com rồi set vào .env"
        )

    trip_type  = 1 if return_date else 2   # SerpApi: 1=round-trip, 2=one-way
    start_date = datetime.strptime(depart_date, "%Y-%m-%d")
    search_dates = [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days_range)
    ]

    all_flights    = []
    price_insights = None

    for date_str in search_dates:
        print(f"  [SerpApi] Google Flights {origin} → {destination} ngày {date_str} ...")

        params: dict = {
            "engine":          "google_flights",
            "departure_id":    origin.upper(),
            "arrival_id":      destination.upper(),
            "outbound_date":   date_str,
            "type":            trip_type,
            "adults":          adults,
            "currency":        currency.upper(),
            "hl":              "vi",           # giao diện tiếng Việt
            "gl":              "vn",           # quốc gia Vietnam
            "api_key":         api_key,
        }
        if return_date:
            params["return_date"] = return_date
        if stops is not None:
            params["stops"] = stops            # 0=nonstop, 1=1stop, 2=2+stops

        qs  = urllib.parse.urlencode(params)
        url = f"https://serpapi.com/search.json?{qs}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TravelAgent/1.0)"},
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode())
                msg  = body.get("error", e.reason)
            except Exception:
                msg = e.reason
            print(f"  [SKIP] {date_str} — HTTP {e.code}: {msg}")
            continue

        # Lấy price_insights một lần (giống nhau cho cùng route)
        if price_insights is None:
            price_insights = raw.get("price_insights")

        # Google Flights trả về "best_flights" và "other_flights"
        buckets = raw.get("best_flights", []) + raw.get("other_flights", [])

        for item in buckets:
            try:
                # Mỗi "item" có thể có nhiều flight legs (với stopover)
                legs      = item.get("flights", [])
                if not legs:
                    continue

                first_leg = legs[0]
                last_leg  = legs[-1]

                # Giá
                price_val  = item.get("price")
                if price_val is None:
                    continue

                # Hãng bay và số hiệu chuyến
                airline       = first_leg.get("airline", "N/A")
                flight_number = first_leg.get("flight_number", "")

                # Giờ bay
                depart_time = first_leg.get("departure_airport", {}).get("time", "")
                arrive_time = last_leg.get("arrival_airport",   {}).get("time", "")

                # Thời gian bay tổng (phút)
                dur_min = item.get("total_duration", 0)

                # Điểm dừng
                stop_count = len(legs) - 1
                layovers   = [
                    {
                        "airport":      lv.get("name", ""),
                        "duration_min": lv.get("duration", 0),
                    }
                    for lv in item.get("layovers", [])
                ]

                # Carbon emissions (gram CO₂ ước tính)
                carbon_g = item.get("carbon_emissions", {}).get("this_flight", None)

                all_flights.append({
                    "date":               date_str,
                    "price":              price_val,
                    "currency":           currency.upper(),
                    "airline":            airline,
                    "flight_number":      flight_number,
                    "depart_time":        depart_time,
                    "arrive_time":        arrive_time,
                    "duration_min":       dur_min,
                    "direct":             stop_count == 0,
                    "stops":              stop_count,
                    "layovers":           layovers,
                    "carbon_emissions_g": carbon_g,
                })
            except (KeyError, TypeError):
                continue

        # Tránh rate-limit nếu tìm nhiều ngày
        if len(search_dates) > 1:
            time.sleep(1)

    # Sắp xếp theo giá tăng dần
    all_flights.sort(key=lambda x: x["price"])
    cheapest = all_flights[0] if all_flights else None

    result = {
        "origin":          origin.upper(),
        "destination":     destination.upper(),
        "trip_type":       "round_trip" if return_date else "one_way",
        "search_dates":    search_dates,
        "return_date":     return_date,
        "adults":          adults,
        "currency":        currency.upper(),
        "total_found":     len(all_flights),
        "flights":         all_flights,
        "cheapest":        cheapest,
        "price_insights":  price_insights,
    }

    # Ghi ra file JSON vào folder "tool result"
    output_path = _RESULT_DIR / "google_flights_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] Đã lưu kết quả vào: {output_path}")

    return result


@tool
def search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    currency: str = "VND",
    rating: int | None = None,
    max_results: int = 10,
) -> dict:
    """
    Tìm kiếm khách sạn qua SerpApi (Google Hotels).

    Args:
        location:    Tên thành phố / địa điểm (e.g., "Tokyo", "Shinjuku Tokyo")
        check_in:    Ngày nhận phòng   "YYYY-MM-DD"
        check_out:   Ngày trả phòng    "YYYY-MM-DD"
        adults:      Số người lớn      (mặc định: 2)
        currency:    Mã tiền tệ        (mặc định: "VND")
        rating:      Lọc số sao tối thiểu: 7=3 sao, 8=3.5 sao, 9=4 sao (None=tất cả)
        max_results: Số khách sạn tối đa trả về (mặc định: 10)

    Returns:
        dict chứa:
            - location    : địa điểm tìm kiếm
            - check_in    : ngày nhận phòng
            - check_out   : ngày trả phòng
            - nights      : số đêm lưu trú
            - adults      : số người lớn
            - total_found : tổng số khách sạn tìm được
            - hotels      : danh sách khách sạn sắp xếp giá tăng dần, mỗi item:
                              name, price_per_night, total_price, currency,
                              rating, stars, reviews_count,
                              location (địa chỉ), amenities, images[0],
                              deal (nhãn khuyến mãi nếu có), link
            - cheapest    : khách sạn rẻ nhất (hoặc None)
            - brands      : danh sách nhãn hiệu nổi bật (nếu có)
    """
    api_key = settings.SERPAPI_KEY
    if not api_key or api_key == "your_serpapi_key_here":
        raise EnvironmentError(
            "Thiếu SERPAPI_KEY. Đăng ký tại https://serpapi.com rồi set vào .env"
        )

    # Tính số đêm để hiển thị
    nights = (
        datetime.strptime(check_out, "%Y-%m-%d")
        - datetime.strptime(check_in,  "%Y-%m-%d")
    ).days
    if nights <= 0:
        raise ValueError("check_out phải sau check_in ít nhất 1 ngày")

    params: dict = {
        "engine":       "google_hotels",
        "q":            location,
        "check_in_date":  check_in,
        "check_out_date": check_out,
        "adults":       adults,
        "currency":     currency.upper(),
        "hl":           "vi",           # giao diện tiếng Việt
        "gl":           "vn",           # quốc gia Vietnam
        "api_key":      api_key,
    }
    if rating is not None:
        params["rating"] = rating       # 7=3*, 8=3.5*, 9=4*, 10=4.5*

    print(f"  [SerpApi] Google Hotels '{location}'"
          f" ({check_in} → {check_out}, {nights} đêm, {adults} người) ...")

    qs  = urllib.parse.urlencode(params)
    url = f"https://serpapi.com/search.json?{qs}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; TravelAgent/1.0)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
            msg  = body.get("error", e.reason)
        except Exception:
            msg = e.reason
        raise ValueError(f"HTTP {e.code} — {msg}") from e

    # Parse danh sách khách sạn
    properties = raw.get("properties", [])
    hotels = []

    for prop in properties:
        try:
            # Giá / đêm và tổng giá
            rate      = prop.get("rate_per_night", {})
            price_raw = rate.get("extracted_lowest") or rate.get("extracted_before_taxes_fees")
            total_raw = prop.get("total_rate", {}).get("extracted_lowest") or (
                price_raw * nights if price_raw else None
            )

            if price_raw is None:
                continue   # bỏ qua nếu không có giá

            # Tiện ích
            amenities = prop.get("amenities", [])[:8]   # tối đa 8 tiện ích

            # Ảnh đại diện
            images = prop.get("images", [])
            thumb  = images[0].get("thumbnail", "") if images else ""

            # Nhãn khuyến mãi / deal
            deal = prop.get("deal") or prop.get("deal_description", "")

            hotels.append({
                "name":             prop.get("name", "N/A"),
                "price_per_night":  price_raw,
                "total_price":      total_raw,
                "currency":         currency.upper(),
                "rating":           prop.get("overall_rating"),
                "stars":            prop.get("hotel_class"),
                "reviews_count":    prop.get("reviews"),
                "location":         prop.get("location", {}).get("address", ""),
                "amenities":        amenities,
                "thumbnail":        thumb,
                "deal":             deal,
                "link":             prop.get("link", ""),
            })
        except (KeyError, TypeError):
            continue

    # Sắp xếp theo giá / đêm tăng dần
    hotels.sort(key=lambda x: x["price_per_night"])
    hotels = hotels[:max_results]

    cheapest = hotels[0] if hotels else None
    brands   = [b.get("name") for b in raw.get("brands", []) if b.get("name")]

    result = {
        "location":    location,
        "check_in":    check_in,
        "check_out":   check_out,
        "nights":      nights,
        "adults":      adults,
        "currency":    currency.upper(),
        "total_found": len(properties),
        "hotels":      hotels,
        "cheapest":    cheapest,
        "brands":      brands,
    }

    # Ghi ra file JSON vào folder "tool result"
    output_path = _RESULT_DIR / "hotels_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] Đã lưu kết quả vào: {output_path}")

    return result


# ==============================================================
# TEST - Chạy trực tiếp file này để kiểm tra hàm get_weather
# Lệnh: python src/agent/tool.py
# ==============================================================

# if __name__ == "__main__":
#     # Fix encoding UTF-8 cho terminal Windows
#     sys.stdout.reconfigure(encoding="utf-8")

#     # Địa điểm muốn kiểm tra thời tiết
#     test_location = "Tokyo"

    # print(f"Đang lấy thông tin thời tiết cho: {test_location} ...\n")
    #
    # try:
    #     weather = get_weather(test_location)
    #
    #     # --- In thời tiết hiện tại ---
    #     print("===== THỜI TIẾT HIỆN TẠI =====")
    #     print(f"  Địa điểm     : {weather['location']}")
    #     print(f"  Nhiệt độ     : {weather['temperature_c']} °C")
    #     print(f"  Cảm nhận như : {weather['feels_like_c']} °C")
    #     print(f"  Độ ẩm        : {weather['humidity_pct']} %")
    #     print(f"  Mô tả        : {weather['description']}")
    #     print(f"  Tốc độ gió   : {weather['wind_speed_ms']} m/s")
    #
    #     # --- In dự báo 5 ngày ---
    #     print("\n===== DỰ BÁO 5 NGÀY TỚI =====")
    #     for day in weather["forecast"]:
    #         print(
    #             f"  {day['date']}  |  "
    #             f"Min: {day['temp_min_c']}°C  "
    #             f"Max: {day['temp_max_c']}°C  |  "
    #             f"{day['description']}"
    #         )
    #
    # except urllib.error.HTTPError as e:
    #     # Phải đặt TRƯỚC EnvironmentError vì HTTPError là subclass của OSError
    #     if e.code == 401:
    #         print("[LỖI 401] API key không hợp lệ hoặc chưa được kích hoạt.")
    #         print("  - Kiểm tra lại key trong file .env")
    #         print("  - Key mới tạo cần chờ tối đa 2 giờ để kích hoạt")
    #     elif e.code == 404:
    #         print(f"[LỖI 404] Không tìm thấy địa điểm: '{test_location}'")
    #     else:
    #         print(f"[LỖI HTTP {e.code}] {e}")
    # except EnvironmentError as e:
    #     print(f"[LỖI CẤU HÌNH] {e}")
    # except Exception as e:
    #     print(f"[LỖI] {e}")
    #
    # # ==============================================================
    # # TEST Tool 2: get_exchange_rate
    # # ==============================================================
    # print("\n" + "=" * 50)
    # from_cur = "VND"
    # to_cur   = "JPY"
    #
    # print(f"Đang lấy tỷ giá {from_cur} → {to_cur} ...\n")
    #
    # try:
    #     rate_info = get_exchange_rate(from_cur, to_cur)
    #
    #     print("===== TỶ GIÁ HỐI ĐOÁI =====")
    #     print(f"  {rate_info['from_currency']} → {rate_info['to_currency']}")
    #     print(f"  1 {rate_info['from_currency']} = {rate_info['rate']} {rate_info['to_currency']}")
    #     print(f"  Cập nhật lúc : {rate_info['last_updated']}")
    #
    #     # Ví dụ thực tế: đổi 10,000,000 VND sang JPY
    #     amount_vnd = 10000000
    #     amount_jpy = round(amount_vnd * rate_info["rate"], 2)
    #     print(f"\n  {amount_vnd:,} VND = {amount_jpy:,} JPY")
    #
    # except urllib.error.HTTPError as e:
    #     if e.code == 403:
    #         print("[LỖI 403] API key không hợp lệ hoặc hết quota.")
    #     else:
    #         print(f"[LỖI HTTP {e.code}] {e}")
    # except EnvironmentError as e:
    #     print(f"[LỖI CẤU HÌNH] {e}")
    # except ValueError as e:
    #     print(f"[LỖI GIÁ TRỊ] {e}")
    # except Exception as e:
    #     print(f"[LỖI] {e}")
    #
    # # ==============================================================
    # # TEST Tool 3: web_search — DuckDuckGo
    # # ==============================================================
    # print("\n" + "=" * 50)
    # ddg_query = "Tokyo snow spots open visiting tips"
    # print(f"[DuckDuckGo] Tìm kiếm: '{ddg_query}' ...\n")
    #
    # try:
    #     ddg_result = web_search(ddg_query, source="duckduckgo", max_results=3)
    #
    #     print(f"===== KẾT QUẢ DUCKDUCKGO ({len(ddg_result['results'])} kết quả) =====")
    #     for i, item in enumerate(ddg_result["results"], 1):
    #         print(f"\n  [{i}] {item['title']}")
    #         print(f"       URL    : {item['url']}")
    #         print(f"       Snippet: {item['snippet'][:120]}...")
    #
    # except Exception as e:
    #     print(f"[LỖI] {e}")
    #
    # # ==============================================================
    # # TEST Tool 3: web_search — Wikipedia
    # # ==============================================================
    # print("\n" + "=" * 50)
    # wiki_query = "Japan visa requirements"
    # print(f"[Wikipedia] Tìm kiếm: '{wiki_query}' ...\n")
    #
    # try:
    #     wiki_result = web_search(wiki_query, source="wikipedia", max_results=2)
    #
    #     print(f"===== KẾT QUẢ WIKIPEDIA ({len(wiki_result['results'])} kết quả) =====")
    #     for i, item in enumerate(wiki_result["results"], 1):
    #         print(f"\n  [{i}] {item['title']}")
    #         print(f"       URL    : {item['url']}")
    #         print(f"       Summary: {item['summary'][:200]}...")
    #
    # except Exception as e:
    #     print(f"[LỖI] {e}")
    #
    # # ==============================================================
    # # TEST Tool 4: calculator
    # # Kịch bản: Máy bay 8,000,000 VND + Khách sạn 7,000,000 VND
    # #           → tổng VND → đổi sang JPY theo tỷ giá Tool 2
    # # ==============================================================
    # print("\n" + "=" * 50)
    # print("Tính toán chi phí chuyến đi ...\n")
    #
    # test_cases = [
    #     ("Tổng chi phí VND",               "8_000_000 + 7_000_000"),
    #     ("Tổng VND → JPY (tỷ giá 0.00627)", "(8_000_000 + 7_000_000) * 0.00627"),
    #     ("Dự phòng thêm 20%",              "(8_000_000 + 7_000_000) * 1.2 * 0.00627"),
    #     ("Chi phí mỗi ngày (7 ngày)",      "(8_000_000 + 7_000_000) / 7"),
    # ]
    #
    # for label, expr in test_cases:
    #     try:
    #         calc = calculator(expr)
    #         print(f"  {label}")
    #         print(f"    Biểu thức : {calc['expression']}")
    #         print(f"    Kết quả   : {calc['result']:,.4f}  (≈ {calc['result_int']:,})\n")
    #     except (ValueError, ZeroDivisionError) as e:
    #         print(f"  [LỖI TÍNH TOÁN] {label}: {e}\n")
    #     except Exception as e:
    #         print(f"  [LỖI] {e}\n")

    # # ==============================================================
    # # TEST Tool 5 : search_flights_serpapi — Google Flights
    # # Kịch bản: HAN → NRT (Tokyo Narita), bay ngày mai, 3 ngày, bay thẳng
    # # ==============================================================
    # print("\n" + "=" * 50)
    # day1 = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    # print(f"[SerpApi] Tìm chuyến bay HAN → NRT từ {day1} trong 3 ngày ...\n")
    #
    # try:
    #     gf = search_flights_serpapi(
    #         origin="HAN",
    #         destination="NRT",
    #         depart_date=day1,
    #         days_range=3,
    #         adults=1,
    #         currency="VND",
    #         stops=None,       # None=tất cả, 0=bay thẳng, 1=1 điểm dừng
    #     )
    #
    #     print(f"\n  Tìm thấy: {gf['total_found']} chuyến\n")
    #
    #     # Price insights từ Google
    #     if gf["price_insights"]:
    #         pi = gf["price_insights"]
    #         print(f"  [Google Price Insights]")
    #         print(f"    Mức giá thấp  : {pi.get('lowest_price', 'N/A'):,}")
    #         print(f"    Mức giá thường: {pi.get('typical_price_range', ['N/A','N/A'])}")
    #         print(f"    Đánh giá      : {pi.get('price_level', 'N/A')}\n")
    #
    #     # In top 5 chuyến rẻ nhất
    #     print("===== TOP 5 CHUYẾN BAY RẺ NHẤT (Google Flights) =====")
    #     for i, f in enumerate(gf["flights"][:5], 1):
    #         dur_h        = f["duration_min"] // 60
    #         dur_m        = f["duration_min"] % 60
    #         stop_label   = "Bay thẳng" if f["direct"] else f"{f['stops']} điểm dừng"
    #         carbon_label = f"  | CO₂ ~{f['carbon_emissions_g']:,}g" if f["carbon_emissions_g"] else ""
    #         print(
    #             f"\n  [{i}] {f['date']}  |  {f['airline']}  {f['flight_number']}"
    #             f"\n       {f['depart_time']} → {f['arrive_time']}"
    #             f"  ({dur_h}h{dur_m:02d}m)  |  {stop_label}{carbon_label}"
    #             f"\n       Giá: {f['price']:,.0f} {f['currency']}"
    #         )
    #         for lv in f["layovers"]:
    #             print(f"         ↳ Quá cảnh: {lv['airport']} ({lv['duration_min']} phút)")
    #
    #     if gf["cheapest"]:
    #         c = gf["cheapest"]
    #         print(
    #             f"\n  Rẻ nhất: {c['price']:,.0f} {c['currency']}"
    #             f" — {c['airline']} {c['flight_number']} ngày {c['date']}"
    #         )
    #
    # except EnvironmentError as e:
    #     print(f"[LỖI CẤU HÌNH] {e}")
    # except Exception as e:
    #     print(f"[LỖI] {e}")

    # # ==============================================================
    # # TEST Tool 6: search_hotels — Google Hotels
    # # Kịch bản: Tìm khách sạn ở Tokyo, nhận phòng ngày mai, 3 đêm, 2 người, từ 4 sao
    # # ==============================================================
    # print("\n" + "=" * 50)
    # ci = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    # co = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
    # print(f"[SerpApi] Tìm khách sạn Tokyo ({ci} → {co}, 3 đêm, 2 người) ...\n")
    #
    # try:
    #     hotels = search_hotels(
    #         location="Tokyo",
    #         check_in=ci,
    #         check_out=co,
    #         adults=2,
    #         currency="VND",
    #         rating=9,           # 9 = từ 4 sao trở lên
    #         max_results=5,
    #     )
    #
    #     print(f"  Tìm thấy: {hotels['total_found']} khách sạn  |  Hiển thị top {len(hotels['hotels'])}\n")
    #
    #     if hotels["brands"]:
    #         print(f"  Thương hiệu nổi bật: {', '.join(hotels['brands'][:5])}\n")
    #
    #     print("===== TOP KHÁCH SẠN RẺ NHẤT (Google Hotels) =====")
    #     for i, h in enumerate(hotels["hotels"], 1):
    #         stars_label = f"{h['stars']}" if h["stars"] else "N/A"
    #         rating_str  = f"{h['rating']}/5" if h["rating"] else "Chưa có"
    #         reviews_str = f"{h['reviews_count']:,} đánh giá" if h["reviews_count"] else ""
    #         deal_str    = f"  🏷 {h['deal']}" if h["deal"] else ""
    #         amenity_str = ", ".join(h["amenities"][:4]) if h["amenities"] else ""
    #
    #         print(
    #             f"\n  [{i}] {h['name']}{deal_str}"
    #             f"\n       {stars_label} sao  |  ⭐ {rating_str}  {reviews_str}"
    #             f"\n       📍 {h['location']}"
    #             f"\n       💰 {h['price_per_night']:,.0f} VND/đêm"
    #             f"  →  Tổng {h['total_price']:,.0f} VND ({hotels['nights']} đêm)"
    #             f"\n       🛎 {amenity_str}"
    #         )
    #
    #     if hotels["cheapest"]:
    #         c = hotels["cheapest"]
    #         print(f"\n  Rẻ nhất: {c['name']} — {c['price_per_night']:,.0f} VND/đêm")
    #
    # except EnvironmentError as e:
    #     print(f"[LỖI CẤU HÌNH] {e}")
    # except ValueError as e:
    #     print(f"[LỖI] {e}")
    # except Exception as e:
    #     print(f"[LỖI] {e}")

@tool
def search_web_info(thought: str, query: str):
    """
    Searches the internet for real-time information (weather, news, gold prices, current time, etc.)
    using Tavily Search API. Returns a concise summary of the findings.
    Args:
        thought (str): Why you need to perform this search.
        query (str): The specific search query.
    Returns:
        str: A summary of the search results, or an error message starting with 'Error:' if the search fails.
    """
    try:
        
        response = tavily.search(query=query, search_depth="basic", include_answer=True)
        print(f"Tavily Search Response: {response}")
        
        if response.get("answer"):
            return f"Search Result: {response['answer']}"
        
        context = "\n".join([f"- {res['content']}" for res in response['results'][:3]])
        return f"Search Results for '{query}':\n{context}"
        
    except Exception as e:
        return f"Error searching Tavily: {str(e)}"

@tool
def request_user(question: str):
    """
    Ask the user for missing information or clarification.
    Use this if you can't proceed without more data (e.g., user preferences, personal details).
    """
    # This tool will be intercepted by the graph logic/CLI to wait for user input
    return f"REQUESTED_USER_INPUT: {question}"


tools = [get_exchange_rate, web_search, calculator, search_flights_serpapi, search_hotels, request_user, search_web_info]