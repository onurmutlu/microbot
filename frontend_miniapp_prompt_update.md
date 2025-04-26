# MicroBot MiniApp Geliştirme - Cron Zamanlaması UI

## Görev Tanımı

MicroBot MiniApp'e cron-style zamanlama desteği eklenmesi gerekiyor. Bu özellik, kullanıcıların mesaj şablonları için daha karmaşık zamanlama desenleri oluşturmasını sağlayacak.

## Yeni API Özellikleri

- `POST /api/scheduler/validate-cron` - Cron ifadesini doğrulama ve sonraki çalışma zamanlarını gösterme
- Mesaj şablonu oluşturma/güncelleme API'lerine `cron_expression` alanı eklendi
- Zamanlanmış mesaj servisi cron ifadelerini destekliyor

## Gerekli UI Bileşenleri

### 1. Cron İfadesi Editörü (`CronExpressionEditor.tsx`)

Kullanıcıların kolayca cron ifadeleri oluşturabilmeleri için görsel bir editör:

```tsx
import React, { useState, useEffect } from 'react';
import { Box, Text, Select, Tabs, Button, Alert } from '@telegram-ui/react';
import { useCronValidation } from '../../hooks/useCron';

type CronEditorProps = {
  value: string;
  onChange: (value: string) => void;
};

export const CronExpressionEditor: React.FC<CronEditorProps> = ({ value, onChange }) => {
  const [activeTab, setActiveTab] = useState<'simple' | 'advanced'>('simple');
  const [minute, setMinute] = useState<string>('0');
  const [hour, setHour] = useState<string>('9');
  const [day, setDay] = useState<string>('*');
  const [month, setMonth] = useState<string>('*');
  const [weekday, setWeekday] = useState<string>('1-5');
  const [customExpression, setCustomExpression] = useState<string>(value || '0 9 * * 1-5');
  
  const { isValidating, data, validate } = useCronValidation();
  
  // Basit modda değerler değiştiğinde cron ifadesini güncelle
  useEffect(() => {
    if (activeTab === 'simple') {
      const expression = `${minute} ${hour} ${day} ${month} ${weekday}`;
      setCustomExpression(expression);
      onChange(expression);
    }
  }, [minute, hour, day, month, weekday, activeTab]);
  
  // Gelişmiş modda manuel ifade değiştiğinde
  const handleCustomExpressionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCustomExpression(e.target.value);
  };
  
  // Gelişmiş moddaki ifadeyi kaydet
  const handleSaveCustomExpression = () => {
    onChange(customExpression);
    validate(customExpression);
  };
  
  // Yaygın zamanlamalar için hızlı seçim
  const presets = [
    { label: 'Hafta içi her sabah (09:00)', value: '0 9 * * 1-5' },
    { label: 'Her gün sabah (09:00)', value: '0 9 * * *' },
    { label: 'Her saatin başında', value: '0 * * * *' },
    { label: 'Her ayın ilk günü', value: '0 9 1 * *' },
    { label: 'Her Pazartesi', value: '0 9 * * 1' },
  ];
  
  return (
    <Box className="cron-editor">
      <Tabs 
        activeKey={activeTab} 
        onChange={(key) => setActiveTab(key as 'simple' | 'advanced')}
        items={[
          { key: 'simple', label: 'Basit' },
          { key: 'advanced', label: 'Gelişmiş' },
        ]}
      />
      
      {activeTab === 'simple' ? (
        <Box className="simple-editor">
          <Box className="editor-row">
            <Text>Dakika:</Text>
            <Select 
              value={minute} 
              onChange={(val) => setMinute(val)}
              options={[
                { label: 'Her dakika (*)', value: '*' },
                { label: 'Her 5 dakika (*/5)', value: '*/5' },
                { label: 'Her 15 dakika (*/15)', value: '*/15' },
                { label: 'Her 30 dakika (*/30)', value: '*/30' },
                { label: 'Tam saatte (0)', value: '0' },
              ]}
            />
          </Box>
          
          <Box className="editor-row">
            <Text>Saat:</Text>
            <Select 
              value={hour} 
              onChange={(val) => setHour(val)}
              options={[
                { label: 'Her saat (*)', value: '*' },
                { label: 'Sabah 9 (9)', value: '9' },
                { label: 'Öğle 12 (12)', value: '12' },
                { label: 'Akşam 17 (17)', value: '17' },
                { label: 'İş saatleri (9-17)', value: '9-17' },
              ]}
            />
          </Box>
          
          <Box className="editor-row">
            <Text>Günler:</Text>
            <Select 
              value={weekday} 
              onChange={(val) => setWeekday(val)}
              options={[
                { label: 'Her gün (*)', value: '*' },
                { label: 'Hafta içi (1-5)', value: '1-5' },
                { label: 'Hafta sonu (0,6)', value: '0,6' },
                { label: 'Pazartesi (1)', value: '1' },
                { label: 'Cuma (5)', value: '5' },
              ]}
            />
          </Box>
          
          <Box className="preset-selector">
            <Text>Hazır Kalıplar:</Text>
            <Select
              placeholder="Zamanlama seçin"
              onChange={(val) => {
                const preset = presets.find(p => p.value === val);
                if (preset) {
                  const [min, hr, dy, mth, wkd] = preset.value.split(' ');
                  setMinute(min);
                  setHour(hr);
                  setDay(dy);
                  setMonth(mth);
                  setWeekday(wkd);
                }
              }}
              options={presets.map(p => ({ label: p.label, value: p.value }))}
            />
          </Box>
        </Box>
      ) : (
        <Box className="advanced-editor">
          <Text>Cron İfadesi:</Text>
          <Box className="custom-expression-input">
            <input 
              type="text" 
              value={customExpression} 
              onChange={handleCustomExpressionChange} 
              placeholder="* * * * *"
            />
            <Button onClick={handleSaveCustomExpression}>Doğrula</Button>
          </Box>
          <Text className="cron-format-helper">
            Format: dakika saat gün ay haftanın_günü
          </Text>
        </Box>
      )}
      
      {data && (
        <Box className="validation-result">
          <Text weight="bold">Sonraki çalışma zamanları:</Text>
          {data.is_valid ? (
            <ul>
              {data.next_dates.map((date, index) => (
                <li key={index}>{new Date(date).toLocaleString('tr-TR')}</li>
              ))}
            </ul>
          ) : (
            <Alert type="error">
              Geçersiz cron ifadesi: {data.error}
            </Alert>
          )}
        </Box>
      )}
    </Box>
  );
};
```

