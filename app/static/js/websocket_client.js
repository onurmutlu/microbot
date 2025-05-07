/**
 * DEPRECATED - Bu dosya artık kullanımdan kaldırılıyor
 * 
 * WebSocket istemci kodları backend API projesinin bir parçası olmamalıdır.
 * Frontend uygulamanızda kendi WebSocket istemci kodlarınızı uygulamanız önerilir.
 * 
 * Backend, WebSocket API sunucu tarafını sağlamaya devam edecektir, ancak
 * istemci kodları artık frontend projesi içinde geliştirilmelidir.
 * 
 * @deprecated Bu modül kaldırılacak. Frontend projesinde kendi WebSocket istemcinizi kullanın.
 */

/**
 * WebSocket İstemcisi
 * 
 * Bu sınıf, sunucu ile WebSocket bağlantısı kurmak ve gerçek zamanlı veri alışverişi için kullanılır.
 * Çift yönlü iletişim için uygundur ve SSE'den daha karmaşık bir yapıya sahiptir.
 */
class WebSocketClient {
    /**
     * WebSocket istemcisi oluşturur
     * 
     * @param {string} url - WebSocket endpoint URL'i (örn: "ws://example.com/ws")
     * @param {Object} options - İstemci seçenekleri
     * @param {boolean} options.autoReconnect - Bağlantı kesildiğinde otomatik yeniden bağlansın mı
     * @param {number} options.reconnectDelay - Yeniden bağlanma gecikmesi (ms)
     * @param {number} options.maxReconnectAttempts - Maksimum yeniden bağlanma denemesi
     * @param {number} options.pingInterval - Ping mesajı gönderme aralığı (ms)
     * @param {boolean} options.debug - Debug modunu etkinleştir
     */
    constructor(url, options = {}) {
        this.url = url;
        this.options = Object.assign({
            autoReconnect: true,
            reconnectDelay: 3000,
            maxReconnectAttempts: 5,
            pingInterval: 30000, // 30 saniye
            debug: false
        }, options);
        
        // İç durum değişkenleri
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.pingInterval = null;
        this.lastPingTime = 0;
        this.lastPongTime = 0;
        
        // Event handler'ları
        this.messageHandlers = {};
        this.connectionStateHandlers = {
            open: [],
            close: [],
            error: []
        };
        
        // Mesaj kuyruğu (bağlantı yokken gönderilemeyen mesajlar için)
        this.messageQueue = [];
        
        // Debug modu
        this.debug = this.options.debug;
    }
    
