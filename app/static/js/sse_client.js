/**
 * DEPRECATED - Bu dosya artık kullanımdan kaldırılıyor
 * 
 * SSE istemci kodları backend API projesinin bir parçası olmamalıdır.
 * Frontend uygulamanızda kendi SSE istemci kodlarınızı uygulamanız önerilir.
 * 
 * Backend, SSE API sunucu tarafını sağlamaya devam edecektir, ancak
 * istemci kodları artık frontend projesi içinde geliştirilmelidir.
 * 
 * @deprecated Bu modül kaldırılacak. Frontend projesinde kendi SSE istemcinizi kullanın.
 */

/**
 * Server-Sent Events (SSE) İstemcisi
 * 
 * Bu sınıf, sunucudan SSE kullanarak gerçek zamanlı veri almak için kullanılır.
 * WebSocket'e göre daha basit ve sadece sunucudan istemciye veri akışı için tasarlanmıştır.
 * 
 * @version 1.1.0
 * @license MIT
 * @author MicroBot Team
 */
class SSEClient {
    /**
     * SSE istemcisi oluşturur
     * 
     * @param {string} url - SSE endpoint URL'i (örn: "/api/sse/user123")
     * @param {Object} options - İstemci seçenekleri
     * @param {boolean} options.autoReconnect - Bağlantı kesildiğinde otomatik yeniden bağlansın mı
     * @param {number} options.reconnectDelay - Yeniden bağlanma gecikmesi (ms)
     * @param {number} options.maxReconnectAttempts - Maksimum yeniden bağlanma denemesi
     * @param {string} options.authToken - Kimlik doğrulama token'ı (opsiyonel)
     */
    constructor(url, options = {}) {
        this.url = url;
        this.options = Object.assign({
            autoReconnect: true,
            reconnectDelay: 3000,
            maxReconnectAttempts: 5,
            authToken: null
        }, options);
        
        // İç durum değişkenleri
        this.eventSource = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.eventHandlers = {
            "message": [],  // Genel mesajlar için handler'lar
            "connection": [], // Bağlantı mesajları
            "broadcast": [], // Broadcast mesajları 
            "topic_message": [], // Konu mesajları
            "ping": [],     // Ping mesajları
            "error": []     // Hata mesajları
        };
        
        // EventSource durumları için handler'lar
        this.connectionStateHandlers = {
            open: [],
            error: [],
            close: []
        };
    }
    
