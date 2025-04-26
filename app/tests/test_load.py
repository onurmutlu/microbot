import pytest
import asyncio
import time
import random
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from app.main import app

# Test istemcisi oluşturun
client = TestClient(app)

# Temel istekler
def get_health():
    return client.get("/health")

def get_root():
    return client.get("/")

# Yük testi parametreleri
@pytest.mark.parametrize("endpoint,requests,concurrency", [
    ("/health", 100, 10),
    ("/", 100, 10),
])
def test_endpoint_load(endpoint, requests, concurrency):
    """Belirtilen endpoint'in yük testini yapar."""
    start_time = time.time()
    success_count = 0
    error_count = 0
    response_times = []
    
    def make_request():
        nonlocal success_count, error_count
        request_start = time.time()
        try:
            response = client.get(endpoint)
            request_time = time.time() - request_start
            response_times.append(request_time)
            
            if response.status_code == 200:
                success_count += 1
            else:
                error_count += 1
                print(f"Error {response.status_code}: {response.text}")
        except Exception as e:
            error_count += 1
            print(f"Exception: {str(e)}")
    
    # İstekleri paralel olarak çalıştırın
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request) for _ in range(requests)]
        for future in futures:
            future.result()
    
    total_time = time.time() - start_time
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    print(f"\nYük Testi Sonuçları - {endpoint}")
    print(f"Toplam istek: {requests}")
    print(f"Eşzamanlılık: {concurrency}")
    print(f"Başarılı: {success_count}")
    print(f"Hata: {error_count}")
    print(f"Toplam süre: {total_time:.2f} saniye")
    print(f"Ortalama yanıt süresi: {avg_response_time:.4f} saniye")
    print(f"Saniyedeki istek: {requests/total_time:.2f} istek/saniye")
    
    assert success_count > 0, "Başarılı istek yok"
    assert error_count == 0, f"Hata sayısı: {error_count}"

# İleri seviye yük testi: Artan yük simülasyonu
def test_increasing_load():
    """Artan yük altında API performansını test eder."""
    endpoints = ["/health", "/"]
    max_concurrency = 20
    requests_per_level = 50
    levels = 5
    
    results = {}
    
    for endpoint in endpoints:
        endpoint_results = []
        
        for level in range(1, levels + 1):
            concurrency = max(1, int(max_concurrency * (level / levels)))
            start_time = time.time()
            success_count = 0
            error_count = 0
            response_times = []
            
            def make_request():
                nonlocal success_count, error_count
                request_start = time.time()
                try:
                    response = client.get(endpoint)
                    request_time = time.time() - request_start
                    response_times.append(request_time)
                    
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        error_count += 1
                except Exception:
                    error_count += 1
            
            # İstekleri paralel olarak çalıştırın
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(make_request) for _ in range(requests_per_level)]
                for future in futures:
                    future.result()
            
            total_time = time.time() - start_time
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            level_result = {
                "level": level,
                "concurrency": concurrency,
                "success_count": success_count,
                "error_count": error_count,
                "total_time": total_time,
                "avg_response_time": avg_response_time,
                "requests_per_second": requests_per_level / total_time
            }
            
            endpoint_results.append(level_result)
            
            # Sonuçları yazdırın
            print(f"\nArtan Yük Seviyesi {level}/{levels} - {endpoint}")
            print(f"Eşzamanlılık: {concurrency}")
            print(f"Başarılı: {success_count}/{requests_per_level}")
            print(f"Ortalama yanıt süresi: {avg_response_time:.4f} saniye")
            print(f"Saniyedeki istek: {requests_per_level/total_time:.2f} istek/saniye")
            
            # Her seviye arasında kısa bir duraklatma
            time.sleep(1)
        
        results[endpoint] = endpoint_results
    
    # Tüm sonuçların özeti
    print("\nArtan Yük Testi Özeti:")
    for endpoint, endpoint_results in results.items():
        print(f"\n{endpoint}:")
        for level in endpoint_results:
            print(f"Seviye {level['level']} - "
                  f"İstek/s: {level['requests_per_second']:.2f}, "
                  f"Ort. Süre: {level['avg_response_time']:.4f}s, "
                  f"Başarı: {level['success_count']}/{requests_per_level}")
        
        # Son seviyede hata olmamalı
        last_level = endpoint_results[-1]
        assert last_level["error_count"] == 0, f"Son seviyede hatalar var: {last_level['error_count']}" 