/**
 * Утилиты для работы с аутентификацией
 * Используется в фронтенде для управления JWT токенами
 */

const AuthUtils = {
    /**
     * Получить токен из localStorage
     */
    getToken() {
        return localStorage.getItem('access_token');
    },

    /**
     * Сохранить токен в localStorage
     */
    setToken(token, username, role) {
        localStorage.setItem('access_token', token);
        if (username) localStorage.setItem('username', username);
        if (role) localStorage.setItem('role', role);
    },

    /**
     * Удалить токен из localStorage
     */
    clearToken() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('username');
        localStorage.removeItem('role');
    },

    /**
     * Проверить, авторизован ли пользователь
     */
    isAuthenticated() {
        return !!this.getToken();
    },

    /**
     * Получить информацию о текущем пользователе
     */
    async getCurrentUser() {
        const token = this.getToken();
        if (!token) return null;

        try {
            const response = await fetch('/auth/me', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                return await response.json();
            } else {
                // Токен невалиден, очищаем
                this.clearToken();
                return null;
            }
        } catch (error) {
            console.error('Ошибка получения информации о пользователе:', error);
            return null;
        }
    },

    /**
     * Создать заголовок Authorization для fetch запросов
     */
    getAuthHeader() {
        const token = this.getToken();
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    },

    /**
     * Выполнить авторизованный fetch запрос
     */
    async fetch(url, options = {}) {
        const headers = {
            ...this.getAuthHeader(),
            ...(options.headers || {})
        };

        const response = await window.fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...headers
            }
        });

        // Если получили 401, токен истек - очищаем и перенаправляем на логин
        if (response.status === 401) {
            this.clearToken();
            window.location.href = '/login';
            throw new Error('Требуется авторизация');
        }

        return response;
    },

    /**
     * Выйти из системы
     */
    async logout() {
        try {
            // Вызываем эндпоинт logout для очистки session на сервере
            await fetch('/auth/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...this.getAuthHeader()
                }
            });
        } catch (error) {
            console.error('Ошибка при выходе:', error);
        } finally {
            // Очищаем токен и перенаправляем на страницу входа
            this.clearToken();
            window.location.href = '/login';
        }
    },

    /**
     * Проверить роль пользователя
     */
    hasRole(requiredRole) {
        const role = localStorage.getItem('role');
        return role === requiredRole;
    },

    /**
     * Проверить, является ли пользователь администратором
     */
    isAdmin() {
        return this.hasRole('admin');
    }
};

// Экспорт для использования в других скриптах
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuthUtils;
}