    /**
     * WebSocket sunucusuna bağlanır
     * 
     * @returns {Promise<boolean>} Bağlantı başarılı olursa true, değilse false
     */
    connect() {
        return new Promise((resolve, reject) => {
            try {
                // Eğer zaten bağlıysa, mevcut bağlantıyı kapat
                if (this.socket) {
                    this.disconnect();
                }
                
                this._log("WebSocket bağlantısı başlatılıyor:", this.url);
                
                // Yeni WebSocket oluştur
                this.socket = new WebSocket(this.url);
                
                // Bağlantı açıldığında
                this.socket.onopen = (event) => {
                    this._log("WebSocket bağlantısı açıldı", event);
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    
                    // Bağlantı açılma handler'larını çağır
                    this._triggerConnectionStateHandlers('open', event);
                    
                    // Bağlantı canlı tutmak için ping göndermeye başla
                    this._startPingInterval();
                    
                    // Kuyrukta bekleyen mesajları gönder
                    this._sendQueuedMessages();
                    
                    resolve(true);
                };
                
                // Bağlantı kapandığında
                this.socket.onclose = (event) => {
                    this._log("WebSocket bağlantısı kapandı", event);
                    this.isConnected = false;
                    
                    // Ping interval'i durdur
                    this._stopPingInterval();
                    
                    // Bağlantı kapanma handler'larını çağır
                    this._triggerConnectionStateHandlers('close', event);
                    
                    // Otomatik yeniden bağlanma
                    if (this.options.autoReconnect && this.reconnectAttempts < this.options.maxReconnectAttempts) {
                        this.reconnectAttempts++;
                        this._log(`Yeniden bağlanılıyor... (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`);
                        
                        // Gecikme sonra yeniden bağlan
                        setTimeout(() => {
                            this.connect().catch(err => {
                                this._log("Yeniden bağlanma hatası", err, 'error');
                            });
                        }, this.options.reconnectDelay);
                    } else if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
                        this._log("Maksimum yeniden bağlanma denemesi aşıldı", null, 'error');
                        reject(new Error("Maksimum yeniden bağlanma denemesi aşıldı"));
                    }
                };
                
                // Bağlantı hatası olduğunda
                this.socket.onerror = (event) => {
                    this._log("WebSocket bağlantı hatası", event, 'error');
                    
                    // Hata handler'larını çağır
                    this._triggerConnectionStateHandlers('error', event);
                    
                    reject(new Error("WebSocket bağlantı hatası"));
                };
                
                // Mesaj geldiğinde
                this.socket.onmessage = (event) => {
                    this._handleMessage(event);
                };
                
            } catch (error) {
                this._log("WebSocket bağlantı hatası:", error, 'error');
                reject(error);
            }
        });
    }
    
    /**
     * WebSocket bağlantısını kapatır
     */
    disconnect() {
        this._stopPingInterval();
        
        if (this.socket) {
            // Sadece açık bağlantıları kapat
            if (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING) {
                this.socket.close(1000, "Istemci tarafından kapatıldı");
            }
            
            this.socket = null;
            this.isConnected = false;
            
            // Kapatma handler'larını çağır
            this._triggerConnectionStateHandlers('close', null);
            
            this._log("WebSocket bağlantısı kapatıldı");
        }
    }
    
    /**
     * WebSocket üzerinden mesaj gönderir
     * 
     * @param {string|Object} message - Gönderilecek mesaj
     * @param {string} [type='message'] - Mesaj türü
     * @returns {boolean} - Mesaj başarıyla gönderildiyse true
     */
    send(message, type = 'message') {
        // Nesne tipinde mesajlar için JSON hazırla
        const payload = typeof message === 'object' 
            ? Object.assign({ type }, message) 
            : { type, content: message };
            
        // Mesajı JSON string'e dönüştür
        const data = JSON.stringify(payload);
        
        // Bağlantı açıksa mesajı gönder
        if (this.isConnected && this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(data);
            this._log("Mesaj gönderildi:", payload);
            return true;
        } else {
            // Bağlantı yoksa mesajı kuyruğa ekle
            this._log("Bağlantı yok, mesaj kuyruğa eklendi:", payload);
            this.messageQueue.push(data);
            return false;
        }
    }
    
    /**
     * Ping mesajı gönderir
     * 
     * @private
     */
    _sendPing() {
        this.lastPingTime = Date.now();
        this.send({ 
            type: 'ping', 
            timestamp: this.lastPingTime 
        });
    }
    
    /**
     * Mesajları dinlemek için handler ekler
     * 
     * @param {string} type - Mesaj türü ('message', 'ping', 'pong', vb.)
     * @param {Function} handler - Mesaj işleyici fonksiyon
     */
    on(type, handler) {
        if (!this.messageHandlers[type]) {
            this.messageHandlers[type] = [];
        }
        
        this.messageHandlers[type].push(handler);
        
        // Handler'ı kaldırmak için bir fonksiyon döndür
        return () => {
            this.off(type, handler);
        };
    }
    
    /**
     * Mesaj handler'ını kaldırır
     * 
     * @param {string} type - Mesaj türü
     * @param {Function} handler - Kaldırılacak handler fonksiyonu
     */
    off(type, handler) {
        if (this.messageHandlers[type]) {
            const index = this.messageHandlers[type].indexOf(handler);
            if (index !== -1) {
                this.messageHandlers[type].splice(index, 1);
            }
        }
    }
    
    /**
     * Bağlantı durumu olayları için dinleyici ekler
     * 
     * @param {string} state - Bağlantı durumu ('open', 'close', 'error')
     * @param {Function} handler - Durum değişikliği işleyici fonksiyonu
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
     * @param {string} state - Bağlantı durumu ('open', 'close', 'error')
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
     * Ping interval'i başlatır
     * 
     * @private
     */
    _startPingInterval() {
        this._stopPingInterval();
        
        // Düzenli ping gönder
        this.pingInterval = setInterval(() => {
            if (this.isConnected) {
                this._sendPing();
            }
        }, this.options.pingInterval);
    }
    
    /**
     * Ping interval'i durdurur
     * 
     * @private
     */
    _stopPingInterval() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }
    
    /**
     * Kuyrukta bekleyen mesajları gönderir
     * 
     * @private
     */
    _sendQueuedMessages() {
        if (this.messageQueue.length > 0 && this.isConnected) {
            this._log(`Kuyrukta bekleyen ${this.messageQueue.length} mesaj gönderiliyor`);
            
            while (this.messageQueue.length > 0) {
                const message = this.messageQueue.shift();
                this.socket.send(message);
            }
        }
    }
    
    /**
     * Gelen mesajları işler
     * 
     * @param {MessageEvent} event - WebSocket mesaj olayı
     * @private
     */
    _handleMessage(event) {
        try {
            // JSON mesajını ayrıştır
            const data = JSON.parse(event.data);
            
            // Pong mesajı gelirse zamanı kaydet
            if (data.type === 'pong') {
                this.lastPongTime = Date.now();
                const latency = this.lastPongTime - this.lastPingTime;
                this._log(`Pong alındı, latency: ${latency}ms`);
            }
            
            // Ping mesajı gelirse pong gönder
            if (data.type === 'ping') {
                this.send({ 
                    type: 'pong', 
                    timestamp: Date.now(),
                    echo: data.timestamp 
                });
            }
            
            // Mesajın türüne göre ilgili handler'ları çağır
            const messageType = data.type || 'message';
            
            // İlgili event tipi için handler'ları çağır
            this._triggerMessageHandlers(messageType, data);
            
            // Genel mesaj handler'larını da çağır
            if (messageType !== 'message') {
                this._triggerMessageHandlers('message', data);
            }
            
        } catch (error) {
            this._log("Mesaj işleme hatası:", error, 'error');
            this._log("Mesaj:", event.data, 'error');
        }
    }
    
    /**
     * Belirli bir mesaj türü için tüm handler'ları çağırır
     * 
     * @param {string} type - Mesaj türü
     * @param {Object} data - Mesaj verisi
     * @private
     */
    _triggerMessageHandlers(type, data) {
        if (this.messageHandlers[type]) {
            this.messageHandlers[type].forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    this._log(`Handler çağırma hatası (${type}):`, error, 'error');
                }
            });
        }
    }
    
    /**
     * Bağlantı durumu handler'larını çağırır
     * 
     * @param {string} state - Bağlantı durumu ('open', 'close', 'error')
     * @param {Event} event - Olay nesnesi
     * @private
     */
    _triggerConnectionStateHandlers(state, event) {
        if (this.connectionStateHandlers[state]) {
            this.connectionStateHandlers[state].forEach(handler => {
                try {
                    handler(event);
                } catch (error) {
                    this._log(`Bağlantı durumu handler çağırma hatası (${state}):`, error, 'error');
                }
            });
        }
    }
    
    /**
     * Debug log'ları
     * 
     * @param {string} message - Log mesajı
     * @param {*} data - Log verisi
     * @param {string} [level='log'] - Log seviyesi ('log', 'error', 'warn', 'info')
     * @private
     */
    _log(message, data = null, level = 'log') {
        if (this.debug) {
            const timestamp = new Date().toISOString();
            const prefix = `[WebSocketClient ${timestamp}]`;
            
            if (data !== null) {
                console[level](prefix, message, data);
            } else {
                console[level](prefix, message);
            }
        }
    }
}

