# MicroBot Frontend Mini Uygulama Geliştirme Rehberi

## Genel Bakış
MicroBot, Telegram gruplarını yönetmek için geliştirilmiş güçlü bir API ve bot platformudur. Backend'de AI destekli içerik optimizasyonu, GraphQL API, performans izleme ve grup analizi özellikleri sunmaktadır. Bu rehber, bu özellikleri kullanacak bir frontend mini uygulaması geliştirmenize yardımcı olacaktır.

## Teknik Gereksinimler
- Vue.js 3 (Composition API ile)
- TypeScript
- Vite
- Tailwind CSS
- Apollo Client (GraphQL entegrasyonu için)
- Chart.js (Metrik görselleştirme için)
- Pinia (Durum yönetimi için)

## Özellikler ve Sayfalar

### 1. Kullanıcı Arayüzü
- Karanlık ve aydınlık tema desteği
- Mobil uyumlu (responsive) tasarım
- Modern, temiz UI/UX
- SSE (Server-Sent Events) ile gerçek zamanlı güncellemeler

### 2. Ana Ekranlar

#### Dashboard
- Aktif telegram oturumları için istatistikler
- Grup mesaj metrikleri (başarı/hata oranları)
- AI içerik optimizasyonu metrikleri
- Sistem kaynak kullanımı (CPU, bellek, disk)
- Son hata ve aktivite logları

#### Grup Yönetimi
- Grup listesi ve arama
- Her grup için detaylı analiz sayfası
  - Aktivite grafiği (zamana göre mesaj sayısı)
  - En aktif saatler analizi
  - İçerik türü analizi
  - Engagement metrikleri
  - Özelleştirilebilir zaman aralığı filtresi

#### İçerik Optimizasyonu
- AI destekli mesaj önerisi sayfası
- Mesaj içerik optimizasyonu arayüzü
  - Kullanıcı mesaj girer
  - AI, grupta en iyi performans gösteren içerik türüne göre öneriler sunar
  - Gerçek zamanlı öneri ve düzeltmeler
  - Mesaj önizleme
- Zamanlı mesaj planlaması (optimize edilmiş mesajlar için)

#### Metrik İzleme ve Performans
- Prometheus metriklerinin görselleştirilmesi
  - İstek latensleri
  - Başarılı/başarısız mesaj oranları
  - Önbellek isabet/ıskalama oranları
  - API istek sayıları
- Metrik alarmları ve bildirimler

#### Ayarlar
- Kullanıcı profili yönetimi
- Telegram hesap ayarları
- AI optimizasyon parametreleri
- Performans ve önbellek ayarları
- Bildirim tercihleri

### 3. API Entegrasyonları

#### REST API
Temel API endpoint'leri:
- `/api/v1/ai/group-insights/{group_id}`
- `/api/v1/ai/optimize-message`
- `/api/v1/ai/batch-analyze`
- `/health` - Sistem sağlık kontrolü
- `/api/groups` - Grup yönetimi
- `/api/messages` - Mesaj yönetimi

#### GraphQL API
Ana GraphQL endpoint'i: `/api/v1/graphql`

Örnek sorgular:
```graphql
# Grup içgörüleri için sorgu
query GetGroupInsights($groupId: Int!) {
  group_content_insights(group_id: $groupId) {
    status
    group_id
    message_count
    success_rate
    content_analysis {
      avg_message_length
      media_rate
      link_rate
      mention_rate
      hashtag_rate
    }
    engagement_rates {
      with_media
      with_links
      with_mentions
      with_hashtags
      short_messages
      long_messages
    }
    active_hours {
      top_active_hours
      hour_distribution {
        hour
        count
      }
    }
    recommendations {
      type
      message
    }
  }
}

# Mesaj optimizasyonu için mutasyon
mutation OptimizeMessage($message: String!, $groupId: Int!) {
  optimize_message(message: $message, group_id: $groupId) {
    original_message
    optimized_message
    applied_optimizations {
      type
      message
    }
    recommendations {
      type
      message
    }
  }
}
```