    /**
     * SSE sunucusuna bağlanır
     * 
     * @returns {Promise<boolean>} Bağlantı başarılı olursa true, değilse false
     */
    connect() {
        return new Promise((resolve, reject) => {
            try {
                // Eğer zaten bağlıysa, mevcut bağlantıyı kapat
                if (this.eventSource) {
                    this.disconnect();
                }
                
                // Bağlantı URL'ini oluştur
                let url = this.url;
                
                // URL'e auth token ekle (bazı sunucular query parametresi olarak token kabul eder)
                if (this.options.authToken && !url.includes('?')) {
                    url = `${url}?token=${encodeURIComponent(this.options.authToken)}`;
                }
                
                // Yeni EventSource oluştur
                this.eventSource = new EventSource(url);
                
                // Bağlantı açıldığında
                this.eventSource.onopen = (event) => {
                    console.log("SSE bağlantısı açıldı", event);
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    
                    // Bağlantı açılma handler'larını çağır
                    this._triggerConnectionStateHandlers('open', event);
                    
                    resolve(true);
                };
                
                // Bağlantı hatası olduğunda
                this.eventSource.onerror = async (event) => {
                    console.error("SSE bağlantı hatası", event);
                    this.isConnected = false;
                    
                    // Hata türünü belirle
                    const errorType = this._determineErrorType(event);
                    
                    // Hata handler'larını çağır
                    this._triggerConnectionStateHandlers('error', { event, errorType });
                    
                    // Bağlantıyı kapat
                    this.disconnect();
                    
                    // Otomatik yeniden bağlanma
                    if (this.options.autoReconnect && this.reconnectAttempts < this.options.maxReconnectAttempts) {
                        this.reconnectAttempts++;
                        
                        // Ağ hatası için daha uzun bekle
                        const delay = errorType === 'network' 
                            ? this.options.reconnectDelay * 2 
                            : this.options.reconnectDelay;
                        
                        console.log(`Yeniden bağlanılıyor... (${this.reconnectAttempts}/${this.options.maxReconnectAttempts}) - ${delay}ms sonra`);
                        
                        // Gecikme sonra yeniden bağlan
                        await new Promise(r => setTimeout(r, delay));
                        this.connect().catch(err => {
                            console.error("Yeniden bağlanma hatası", err);
                            reject(err);
                        });
                    } else if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
                        console.error("Maksimum yeniden bağlanma denemesi aşıldı");
                        reject(new Error("Maksimum yeniden bağlanma denemesi aşıldı"));
                    }
                };
                
                // Mesaj event handler'ı
                this.eventSource.onmessage = (event) => {
                    this._handleMessage(event);
                };
                
                // Özel event'lar için handler'lar ekle
                Object.keys(this.eventHandlers).forEach(eventType => {
                    if (eventType !== 'message') {
                        this.eventSource.addEventListener(eventType, (event) => {
                            this._handleEvent(eventType, event);
                        });
                    }
                });
                
            } catch (error) {
                console.error("SSE bağlantı hatası:", error);
                reject(error);
            }
        });
    }
    
    /**
     * SSE bağlantısını kapatır
     */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
            this.isConnected = false;
            
            // Kapatma handler'larını çağır
            this._triggerConnectionStateHandlers('close', null);
            
            console.log("SSE bağlantısı kapatıldı");
        }
    }
    
    /**
     * Mesaj olaylarını işler
     * 
     * @param {MessageEvent} event - SSE mesaj olayı
     * @private
     */
    _handleMessage(event) {
        try {
            // JSON mesajını ayrıştır
            const data = JSON.parse(event.data);
            
            // Mesajın türüne göre ilgili handler'ları çağır
            const messageType = data.type || 'message';
            
            // İlgili event tipi için handler'ları çağır
            this._triggerEventHandlers(messageType, data);
            
            // Konu bazlı mesaj filtresi
            if (data.topic) {
                this._triggerEventHandlers(`topic:${data.topic}`, data);
            }
            
            // Genel mesaj handler'larını da çağır
            if (messageType !== 'message') {
                this._triggerEventHandlers('message', data);
            }
            
        } catch (error) {
            console.error("Mesaj işleme hatası:", error, event.data);
        }
    }
    
    /**
     * Özel olayları işler
     * 
     * @param {string} eventType - Olay türü
     * @param {MessageEvent} event - SSE mesaj olayı
     * @private
     */
    _handleEvent(eventType, event) {
        try {
            // JSON mesajını ayrıştır
            const data = JSON.parse(event.data);
            
            // İlgili event tipi için handler'ları çağır
            this._triggerEventHandlers(eventType, data);
            
            // Genel mesaj handler'larını da çağır
            this._triggerEventHandlers('message', data);
            
        } catch (error) {
            console.error(`Özel olay (${eventType}) işleme hatası:`, error, event.data);
        }
    }
    
    /**
     * Belirli bir event türü için tüm handler'ları çağırır
     * 
     * @param {string} eventType - Event türü
     * @param {Object} data - Event verisi
     * @private
     */
    _triggerEventHandlers(eventType, data) {
        if (this.eventHandlers[eventType]) {
            this.eventHandlers[eventType].forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Handler çağırma hatası (${eventType}):`, error);
                }
            });
        }
    }
    
    /**
     * Bağlantı durumu handler'larını çağırır
     * 
     * @param {string} state - Bağlantı durumu ('open', 'error', 'close')
     * @param {Event} event - Olay nesnesi
     * @private
     */
    _triggerConnectionStateHandlers(state, event) {
        if (this.connectionStateHandlers[state]) {
            this.connectionStateHandlers[state].forEach(handler => {
                try {
                    handler(event);
                } catch (error) {
                    console.error(`Bağlantı durumu handler çağırma hatası (${state}):`, error);
                }
            });
        }
    }
    
    /**
     * Belirli bir tür mesaj için event handler'ı ekler
     * 
     * @param {string} eventType - Mesaj türü ('message', 'broadcast', 'ping', vb.)
     * @param {Function} handler - Mesaj işleyici fonksiyon
     * @returns {Function} Handler'ı kaldırmak için çağrılabilecek fonksiyon
     */
    on(eventType, handler) {
        if (!this.eventHandlers[eventType]) {
            this.eventHandlers[eventType] = [];
        }
        
        this.eventHandlers[eventType].push(handler);
        
        // Handler'ı kaldırmak için bir fonksiyon döndür
        return () => {
            this.off(eventType, handler);
        };
    }
    
    /**
     * Belirli bir tür mesaj için event handler'ı kaldırır
     * 
     * @param {string} eventType - Mesaj türü
     * @param {Function} handler - Kaldırılacak handler fonksiyonu
     */
    off(eventType, handler) {
        if (this.eventHandlers[eventType]) {
            const index = this.eventHandlers[eventType].indexOf(handler);
            if (index !== -1) {
                this.eventHandlers[eventType].splice(index, 1);
            }
        }
    }
    
    /**
     * Bağlantı durumu olayları için dinleyici ekler
     * 
     * @param {string} state - Bağlantı durumu ('open', 'error', 'close')
     * @param {Function} handler - Durum değişikliği işleyici fonksiyonu
     * @returns {Function} Handler'ı kaldırmak için çağrılabilecek fonksiyon
     */
    onConnectionState(state, handler) {
        if (!this.connectionStateHandlers[state]) {
            this.connectionStateHandlers[state] = [];
        }
        
        this.connectionStateHandlers[state].push(handler);
        
        // Handler'ı kaldırmak için bir fonksiyon döndür
        return () => {
            this.offConnectionState(state, handler);
        };
    }
    
    /**
     * Bağlantı durumu event handler'ını kaldırır
     * 
     * @param {string} state - Bağlantı durumu ('open', 'error', 'close')
     * @param {Function} handler - Kaldırılacak handler fonksiyonu
     */
    offConnectionState(state, handler) {
        if (this.connectionStateHandlers[state]) {
            const index = this.connectionStateHandlers[state].indexOf(handler);
            if (index !== -1) {
                this.connectionStateHandlers[state].splice(index, 1);
            }
        }
    }
    
    /**
     * Belirli bir konuya abone olur
     * 
     * @param {string} topic - Abone olunacak konu
     * @returns {Promise<Object>} - Abonelik sonucu 
     */
    async subscribeTopic(topic) {
        const clientId = this._extractClientId();
        if (!clientId) {
            throw new Error("Geçerli bir client ID bulunamadı");
        }
        
        try {
            const headers = {
                'Content-Type': 'application/json'
            };
            
            // Eğer auth token varsa ekle
            if (this.options.authToken) {
                headers['Authorization'] = `Bearer ${this.options.authToken}`;
            }
            
            const response = await fetch(`/api/sse/subscribe/${clientId}/${topic}`, {
                method: 'POST',
                headers: headers
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || "Konuya abone olma hatası");
            }
            
            return await response.json();
        } catch (error) {
            console.error("Konuya abone olma hatası:", error);
            throw error;
        }
    }
    
    /**
     * URL'den client ID'yi çıkarır
     * 
     * @returns {string|null} - Client ID veya null
     * @private
     */
    _extractClientId() {
        // Client ID genellikle URL'deki son parçadır (/api/sse/{client_id})
        const parts = this.url.split('/');
        return parts[parts.length - 1] || null;
    }
    
    /**
     * Token ile kimlik doğrulama ayarları
     * 
     * @param {string} token - Bearer token
     */
    setAuthToken(token) {
        this.options.authToken = token;
    }
    
    /**
     * Kimlik doğrulama token'ını temizler
     */
    clearAuthToken() {
        this.options.authToken = null;
    }
    
    /**
     * Hata türünü belirler
     * 
     * @param {Event} event - Hata olayı
     * @returns {string} - Hata türü ('network', 'auth', 'timeout', 'server', 'unknown')
     * @private
     */
    _determineErrorType(event) {
        if (!navigator.onLine) {
            return 'network';
        }
        
        if (event && event.target) {
            // ReadyState 0 genellikle bağlantı kurulmadan önce oluşan ağ sorunlarını gösterir
            if (event.target.readyState === 0) {
                return 'network';
            }
            
            // ReadyState 2 genellikle sunucu bağlantıyı kapatmış demektir
            if (event.target.readyState === 2) {
                return 'server';
            }
        }
        
        return 'unknown';
    }
    
    /**
     * Bağlantı durumunu kontrol eder
     * 
     * @returns {boolean} - Bağlantı durumu
     */
    isConnectionActive() {
        return this.isConnected && 
               this.eventSource && 
               this.eventSource.readyState === EventSource.OPEN;
    }
    
    /**
     * Bağlantı durumunu metin olarak döndürür
     * 
     * @returns {string} - Bağlantı durumu ('connected', 'connecting', 'disconnected')
     */
    getConnectionStatus() {
        if (!this.eventSource) {
            return 'disconnected';
        }
        
        switch (this.eventSource.readyState) {
            case EventSource.CONNECTING:
                return 'connecting';
            case EventSource.OPEN:
                return 'connected';
            default:
                return 'disconnected';
        }
    }
    
    /**
     * Belirli bir konudaki mesajlar için dinleyici ekler
     * 
     * @param {string} topic - Dinlenecek konu adı
     * @param {Function} handler - Konu mesajı işleyici fonksiyonu
     * @returns {Function} Handler'ı kaldırmak için çağrılabilecek fonksiyon
     */
    onTopic(topic, handler) {
        return this.on(`topic:${topic}`, handler);
    }
    
    /**
     * Belirli bir konuyu dinlemeyi durdurur
     * 
     * @param {string} topic - Dinlenecek konu adı
     * @param {Function} handler - Kaldırılacak handler fonksiyonu
     */
    offTopic(topic, handler) {
        this.off(`topic:${topic}`, handler);
    }
    
    /**
     * Bağlantıyı yeniler
     * 
     * @returns {Promise<boolean>} - Yeniden bağlantı başarılı olursa true, değilse false
     */
    async reconnect() {
        this.disconnect();
        return this.connect();
    }
    
    /**
     * Belirtilen konuya abone ol ve konudan gelen mesajları dinle
     * 
     * @param {string} topic - Abone olunacak konu
     * @param {Function} handler - Mesaj işleyici fonksiyonu
     * @returns {Promise<Object>} - İşlem sonucu
     */
    async subscribeAndListen(topic, handler) {
        // Önce dinleyiciyi ekle
        this.onTopic(topic, handler);
        
        // Sonra abonelik oluştur
        try {
            const result = await this.subscribeTopic(topic);
            return result;
        } catch (error) {
            // Hata durumunda dinleyiciyi kaldır
            this.offTopic(topic, handler);
            throw error;
        }
    }
    
    /**
     * Tüm konulardan ve dinleyicilerden çıkar
     */
    unsubscribeFromAllTopics() {
        // Dinleyicileri temizle
        Object.keys(this.eventHandlers).forEach(eventType => {
            if (eventType.startsWith('topic:')) {
                this.eventHandlers[eventType] = [];
            }
        });
        
        // Sunucu tarafında abonelikler otomatik olarak bağlantı kapatıldığında temizlenir
    }
}

// Global SSE istemcisi örneği
let globalSSEClient = null;

/**
 * SSE istemcisi oluşturup bağlantı kurar
 * 
 * @param {string} clientId - İstemci kimliği
 * @param {Object} options - SSE istemci seçenekleri
 * @returns {SSEClient} SSE istemci örneği
 */
function initSSE(clientId, options = {}) {
    // Eğer varsa mevcut bağlantıyı kapat
    if (globalSSEClient) {
        globalSSEClient.disconnect();
    }
    
    // Yeni SSE istemcisi oluştur
    const url = `/api/sse/${clientId}`;
    globalSSEClient = new SSEClient(url, options);
    
    // Bağlantıyı başlat
    globalSSEClient.connect().catch(error => {
        console.error("SSE bağlantı hatası:", error);
    });
    
    return globalSSEClient;
}

// Örnek kullanım:
/*
document.addEventListener('DOMContentLoaded', function() {
    // Rastgele bir client ID oluştur
    const clientId = 'user_' + Math.random().toString(36).substring(2, 10);
    
    // SSE istemcisini başlat
    const sseClient = initSSE(clientId);
    
    // Mesaj olaylarını dinle
    sseClient.on('message', function(data) {
        console.log('Yeni mesaj:', data);
    });
    
    // Broadcast mesajlarını dinle
    sseClient.on('broadcast', function(data) {
        console.log('Broadcast mesajı:', data);
        // UI güncelleme işlemleri burada yapılabilir
    });
    
    // Bağlantı açıldığında
    sseClient.onConnectionState('open', function() {
        console.log('SSE bağlantısı açıldı');
        // UI'da bağlantı durumunu göster
        document.getElementById('connection-status').textContent = 'Bağlı';
        document.getElementById('connection-status').className = 'connected';
    });
    
    // Bağlantı hatası olduğunda
    sseClient.onConnectionState('error', function() {
        console.log('SSE bağlantı hatası');
        // UI'da bağlantı durumunu göster
        document.getElementById('connection-status').textContent = 'Bağlantı hatası';
        document.getElementById('connection-status').className = 'error';
    });
    
    // Bağlantı kapandığında
    sseClient.onConnectionState('close', function() {
        console.log('SSE bağlantısı kapandı');
        // UI'da bağlantı durumunu göster
        document.getElementById('connection-status').textContent = 'Bağlantı kesildi';
        document.getElementById('connection-status').className = 'disconnected';
    });
    
    // Konuya abone ol
    sseClient.subscribeTopic('notifications')
        .then(result => {
            console.log('Konuya abone olundu:', result);
        })
        .catch(error => {
            console.error('Konuya abone olma hatası:', error);
        });
});
*/ 