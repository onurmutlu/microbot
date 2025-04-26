# Cron İfadeleri Rehberi

Bu rehber, MicroBot'ta zamanlanmış mesajlar için kullanabileceğiniz cron ifadelerini açıklar.

## Cron Formatı Nedir?

Cron ifadeleri, belirli görevlerin ne zaman çalıştırılacağını tanımlamak için kullanılan bir zaman planlama sistemidir. Format 5 alandan oluşur:

```
* * * * *
│ │ │ │ │
│ │ │ │ └── Haftanın günü (0-6) (Pazar=0, Cumartesi=6)
│ │ │ └──── Ay (1-12)
│ │ └────── Ayın günü (1-31)
│ └──────── Saat (0-23)
└────────── Dakika (0-59)
```

## Sık Kullanılan Örnekler

| Cron İfadesi | Açıklama |
|--------------|----------|
| `*/5 * * * *` | Her 5 dakikada bir |
| `0 * * * *` | Her saatin başında (00 dakika) |
| `0 9 * * *` | Her gün saat 09:00'da |
| `0 9 * * 1-5` | Hafta içi (Pazartesi-Cuma) saat 09:00'da |
| `0 9 * * 1` | Her Pazartesi saat 09:00'da |
| `0 9-17 * * 1-5` | Hafta içi, 09:00-17:00 arasında her saat başında |
| `0 9,17 * * *` | Her gün saat 09:00 ve 17:00'da |
| `0 0 1 * *` | Her ayın ilk günü, gece yarısı |
| `0 0 * * 0` | Her Pazar gece yarısı |
| `*/10 9-17 * * 1-5` | Hafta içi 09:00-17:00 arasında her 10 dakikada bir |

## Özel Karakterler

| Karakter | Açıklama |
|----------|----------|
| `*` | Tüm geçerli değerler |
| `,` | Değer listesi (örn. "1,3,5") |
| `-` | Değer aralığı (örn. "1-5") |
| `/` | Adım değeri (örn. "*/2" her iki dakikada bir) |

## Sık Kullanılan Senaryolar

### İş Saatleri İçinde Mesaj Gönderimi

- Her hafta içi sabah 9'da bildirim: `0 9 * * 1-5`
- Her hafta içi öğle molası: `0 12 * * 1-5`
- Her hafta içi akşam kapanış: `0 17 * * 1-5`

### Günlük Hatırlatmalar

- Her gün sabah 8'de günlük plan: `0 8 * * *`
- Her akşam 10'da günlük kapanış: `0 22 * * *`

### Haftalık Etkinlikler

- Her Pazartesi sabah haftalık özet: `0 9 * * 1`
- Her Cuma akşam hafta sonu planı: `0 17 * * 5`

### Aylık Toplantılar

- Her ayın ilk Pazartesi günü: `0 9 1-7 * 1`
- Her ayın son iş günü (yaklaşık): `0 15 25-31 * 1-5`

## Nasıl Test Edebilirim?

MicroBot'ta bir cron ifadesinin geçerliliğini kontrol etmek ve sonraki çalışma zamanlarını görmek için API endpoint'ini kullanabilirsiniz:

```
POST /api/scheduler/validate-cron
{
    "cron_expression": "0 9 * * 1-5"
}
```

Bu sorgu başarılı olursa, sonraki 5 çalışma zamanını göreceksiniz. 