// Global WebSocket istemcisi örneği
let globalWSClient = null;

/**
 * WebSocket istemcisi oluşturup bağlantı kurar
 * 
 * @param {string} clientId - İstemci kimliği
 * @param {Object} options - WebSocket istemci seçenekleri
 * @returns {WebSocketClient} WebSocket istemci örneği
 */
function initWebSocket(clientId, options = {}) {
    // Eğer varsa mevcut bağlantıyı kapat
    if (globalWSClient) {
        globalWSClient.disconnect();
    }
    
    // WebSocket URL'ini oluştur
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/api/ws/${clientId}`;
    
    // Yeni WebSocket istemcisi oluştur
    globalWSClient = new WebSocketClient(url, options);
    
    // Bağlantıyı başlat
    globalWSClient.connect().catch(error => {
        console.error("WebSocket bağlantı hatası:", error);
    });
    
    return globalWSClient;
}

// Örnek kullanım:
/*
document.addEventListener('DOMContentLoaded', function() {
    // Rastgele bir client ID oluştur
    const clientId = 'user_' + Math.random().toString(36).substring(2, 10);
    
    // WebSocket istemcisini başlat
    const wsClient = initWebSocket(clientId, {
        debug: true,
        pingInterval: 10000 // 10 saniye
    });
    
    // Mesaj olaylarını dinle
    wsClient.on('message', function(data) {
        console.log('Yeni mesaj:', data);
    });
    
    // Bağlantı açıldığında
    wsClient.onConnectionState('open', function() {
        console.log('WebSocket bağlantısı açıldı');
        
        // Örnek mesaj gönder
        wsClient.send({
            action: 'hello',
            name: 'John Doe'
        });
    });
    
    // Bağlantı kapandığında
    wsClient.onConnectionState('close', function() {
        console.log('WebSocket bağlantısı kapandı');
    });
    
    // Bir butona tıklandığında mesaj gönder
    document.getElementById('send-button').addEventListener('click', function() {
        const message = document.getElementById('message-input').value;
        wsClient.send({ content: message, action: 'chat' });
        document.getElementById('message-input').value = '';
    });
});
*/ 