### 2. Şablon Zamanlama Bileşeni (`TemplateScheduler.tsx`)

Mesaj şablonu formunda cron zamanlaması ve interval seçeneği:

```tsx
import React, { useState } from 'react';
import { Box, Text, Switch, InputNumber, Divider } from '@telegram-ui/react';
import { CronExpressionEditor } from './CronExpressionEditor';

type TemplateSchedulerProps = {
  initialIntervalMinutes?: number;
  initialCronExpression?: string;
  onUpdate: (data: { interval_minutes: number; cron_expression: string | null }) => void;
};

export const TemplateScheduler: React.FC<TemplateSchedulerProps> = ({ 
  initialIntervalMinutes = 60, 
  initialCronExpression = null, 
  onUpdate 
}) => {
  const [scheduleType, setScheduleType] = useState<'interval' | 'cron'>(
    initialCronExpression ? 'cron' : 'interval'
  );
  const [intervalMinutes, setIntervalMinutes] = useState(initialIntervalMinutes);
  const [cronExpression, setCronExpression] = useState(initialCronExpression || '0 9 * * 1-5');
  
  // Zamanlama türü değiştiğinde
  const handleScheduleTypeChange = (type: 'interval' | 'cron') => {
    setScheduleType(type);
    // Üst bileşene değişikliği bildir
    onUpdate({
      interval_minutes: intervalMinutes,
      cron_expression: type === 'cron' ? cronExpression : null
    });
  };
  
  // Interval değiştiğinde
  const handleIntervalChange = (value: number) => {
    setIntervalMinutes(value);
    if (scheduleType === 'interval') {
      onUpdate({
        interval_minutes: value,
        cron_expression: null
      });
    }
  };
  
  // Cron ifadesi değiştiğinde
  const handleCronChange = (value: string) => {
    setCronExpression(value);
    if (scheduleType === 'cron') {
      onUpdate({
        interval_minutes: intervalMinutes,
        cron_expression: value
      });
    }
  };
  
  return (
    <Box className="template-scheduler">
      <Text size="lg" weight="bold">Zamanlama Ayarları</Text>
      
      <Box className="schedule-type-selector">
        <Box>
          <Switch 
            checked={scheduleType === 'interval'} 
            onChange={() => handleScheduleTypeChange('interval')}
          />
          <Text>Basit Aralık</Text>
        </Box>
        
        <Box>
          <Switch 
            checked={scheduleType === 'cron'} 
            onChange={() => handleScheduleTypeChange('cron')}
          />
          <Text>Cron Zamanlama</Text>
        </Box>
      </Box>
      
      <Divider />
      
      {scheduleType === 'interval' ? (
        <Box className="interval-settings">
          <Text>Her</Text>
          <InputNumber 
            min={1} 
            max={10080} // 1 hafta
            value={intervalMinutes} 
            onChange={handleIntervalChange} 
          />
          <Text>dakikada bir gönder</Text>
          
          <Box className="interval-presets">
            <button onClick={() => handleIntervalChange(60)}>Saatlik</button>
            <button onClick={() => handleIntervalChange(60 * 24)}>Günlük</button>
            <button onClick={() => handleIntervalChange(60 * 24 * 7)}>Haftalık</button>
          </Box>
        </Box>
      ) : (
        <CronExpressionEditor value={cronExpression} onChange={handleCronChange} />
      )}
      
      <Box className="scheduler-help">
        <Text size="sm">
          Zamanlama hakkında daha fazla bilgi için 
          <a href="/docs/cron-guide" target="_blank">Cron Rehberi</a>'ne bakın.
        </Text>
      </Box>
    </Box>
  );
};
```

