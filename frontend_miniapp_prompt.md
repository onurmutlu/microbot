# MicroBot MiniApp Frontend Geliştirme Promptu

## Yeni Özellik: Zamanlanmış Mesaj Gönderimi Arayüzü

### Görev Tanımı

Telegram MicroBot MiniApp'e zamanlanmış mesaj gönderimi için kullanıcı arayüzü eklenmesi gerekiyor. Bu özellik, kullanıcıların belirlediği mesaj şablonlarını seçili gruplara otomatik olarak göndermelerini sağlayacak.

### Teknik Bilgiler

- **Backend API Endpoint'leri:**
  - `POST /api/scheduler/start` - Zamanlayıcıyı başlatma
  - `POST /api/scheduler/stop` - Zamanlayıcıyı durdurma
  - `GET /api/scheduler/status` - Zamanlayıcı durumunu kontrol etme

- **Backend Özellikleri:**
  - Her mesaj şablonu için `interval_minutes` değeri belirtilmeli (gönderim aralığı)
  - Sadece aktif şablonlar ve seçili gruplar otomatik gönderimde kullanılır
  - Son 24 saatte gönderilen mesaj sayısı izlenebilir

### Gerekli Bileşenler

1. **Zamanlayıcı Kontrol Paneli (`SchedulerControlPanel.tsx`)**
   - Zamanlayıcı başlatma/durdurma düğmeleri
   - Mevcut durum göstergesi (çalışıyor/durdu)
   - Son 24 saatte gönderilen mesaj sayısı
   - Aktif şablon sayısı

2. **Şablon Zamanlama Ayarları (`TemplateScheduleSettings.tsx`)**
   - Şablonlar için zamanlama aralığı seçimi (saat/dakika)
   - Aktif/pasif durum toggle'ı
   - Şablon önizleme

3. **Zamanlama Geçmişi (`ScheduleHistory.tsx`)**
   - Son gönderim zamanları
   - Başarı/başarısızlık oranları
   - Grup bazlı gönderim istatistikleri

4. **Yardımcı Servis (`schedulerService.ts`)**
   - API ile iletişim kuran servis fonksiyonları
   - Zamanlayıcı durumunu izleyen hook'lar

### Tasarım Gereksinimleri

- Telegram'ın tema renklerine uyumluluk
- Responsive tasarım (mobil öncelikli)
- Yükleme durumlarının gösterimi (loading states)
- Hata mesajları ve başarı bildirimleri
- Kolay kullanılabilir zaman seçiciler

### Kod Örneği: Zamanlayıcı Kontrol Bileşeni

```tsx
import React, { useState, useEffect } from 'react';
import { Button, Card, Badge, Spinner, Flex, Text, Box } from '@telegram-ui/react';
import { useSchedulerStatus, useStartScheduler, useStopScheduler } from '../../hooks/useScheduler';

export const SchedulerControlPanel: React.FC = () => {
  const { data: status, isLoading: statusLoading, refetch } = useSchedulerStatus();
  const startMutation = useStartScheduler();
  const stopMutation = useStopScheduler();
  
  const handleStart = async () => {
    await startMutation.mutateAsync();
    refetch();
  };
  
  const handleStop = async () => {
    await stopMutation.mutateAsync();
    refetch();
  };
  
  return (
    <Card className="scheduler-control">
      <Text size="lg" weight="bold">Zamanlanmış Mesaj Kontrolü</Text>
      
      <Flex direction="row" justify="space-between" align="center" className="mt-4">
        <Box>
          <Text>Durum:</Text>
          {statusLoading ? (
            <Spinner size="sm" />
          ) : (
            <Badge color={status?.is_running ? 'green' : 'gray'}>
              {status?.is_running ? 'Çalışıyor' : 'Durdu'}
            </Badge>
          )}
        </Box>
        
        <Box>
          <Text>Son 24 saat:</Text>
          <Badge color="blue">{status?.messages_last_24h || 0} mesaj</Badge>
        </Box>
        
        <Box>
          <Text>Aktif şablonlar:</Text>
          <Badge color="purple">{status?.active_templates || 0}</Badge>
        </Box>
      </Flex>
      
      <Flex gap="2" className="mt-4">
        <Button 
          onClick={handleStart}
          isLoading={startMutation.isLoading}
          isDisabled={status?.is_running || startMutation.isLoading || stopMutation.isLoading}
          colorScheme="green"
          className="flex-1"
        >
          Başlat
        </Button>
        
        <Button 
          onClick={handleStop}
          isLoading={stopMutation.isLoading}
          isDisabled={!status?.is_running || startMutation.isLoading || stopMutation.isLoading}
          colorScheme="red"
          className="flex-1"
        >
          Durdur
        </Button>
      </Flex>
    </Card>
  );
};
```