#### SSE (Server-Sent Events)
- `/api/sse` - Gerçek zamanlı olaylar için endpoint
- Konulara abone olma: `/api/sse/subscribe/{client_id}/{topic}`
- Belirli bir konuya mesaj gönderme: `/api/sse/publish/{topic}`

### 4. UI Bileşenleri
- Grup kart bileşeni (istatistikler ve eylemlerle)
- Metrik grafiği bileşeni (Chart.js ile)
- AI önerisi bileşeni (içerik optimizasyonu için)
- Gerçek zamanlı bildirim bileşeni (Toast)
- Mesaj düzenleyici (emoji, medya ve biçimlendirme araçlarıyla)
- SSE bağlantı durumu göstergesi

### 5. İleri Özellikler
- AI temelli içerik öneri motoru entegrasyonu
- Mesaj performans karşılaştırma aracı
- A/B testi arayüzü (farklı mesaj türlerini test etmek için)
- İnteraktif grup analiz paneli
- Görüntü ve medya analizi
- Bağlamsal yanıt önerileri (grup içeriğine göre)

## Tasarım Rehberi
- Modern ve temiz arayüz
- Yüksek kontrast seçenekleriyle erişilebilirlik
- Etkileşimli ve responsive grafikler
- AI özelliklerini vurgulayan görsel ipuçları
- Kullanıcı akışlarını basitleştiren sezgisel tasarım
- Mesaj ve grup analizleri için görsel vurgu

## Backend API Bilgileri
- API Temel URL: `http://localhost:8000`
- API Dokümanları: `/docs` veya `/redoc` 
- GraphQL Arayüzü: `/api/v1/graphql`

## Örnek İstek ve Yanıtlar

### AI İçerik Optimizasyonu İsteği
```javascript
// Mesaj optimizasyonu örneği
async function optimizeMessage(message, groupId) {
  const response = await fetch('/api/v1/ai/optimize-message', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      message: message,
      group_id: groupId
    })
  });
  
  return await response.json();
}
```

### GraphQL ile Grup İçgörüleri
```javascript
// Apollo Client ile grup içgörüleri sorgusu
const GET_GROUP_INSIGHTS = gql`
  query GetGroupInsights($groupId: Int!) {
    group_content_insights(group_id: $groupId) {
      status
      message_count
      success_rate
      recommendations {
        type
        message
      }
    }
  }
`;

// Sorguyu kullanma
const { loading, error, data } = useQuery(GET_GROUP_INSIGHTS, {
  variables: { groupId: 123456789 }
});
```

## Güvenlik Önlemleri
- Tüm HTTP isteklerinde JWT token doğrulaması 
- GraphQL sorgularında rate limiting
- Hassas verileri taşımak için HTTPS kullanımı
- Form validasyonları ve XSS korumaları
- API isteklerinde hata işleme ve yeniden deneme stratejileri

## SSE Kullanımı
```javascript
// SSE bağlantısı kurma
function setupSSEConnection(clientId) {
  const eventSource = new EventSource('/api/sse');
  
  eventSource.onopen = () => {
    console.log('SSE bağlantısı kuruldu');
    
    // Konulara abone ol
    fetch(`/api/sse/subscribe/${clientId}/group_updates`, { method: 'POST' });
  };
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Gelen verileri işle
    console.log('SSE veri alındı:', data);
  };
  
  eventSource.onerror = (error) => {
    console.error('SSE bağlantı hatası:', error);
    // Yeniden bağlan
    setTimeout(() => setupSSEConnection(clientId), 5000);
  };
  
  return eventSource;
}
```

## Önbellek Stratejisi
- Apollo Client önbelleği ile GraphQL yanıtlarını saklama
- Yerel depolama ile kullanıcı tercihlerini saklama
- SSE verilerini geçici olarak önbellekleme
- Metrik verilerini belirli aralıklarla güncelleme

Bu rehber, MicroBot backend API'sine bağlanan güçlü ve kullanıcı dostu bir frontend uygulaması geliştirmenize yardımcı olacaktır. Uygulamanın tam potansiyelini ortaya çıkarmak için AI destekli içerik optimizasyonu, grup analizi ve performans izleme özelliklerine odaklanın. 