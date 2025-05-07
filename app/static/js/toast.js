/**
 * DEPRECATED - Bu dosya artık kullanımdan kaldırılıyor
 * 
 * Bu toast bildirimi kodları backend API projesinin bir parçası olmamalıdır.
 * Bunun yerine, frontend projesinde kendi bildirim sistemini uygulamanız önerilir.
 * 
 * WebSocket ve SSE istemcilerine yapılan frontend toast bildirimleri referansları kaldırıldı.
 * Bu dosya sadece geriye dönük uyumluluk için tutulmaktadır ve yakında tamamen kaldırılacaktır.
 * 
 * @deprecated Bu modül kaldırılacak. Frontend projesinde kendi bildirim sisteminizi kullanın.
 */
 
class ToastManager {
    constructor(options = {}) {
        this.options = Object.assign({
            container: 'toast-container',
            position: 'top-right', // top-right, top-left, bottom-right, bottom-left
            autoClose: true,
            autoCloseDelay: 5000, // ms
            showProgress: true,
            closeOnClick: true,
            pauseOnHover: true,
            maxToasts: 5
        }, options);
        
        this.toasts = [];
        this.container = null;
        
        this._init();
    }
    
    _init() {
        // Toast container oluştur (eğer yoksa)
        let container = document.getElementById(this.options.container);
        if (!container) {
            container = document.createElement('div');
            container.id = this.options.container;
            container.className = `toast-container ${this.options.position}`;
            document.body.appendChild(container);
        }
        
        this.container = container;
        
        // CSS eklenmemişse ekle
        if (!document.getElementById('toast-style')) {
            const style = document.createElement('style');
            style.id = 'toast-style';
            style.textContent = `
                .toast-container {
                    position: fixed;
                    z-index: 9999;
                    padding: 15px;
                    width: 320px;
                    max-width: 100%;
                    box-sizing: border-box;
                }
                .toast-container.top-right {
                    top: 0;
                    right: 0;
                }
                .toast-container.top-left {
                    top: 0;
                    left: 0;
                }
                .toast-container.bottom-right {
                    bottom: 0;
                    right: 0;
                }
                .toast-container.bottom-left {
                    bottom: 0;
                    left: 0;
                }
                .toast {
                    position: relative;
                    background-color: #333;
                    color: #fff;
                    padding: 15px 35px 15px 15px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                    margin-bottom: 10px;
                    opacity: 0;
                    transform: translateY(-20px);
                    transition: all 0.3s ease;
                    overflow: hidden;
                }
                .toast.show {
                    opacity: 1;
                    transform: translateY(0);
                }
                .toast.closing {
                    opacity: 0;
                    height: 0;
                    padding-top: 0;
                    padding-bottom: 0;
                    margin-bottom: 0;
                    transition: all 0.3s ease;
                }
                .toast-success {
                    background-color: #4CAF50;
                }
                .toast-error {
                    background-color: #F44336;
                }
                .toast-warning {
                    background-color: #FF9800;
                }
                .toast-info {
                    background-color: #2196F3;
                }
                .toast-close {
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    width: 16px;
                    height: 16px;
                    cursor: pointer;
                    opacity: 0.6;
                }
                .toast-close:hover {
                    opacity: 1;
                }
                .toast-close:before, .toast-close:after {
                    position: absolute;
                    content: '';
                    width: 100%;
                    height: 2px;
                    background-color: #fff;
                    top: 50%;
                }
                .toast-close:before {
                    transform: rotate(45deg);
                }
                .toast-close:after {
                    transform: rotate(-45deg);
                }
                .toast-progress {
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    height: 4px;
                    background-color: rgba(255,255,255,0.4);
                    width: 100%;
                    transition: width linear;
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    /**
     * Toast bildirimi göster
     * @param {string} message - Gösterilecek mesaj
     * @param {string} type - Bildirim tipi (success, error, warning, info)
     * @param {Object} options - Ek seçenekler
     * @returns {Object} Oluşturulan toast nesnesi
     */
    show(message, type = 'info', options = {}) {
        // Eski toastları kaldır (maksimum sayıdan fazlaysa)
        if (this.toasts.length >= this.options.maxToasts) {
            this.dismiss(this.toasts[0].id);
        }
        
        // Toast oluşturma seçenekleri
        const toastOptions = Object.assign({}, this.options, options);
        
        // Toast elementini oluştur
        const toast = document.createElement('div');
        const id = 'toast-' + Date.now();
        toast.id = id;
        toast.className = `toast toast-${type}`;
        
        // Toast içeriğini oluştur
        toast.innerHTML = `
            <div class="toast-content">${message}</div>
            <div class="toast-close"></div>
            ${toastOptions.showProgress ? '<div class="toast-progress"></div>' : ''}
        `;
        
        // Kapatma butonuna tıklama olayı
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => this.dismiss(id));
        
        // Toast'a tıklama olayı (kapatmak için)
        if (toastOptions.closeOnClick) {
            toast.addEventListener('click', (e) => {
                if (e.target !== closeBtn) {
                    this.dismiss(id);
                }
            });
        }
        
        // Hover durumunda otomatik kapanmayı durdur
        if (toastOptions.pauseOnHover && toastOptions.autoClose) {
            toast.addEventListener('mouseenter', () => {
                const progressBar = toast.querySelector('.toast-progress');
                if (progressBar) {
                    progressBar.style.animationPlayState = 'paused';
                }
                clearTimeout(toast.closeTimeout);
            });
            
            toast.addEventListener('mouseleave', () => {
                const progressBar = toast.querySelector('.toast-progress');
                if (progressBar) {
                    progressBar.style.animationPlayState = 'running';
                }
                this._setAutoClose(toast, id, toastOptions.autoCloseDelay);
            });
        }
        
        // Toast'ı container'a ekle
        this.container.appendChild(toast);
        
        // Toast nesnesini kaydet
        const toastObj = { id, element: toast };
        this.toasts.push(toastObj);
        
        // Animasyon için timeout
        setTimeout(() => {
            toast.classList.add('show');
            
            // İlerleme çubuğunu ayarla
            if (toastOptions.showProgress && toastOptions.autoClose) {
                const progressBar = toast.querySelector('.toast-progress');
                progressBar.style.width = '100%';
                progressBar.style.transition = `width ${toastOptions.autoCloseDelay}ms linear`;
                
                // Animasyon bittiğinde width'i 0 yap
                setTimeout(() => {
                    if (progressBar) progressBar.style.width = '0%';
                }, 10);
            }
            
            // Otomatik kapanma
            if (toastOptions.autoClose) {
                this._setAutoClose(toast, id, toastOptions.autoCloseDelay);
            }
        }, 10);
        
        return toastObj;
    }
    
    /**
     * Toast için otomatik kapanma zamanlayıcısı ayarla
     */
    _setAutoClose(toast, id, delay) {
        // Var olan zamanlayıcıyı temizle
        if (toast.closeTimeout) {
            clearTimeout(toast.closeTimeout);
        }
        
        toast.closeTimeout = setTimeout(() => {
            this.dismiss(id);
        }, delay);
    }
    
    /**
     * Toast bildirimini kapat
     * @param {string} id - Kapatılacak toast ID'si
     */
    dismiss(id) {
        const index = this.toasts.findIndex(t => t.id === id);
        if (index !== -1) {
            const toast = this.toasts[index].element;
            
            // Zamanlayıcıları temizle
            if (toast.closeTimeout) {
                clearTimeout(toast.closeTimeout);
            }
            
            // Animasyonla kapat
            toast.classList.add('closing');
            toast.classList.remove('show');
            
            // Animasyon tamamlanınca DOM'dan kaldır
            setTimeout(() => {
                if (toast && toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
                this.toasts.splice(index, 1);
            }, 300);
        }
    }
    
    /**
     * Başarı toast'ı göster
     */
    success(message, options = {}) {
        return this.show(message, 'success', options);
    }
    
    /**
     * Hata toast'ı göster
     */
    error(message, options = {}) {
        return this.show(message, 'error', options);
    }
    
    /**
     * Uyarı toast'ı göster
     */
    warning(message, options = {}) {
        return this.show(message, 'warning', options);
    }
    
    /**
     * Bilgi toast'ı göster
     */
    info(message, options = {}) {
        return this.show(message, 'info', options);
    }
    
    /**
     * Tüm toastları kapat
     */
    dismissAll() {
        [...this.toasts].forEach(toast => {
            this.dismiss(toast.id);
        });
    }
}

// Global toast manager örneği
const toast = new ToastManager();

// Global fonksiyonlar
function showToast(message, type = 'info', options = {}) {
    return toast.show(message, type, options);
}

function showSuccessToast(message, options = {}) {
    return toast.success(message, options);
}

function showErrorToast(message, options = {}) {
    return toast.error(message, options);
}

function showWarningToast(message, options = {}) {
    return toast.warning(message, options);
}

function showInfoToast(message, options = {}) {
    return toast.info(message, options);
}

function dismissAllToasts() {
    toast.dismissAll();
} 