### 3. Cron Doğrulama Hook'u (`useCron.ts`)

```typescript
import { useState } from 'react';
import { api } from '../services/api';

interface CronValidationResult {
  is_valid: boolean;
  next_dates: string[];
  error: string | null;
}

export const useCronValidation = () => {
  const [isValidating, setIsValidating] = useState(false);
  const [data, setData] = useState<CronValidationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const validate = async (cronExpression: string) => {
    setIsValidating(true);
    setError(null);
    
    try {
      const response = await api.post('/api/scheduler/validate-cron', {
        cron_expression: cronExpression
      });
      setData(response.data);
    } catch (err) {
      setError('Cron ifadesi doğrulanırken bir hata oluştu.');
      console.error('Cron validation error:', err);
    } finally {
      setIsValidating(false);
    }
  };
  
  return {
    isValidating,
    data,
    error,
    validate
  };
};
```

## Şablon Form Güncellemesi

Mevcut template form bileşenine cron zamanlama desteği eklemek için:

```tsx
// Mevcut form içinde zamanlama bölümü güncellemesi
<FormSection title="Zamanlama">
  <TemplateScheduler
    initialIntervalMinutes={formData.interval_minutes}
    initialCronExpression={formData.cron_expression}
    onUpdate={(scheduleData) => {
      setFormData({
        ...formData,
        interval_minutes: scheduleData.interval_minutes,
        cron_expression: scheduleData.cron_expression
      });
    }}
  />
</FormSection>
```

## Cron Rehberi Sayfası (`CronGuidePage.tsx`)

```tsx
import React from 'react';
import { Box, Text, Table, Heading, Code } from '@telegram-ui/react';
import { PageContainer } from '../components/PageContainer';

export const CronGuidePage: React.FC = () => {
  return (
    <PageContainer title="Cron İfadeleri Rehberi">
      <Box className="cron-guide">
        <Heading level={1}>Cron İfadeleri Rehberi</Heading>
        <Text>
          MicroBot'ta zamanlanmış mesajlarınızı daha karmaşık kurallara göre göndermek için
          cron ifadelerini kullanabilirsiniz.
        </Text>
        
        <Heading level={2}>Cron Formatı</Heading>
        <Text>
          Cron ifadeleri, belirli görevlerin ne zaman çalıştırılacağını tanımlamak için 
          kullanılan bir zaman planlama sistemidir. Format 5 alandan oluşur:
        </Text>
        
        <Code block>
        {`* * * * *