### Kod Örneği: Scheduler Service

```typescript
// src/services/schedulerService.ts
import { api } from './api';

export interface SchedulerStatus {
  is_running: boolean;
  active_templates: number;
  messages_last_24h: number;
  user_id: number;
  timestamp: string;
}

export const schedulerService = {
  getStatus: async (): Promise<SchedulerStatus> => {
    const response = await api.get('/api/scheduler/status');
    return response.data;
  },
  
  startScheduler: async (): Promise<any> => {
    const response = await api.post('/api/scheduler/start');
    return response.data;
  },
  
  stopScheduler: async (): Promise<any> => {
    const response = await api.post('/api/scheduler/stop');
    return response.data;
  }
};
```

### Kod Örneği: Custom Hooks

```typescript
// src/hooks/useScheduler.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { schedulerService, SchedulerStatus } from '../services/schedulerService';

export const useSchedulerStatus = () => {
  return useQuery<SchedulerStatus>(['scheduler', 'status'], 
    schedulerService.getStatus,
    { refetchInterval: 30000 } // 30 saniyede bir yenile
  );
};

export const useStartScheduler = () => {
  const queryClient = useQueryClient();
  
  return useMutation(schedulerService.startScheduler, {
    onSuccess: () => {
      queryClient.invalidateQueries(['scheduler', 'status']);
    }
  });
};

export const useStopScheduler = () => {
  const queryClient = useQueryClient();
  
  return useMutation(schedulerService.stopScheduler, {
    onSuccess: () => {
      queryClient.invalidateQueries(['scheduler', 'status']);
    }
  });
};
```

### Entegrasyon Adımları

1. Ana bileşenler oluştur:
   - `SchedulerControlPanel.tsx`
   - `TemplateScheduleSettings.tsx`
   - `ScheduleHistory.tsx`

2. API servisleri ve hook'ları ekle:
   - `schedulerService.ts`
   - `useScheduler.ts`

3. Navigasyon ve state management ekle:
   - Sidebar menüye "Zamanlayıcı" bölümü ekle
   - Global state'e zamanlayıcı durumunu ekle

4. Şablonlar sayfasına zamanlama ayarlarını ekle:
   - Şablon düzenleme formuna `interval_minutes` seçeneği ekle

5. Tema ve stil uyumluluğunu sağla:
   - Telegram tema renklerini kullan
   - MiniApp API entegrasyonunu kontrol et

6. Test ve hata yakalama:
   - Bileşenlerin tüm durumlarını test et
   - Hata işleme ve geri bildirim ekle

### Proje Klasör Yapısı (Eklenti)

```
src/
├── components/
│   ├── scheduler/
│   │   ├── SchedulerControlPanel.tsx
│   │   ├── TemplateScheduleSettings.tsx
│   │   └── ScheduleHistory.tsx
│   └── ...
├── hooks/
│   ├── useScheduler.ts
│   └── ...
├── services/
│   ├── schedulerService.ts
│   └── ...
├── pages/
│   ├── SchedulerPage.tsx
│   └── ...
└── ...
```

Bu prompt doğrultusunda, MicroBot MiniApp için zamanlanmış mesaj gönderimi özelliğini ekleyebilir ve kullanıcı deneyimini zenginleştirebilirsiniz. 