│ │ │ │ │
│ │ │ │ └── Haftanın günü (0-6) (Pazar=0, Cumartesi=6)
│ │ │ └──── Ay (1-12)
│ │ └────── Ayın günü (1-31)
│ └──────── Saat (0-23)
└────────── Dakika (0-59)`}
        </Code>
        
        <Heading level={2}>Sık Kullanılan Örnekler</Heading>
        <Table
          columns={[
            { title: 'Cron İfadesi', dataIndex: 'expression', key: 'expression' },
            { title: 'Açıklama', dataIndex: 'description', key: 'description' },
          ]}
          dataSource={[
            { key: '1', expression: '*/5 * * * *', description: 'Her 5 dakikada bir' },
            { key: '2', expression: '0 * * * *', description: 'Her saatin başında (00 dakika)' },
            { key: '3', expression: '0 9 * * *', description: 'Her gün saat 09:00\'da' },
            { key: '4', expression: '0 9 * * 1-5', description: 'Hafta içi (Pazartesi-Cuma) saat 09:00\'da' },
            { key: '5', expression: '0 9 * * 1', description: 'Her Pazartesi saat 09:00\'da' },
            { key: '6', expression: '0 9-17 * * 1-5', description: 'Hafta içi, 09:00-17:00 arasında her saat başında' },
            { key: '7', expression: '0 9,17 * * *', description: 'Her gün saat 09:00 ve 17:00\'da' },
            { key: '8', expression: '0 0 1 * *', description: 'Her ayın ilk günü, gece yarısı' },
            { key: '9', expression: '0 0 * * 0', description: 'Her Pazar gece yarısı' },
          ]}
        />
        
        {/* Rehberin geri kalanı... */}
      </Box>
    </PageContainer>
  );
};
```

## Entegrasyon Adımları

1. `CronExpressionEditor`, `TemplateScheduler` ve diğer yardımcı bileşenleri oluşturun
2. `useCron` hook'unu implement edin
3. Mesaj şablonu oluşturma/düzenleme formlarını güncelleyin
4. Cron rehber sayfasını ekleyin ve navigasyona bağlayın
5. Şablon listesi görünümünde cron zamanlaması olan şablonları belirtin

## CSS Örnekleri

```css
/* Cron editörü stilleri */
.cron-editor {
  border: 1px solid var(--tg-theme-hint-color);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.simple-editor .editor-row {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.simple-editor .editor-row Text {
  width: 80px;
}

.validation-result {
  margin-top: 16px;
  padding: 12px;
  background-color: var(--tg-theme-bg-color);
  border-radius: 8px;
}

.validation-result ul {
  padding-left: 20px;
  margin: 8px 0;
}

.custom-expression-input {
  display: flex;
  gap: 8px;
  margin: 8px 0;
}

.custom-expression-input input {
  flex: 1;
  padding: 8px;
  border: 1px solid var(--tg-theme-hint-color);
  border-radius: 4px;
  font-family: monospace;
}

.cron-format-helper {
  font-size: 12px;
  color: var(--tg-theme-hint-color);
  margin-top: 4px;
}

.preset-selector {
  margin-top: 16px;
}

.interval-settings {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 0;
}

.interval-presets {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.interval-presets button {
  padding: 4px 12px;
  border-radius: 4px;
  background-color: var(--tg-theme-button-color);
  color: var(--tg-theme-button-text-color);
  border: none;
  cursor: pointer;
}
```

Bu prompt ile MicroBot MiniApp'e cron-style zamanlama desteği eklemek için gereken tüm bileşenleri ve örnekleri sağlamış olduk. Bu özellik kullanıcılarınıza çok daha esnek ve güçlü bir zamanlama seçeneği sunacaktır. 