import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, CallbackContext
)
from telegram.constants import ParseMode
from aiohttp import web
import aiohttp

# =============== НАСТРОЙКИ ===============
@dataclass
class Config:
    BOT_TOKEN: str = "8562130677:AAFS3N3ls-POoDmq9uTC1D7XU7cijFChEg8"
    BOT_USERNAME: str = "StarsRaysbot"
    ADMIN_USERNAME: str = "Lyrne"
    ADMIN_PASSWORD: str = "sb39#$99haldB"
    PORT: int = int(os.environ.get('PORT', 8443))
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", f"https://{BOT_USERNAME}.bothost.ru")
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", f"https://{BOT_USERNAME}.bothost.app/")
    ENABLE_HTTP: bool = True
    HTTP_PORT: int = 8080

config = Config()

# =============== ХРАНИЛИЩЕ ДАННЫХ ===============
class DataStorage:
    """Простое хранилище данных в памяти с сохранением в файл"""
    def __init__(self):
        self.data_file = Path("bot_data.json")
        self.data = self.load_data()
        self.lock = asyncio.Lock()
    
    def load_data(self) -> Dict:
        """Загрузка данных из файла"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Error loading data: {e}")
        
        # Структура по умолчанию
        return {
            "users": {},
            "online_users": [],
            "stats": {
                "total_users": 0,
                "online_count": 0,
                "stars_given": 26500,
                "stars_total": 50000
            },
            "settings": {
                "channels_text": "😇 Чтобы забрать приз, выполни простое задание.\n\nПодпишись на эти каналы спонсоров 👇️\n@durov\n@telegram",
                "redirect_url": "https://share.google/images/nN32IC20Y2cYIEIkH",
                "raffle_end_time": (datetime.now() + timedelta(hours=6, minutes=34, seconds=41)).isoformat()
            },
            "winners": []
        }
    
    async def save_data(self):
        """Асинхронное сохранение данных"""
        async with self.lock:
            try:
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logging.error(f"Error saving data: {e}")
    
    async def add_user(self, user_id: int, username: str, first_name: str):
        """Добавление нового пользователя"""
        user_id_str = str(user_id)
        if user_id_str not in self.data["users"]:
            self.data["users"][user_id_str] = {
                "username": username,
                "first_name": first_name,
                "joined": datetime.now().isoformat(),
                "stars_won": 0,
                "last_seen": datetime.now().isoformat(),
                "tasks_completed": False,
                "prize_claimed": False,
                "current_page": "index"
            }
            self.data["stats"]["total_users"] = len(self.data["users"])
            await self.save_data()
    
    async def mark_user_online(self, user_id: int):
        """Отметить пользователя онлайн"""
        user_id_str = str(user_id)
        if user_id_str not in self.data["online_users"]:
            self.data["online_users"].append(user_id_str)
            self.data["stats"]["online_count"] = len(self.data["online_users"])
            await self.save_data()
    
    async def update_user_stars(self, user_id: int, stars: int):
        """Обновить количество выигранных звезд"""
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["stars_won"] = stars
            self.data["users"][user_id_str]["prize_claimed"] = True
            self.data["users"][user_id_str]["last_seen"] = datetime.now().isoformat()
            self.data["stats"]["stars_given"] += stars
            
            # Добавляем в список победителей
            if user_id_str not in self.data["winners"]:
                self.data["winners"].append(user_id_str)
            
            await self.save_data()
    
    async def update_settings(self, channels_text: str = None, redirect_url: str = None):
        """Обновление настроек"""
        if channels_text:
            self.data["settings"]["channels_text"] = channels_text
        if redirect_url:
            self.data["settings"]["redirect_url"] = redirect_url
        await self.save_data()
    
    async def update_user_page(self, user_id: int, page: str):
        """Обновление текущей страницы пользователя"""
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["current_page"] = page
            await self.save_data()
    
    def get_settings(self) -> Dict:
        """Получить текущие настройки"""
        return self.data["settings"]
    
    def get_stats(self) -> Dict:
        """Получить статистику"""
        return self.data["stats"]
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить данные пользователя"""
        user_id_str = str(user_id)
        return self.data["users"].get(user_id_str)
    
    async def cleanup_online_users(self):
        """Очистка неактивных пользователей"""
        cutoff_time = datetime.now() - timedelta(minutes=5)
        active_users = []
        
        for user_id_str in self.data["online_users"]:
            if user_id_str in self.data["users"]:
                last_seen = datetime.fromisoformat(self.data["users"][user_id_str]["last_seen"])
                if last_seen > cutoff_time:
                    active_users.append(user_id_str)
        
        self.data["online_users"] = active_users
        self.data["stats"]["online_count"] = len(active_users)
        await self.save_data()

storage = DataStorage()

# =============== HTML ШАБЛОНЫ ===============
HTML_TEMPLATES = {
    "index": """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Stars - Бесплатная раздача</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #0a1929 0%, #1a365d 100%);
            color: white;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .container {
            max-width: 450px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
        }
        
        /* Статус бар */
        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 15px 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(64, 156, 255, 0.2);
        }
        
        .stars-earned {
            text-align: center;
            flex: 1;
        }
        
        .stars-count {
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(45deg, #FFD700, #FFC107);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
        }
        
        .stars-label {
            font-size: 12px;
            color: #90a4ae;
            font-weight: 500;
        }
        
        /* Таймер */
        .timer-section {
            text-align: center;
            margin: 30px 0;
        }
        
        .timer-title {
            font-size: 14px;
            color: #bbdefb;
            margin-bottom: 15px;
            font-weight: 500;
            letter-spacing: 1px;
        }
        
        .timer {
            display: flex;
            justify-content: center;
            gap: 10px;
        }
        
        .time-unit {
            background: rgba(0, 0, 0, 0.3);
            padding: 15px 10px;
            border-radius: 12px;
            min-width: 70px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .time-number {
            font-size: 28px;
            font-weight: 700;
            color: #4FC3F7;
            margin-bottom: 5px;
        }
        
        .time-label {
            font-size: 11px;
            color: #90a4ae;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Главный заголовок */
        .main-header {
            text-align: center;
            margin: 30px 0;
        }
        
        .main-title {
            font-size: 32px;
            font-weight: 800;
            background: linear-gradient(45deg, #4FC3F7, #29B6F6, #0288D1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .subtitle {
            font-size: 16px;
            color: #bbdefb;
            font-weight: 400;
        }
        
        /* Карточки преимуществ */
        .features-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin: 30px 0;
        }
        
        .feature-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(64, 156, 255, 0.1);
            transition: all 0.3s ease;
        }
        
        .feature-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(64, 156, 255, 0.3);
        }
        
        .feature-icon {
            font-size: 32px;
            margin-bottom: 15px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .feature-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 8px;
            color: white;
        }
        
        .feature-desc {
            font-size: 12px;
            color: #90a4ae;
            line-height: 1.4;
        }
        
        /* Кнопка начала */
        .start-button {
            display: block;
            width: 100%;
            padding: 20px;
            background: linear-gradient(135deg, #00C853 0%, #00E676 100%);
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 30px 0;
            text-align: center;
            text-decoration: none;
            box-shadow: 0 10px 30px rgba(0, 200, 83, 0.3);
        }
        
        .start-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0, 200, 83, 0.4);
        }
        
        /* Футер */
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .footer-text {
            font-size: 12px;
            color: #90a4ae;
            margin-bottom: 20px;
        }
        
        .admin-link {
            display: inline-block;
            padding: 10px 20px;
            background: rgba(255, 215, 0, 0.1);
            border: 1px solid rgba(255, 215, 0, 0.3);
            border-radius: 15px;
            color: #FFD700;
            text-decoration: none;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        
        .admin-link:hover {
            background: rgba(255, 215, 0, 0.2);
        }
        
        /* Анимации */
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        
        .pulse {
            animation: pulse 2s infinite;
        }
        
        /* Адаптивность */
        @media (max-width: 480px) {
            .container {
                padding: 15px;
            }
            
            .features-grid {
                grid-template-columns: 1fr;
                gap: 10px;
            }
            
            .time-unit {
                min-width: 60px;
                padding: 12px 8px;
            }
            
            .time-number {
                font-size: 24px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Статус бар -->
        <div class="status-bar">
            <div class="stars-earned">
                <div class="stars-count">{stars_earned}/{stars_total}</div>
                <div class="stars-label">звёзд заработано</div>
            </div>
        </div>
        
        <!-- Таймер -->
        <div class="timer-section">
            <div class="timer-title">Осталось времени</div>
            <div class="timer">
                <div class="time-unit">
                    <div class="time-number" id="hours">06</div>
                    <div class="time-label">часов</div>
                </div>
                <div class="time-unit">
                    <div class="time-number" id="minutes">34</div>
                    <div class="time-label">мин</div>
                </div>
                <div class="time-unit">
                    <div class="time-number" id="seconds">41</div>
                    <div class="time-label">сек</div>
                </div>
            </div>
        </div>
        
        <!-- Заголовок -->
        <div class="main-header">
            <div class="main-title">Telegram Stars</div>
            <div class="subtitle">В честь наступления 2026 года</div>
        </div>
        
        <!-- Карточки преимуществ -->
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon">🎁</div>
                <div class="feature-title">Халявные Stars</div>
                <div class="feature-desc">Заработай на Telegram Stars</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">⚡</div>
                <div class="feature-title">Быстрая схема</div>
                <div class="feature-desc">Как получить старсы</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📱</div>
                <div class="feature-title">Простые задания</div>
                <div class="feature-desc">Выполните задания и заработайте</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">💰</div>
                <div class="feature-title">Мгновенный вывод</div>
                <div class="feature-desc">Получите Stars сразу</div>
            </div>
        </div>
        
        <!-- Кнопка начала -->
        <button class="start-button pulse" onclick="startRaffle()">
            Начать заработок
        </button>
        
        <!-- Футер -->
        <div class="footer">
            <div class="footer-text">
                Схема ограничена по времени • Только для пользователей Telegram
            </div>
            <a href="/admin" class="admin-link">🛡️ Админ панель</a>
        </div>
    </div>
    
    <script>
        // Таймер обратного отсчета
        function startTimer() {
            let hours = 6;
            let minutes = 34;
            let seconds = 41;
            
            const timer = setInterval(() => {
                seconds--;
                if (seconds < 0) {
                    seconds = 59;
                    minutes--;
                    if (minutes < 0) {
                        minutes = 59;
                        hours--;
                        if (hours < 0) {
                            hours = 6;
                            minutes = 34;
                            seconds = 41;
                        }
                    }
                }
                
                document.getElementById('hours').textContent = 
                    hours.toString().padStart(2, '0');
                document.getElementById('minutes').textContent = 
                    minutes.toString().padStart(2, '0');
                document.getElementById('seconds').textContent = 
                    seconds.toString().padStart(2, '0');
            }, 1000);
        }
        
        // Начать розыгрыш
        function startRaffle() {
            const userId = getUserId();
            if (userId) {
                window.location.href = `/cells?user_id=${userId}`;
            } else {
                alert('Ошибка: не удалось получить ID пользователя');
            }
        }
        
        // Получить user_id из параметров URL
        function getUserId() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('user_id') || 'demo_user';
        }
        
        // Инициализация
        document.addEventListener('DOMContentLoaded', function() {
            startTimer();
            
            // Обновляем статистику
            updateStats();
        });
        
        // Обновление статистики
        function updateStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    if (data.stars_earned && data.stars_total) {
                        document.querySelector('.stars-count').textContent = 
                            `${data.stars_earned}/${data.stars_total}`;
                    }
                });
        }
    </script>
</body>
</html>
    """,
    
    "cells": """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Выберите ячейку</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #0a1929 0%, #1a365d 100%);
            color: white;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .container {
            max-width: 450px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
        }
        
        /* Заголовок */
        .header {
            text-align: center;
            margin: 30px 0;
        }
        
        .title {
            font-size: 32px;
            font-weight: 800;
            background: linear-gradient(45deg, #FFD700, #FFC107);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
        }
        
        .subtitle {
            font-size: 16px;
            color: #bbdefb;
            margin-bottom: 10px;
            font-weight: 500;
        }
        
        .info-text {
            font-size: 14px;
            color: #90a4ae;
            line-height: 1.5;
        }
        
        /* Сетка ячеек */
        .cells-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin: 40px 0;
        }
        
        .cell {
            aspect-ratio: 1;
            background: linear-gradient(135deg, rgba(41, 182, 246, 0.2) 0%, rgba(2, 136, 209, 0.2) 100%);
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            border: 2px solid rgba(79, 195, 247, 0.3);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .cell:hover {
            transform: translateY(-5px);
            border-color: #FFD700;
            box-shadow: 0 10px 20px rgba(255, 215, 0, 0.2);
        }
        
        .cell::before {
            content: '?';
            font-size: 32px;
            font-weight: 700;
            color: rgba(255, 255, 255, 0.9);
        }
        
        .cell.opened {
            background: linear-gradient(135deg, rgba(255, 215, 0, 0.9) 0%, rgba(255, 193, 7, 0.9) 100%);
            border-color: #FFD700;
        }
        
        .cell.opened::before {
            content: '';
        }
        
        .cell-content {
            display: none;
            text-align: center;
            padding: 10px;
        }
        
        .cell.opened .cell-content {
            display: block;
        }
        
        .cell-stars {
            font-size: 20px;
            font-weight: 700;
            color: #1a237e;
            margin-bottom: 5px;
        }
        
        .cell-number {
            font-size: 10px;
            color: rgba(26, 35, 126, 0.7);
            font-weight: 500;
        }
        
        /* Кнопка */
        .claim-button {
            display: block;
            width: 100%;
            padding: 20px;
            background: linear-gradient(135deg, #00C853 0%, #00E676 100%);
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 20px 0;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0, 200, 83, 0.3);
        }
        
        .claim-button:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0, 200, 83, 0.4);
        }
        
        .claim-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Результат */
        .result-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.5s ease;
        }
        
        .result-overlay.active {
            opacity: 1;
            pointer-events: all;
        }
        
        .result-box {
            background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
            padding: 40px 30px;
            border-radius: 25px;
            text-align: center;
            max-width: 350px;
            width: 90%;
            border: 3px solid rgba(255, 215, 0, 0.5);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
            transform: scale(0.8);
            transition: transform 0.5s ease;
        }
        
        .result-overlay.active .result-box {
            transform: scale(1);
        }
        
        .result-icon {
            font-size: 60px;
            margin-bottom: 20px;
            animation: bounce 1s infinite alternate;
        }
        
        @keyframes bounce {
            from { transform: translateY(0); }
            to { transform: translateY(-15px); }
        }
        
        .result-title {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 10px;
            color: #FFD700;
        }
        
        .result-stars {
            font-size: 42px;
            font-weight: 800;
            color: white;
            margin: 20px 0;
            text-shadow: 0 0 20px rgba(255, 215, 0, 0.7);
        }
        
        .result-message {
            font-size: 14px;
            color: #bbdefb;
            margin-bottom: 25px;
            line-height: 1.5;
        }
        
        .continue-button {
            padding: 15px 30px;
            background: linear-gradient(135deg, #4FC3F7 0%, #29B6F6 100%);
            color: white;
            border: none;
            border-radius: 20px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .continue-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(41, 182, 246, 0.4);
        }
        
        /* Назад */
        .back-button {
            display: inline-block;
            padding: 12px 25px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 15px;
            color: white;
            text-decoration: none;
            font-size: 14px;
            margin-top: 20px;
            transition: all 0.3s ease;
        }
        
        .back-button:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        /* Адаптивность */
        @media (max-width: 480px) {
            .container {
                padding: 15px;
            }
            
            .cells-grid {
                gap: 10px;
            }
            
            .cell::before {
                font-size: 28px;
            }
            
            .cell-stars {
                font-size: 16px;
            }
            
            .result-box {
                padding: 30px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Заголовок -->
        <div class="header">
            <div class="title">Выберите ячейку</div>
            <div class="subtitle">Игра началась!</div>
            <div class="info-text">
                Выберите одну из 9 ячеек и получите награду!<br>
                Схема ограничена по времени • Только для пользователей Telegram
            </div>
        </div>
        
        <!-- Сетка ячеек -->
        <div class="cells-grid" id="cellsGrid">
            <!-- Ячейки будут сгенерированы JavaScript -->
        </div>
        
        <!-- Кнопка -->
        <button class="claim-button" id="claimButton" disabled>
            Забрать приз
        </button>
        
        <!-- Назад -->
        <div style="text-align: center;">
            <a href="/" class="back-button">← Вернуться назад</a>
        </div>
    </div>
    
    <!-- Оверлей результата -->
    <div class="result-overlay" id="resultOverlay">
        <div class="result-box">
            <div class="result-icon">🎉</div>
            <div class="result-title">Поздравляем!</div>
            <div class="result-stars" id="resultStars">1000 ⭐</div>
            <div class="result-message">
                Вы выиграли <span id="wonStars">1000</span> Telegram Stars!<br>
                Все ячейки теперь открыты.
            </div>
            <button class="continue-button" id="continueButton">
                Забрать приз
            </button>
        </div>
    </div>
    
    <script>
        // Призы в ячейках (всегда 1000 на первом выборе)
        const prizes = [50, 250, 250, 500, 300, 400, 350, 550, 1000];
        let shuffledPrizes = [...prizes].sort((a, b) => a - b);
        
        let selectedCell = null;
        
        // Получить user_id
        function getUserId() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('user_id');
        }
        
        // Создать ячейки
        function createCells() {
            const cellsGrid = document.getElementById('cellsGrid');
            cellsGrid.innerHTML = '';
            
            shuffledPrizes.forEach((prize, index) => {
                const cell = document.createElement('div');
                cell.className = 'cell';
                cell.dataset.index = index;
                cell.dataset.prize = prize;
                
                const cellContent = document.createElement('div');
                cellContent.className = 'cell-content';
                cellContent.innerHTML = `
                    <div class="cell-stars">${prize} ⭐</div>
                    <div class="cell-number">Ячейка ${index + 1}</div>
                `;
                
                cell.appendChild(cellContent);
                cell.addEventListener('click', () => selectCell(cell, index, prize));
                cellsGrid.appendChild(cell);
            });
        }
        
        // Выбор ячейки
        function selectCell(cell, index, prize) {
            if (selectedCell) return;
            
            selectedCell = cell;
            cell.classList.add('opened');
            
            // Показать результат через 1 секунду
            setTimeout(() => {
                // Открыть все ячейки
                document.querySelectorAll('.cell').forEach(cell => {
                    cell.classList.add('opened');
                });
                
                // Показать результат
                document.getElementById('wonStars').textContent = prize;
                document.getElementById('resultStars').textContent = prize + ' ⭐';
                document.getElementById('resultOverlay').classList.add('active');
                document.getElementById('claimButton').disabled = false;
            }, 1000);
        }
        
        // Обработка кнопки "Забрать приз"
        document.getElementById('claimButton').addEventListener('click', function() {
            if (!selectedCell) return;
            
            const userId = getUserId();
            const prize = selectedCell.dataset.prize;
            
            // Отправить данные в бота через WebApp
            if (window.Telegram && window.Telegram.WebApp) {
                window.Telegram.WebApp.sendData(JSON.stringify({
                    action: "cell_selected",
                    stars: parseInt(prize),
                    user_id: userId
                }));
                
                // Закрыть WebApp и вернуться в бота
                setTimeout(() => {
                    window.Telegram.WebApp.close();
                }, 500);
            } else {
                // Для тестирования - переход обратно в бота
                window.location.href = `https://t.me/${config.BOT_USERNAME}?start=raffle_complete`;
            }
        });
        
        // Обработка кнопки продолжения
        document.getElementById('continueButton').addEventListener('click', function() {
            document.getElementById('resultOverlay').classList.remove('active');
            document.getElementById('claimButton').click();
        });
        
        // Инициализация
        document.addEventListener('DOMContentLoaded', function() {
            createCells();
        });
    </script>
</body>
</html>
    """,
    
    "tasks": """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Выполните задания</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #0a1929 0%, #1a365d 100%);
            color: white;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .container {
            max-width: 450px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
        }
        
        /* Заголовок */
        .header {
            text-align: center;
            margin: 30px 0;
        }
        
        .title {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(45deg, #FFD700, #FFC107);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
        }
        
        /* Виджет Stars */
        .stars-widget {
            background: linear-gradient(135deg, rgba(255, 215, 0, 0.15) 0%, rgba(255, 193, 7, 0.15) 100%);
            border-radius: 25px;
            padding: 25px;
            margin-bottom: 30px;
            border: 2px solid rgba(255, 215, 0, 0.3);
            text-align: center;
        }
        
        .stars-amount {
            font-size: 36px;
            font-weight: 800;
            color: #FFD700;
            margin-bottom: 10px;
            text-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
        }
        
        .stars-text {
            font-size: 16px;
            color: white;
            font-weight: 500;
        }
        
        /* Прогресс */
        .progress-widget {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 25px;
            padding: 25px;
            margin-bottom: 30px;
            border: 1px solid rgba(79, 195, 247, 0.2);
        }
        
        .progress-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .progress-title {
            font-size: 18px;
            font-weight: 600;
            color: white;
        }
        
        .progress-count {
            font-size: 22px;
            font-weight: 700;
            color: #4CAF50;
        }
        
        .progress-bar {
            height: 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 30px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #2E7D32);
            width: 0%;
            transition: width 0.5s ease;
            border-radius: 4px;
        }
        
        /* Задания */
        .tasks-list {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .task-item {
            display: flex;
            align-items: center;
            padding: 20px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .task-item.completed {
            background: rgba(76, 175, 80, 0.15);
            border-color: rgba(76, 175, 80, 0.5);
        }
        
        .task-icon {
            font-size: 28px;
            margin-right: 20px;
            min-width: 40px;
            text-align: center;
        }
        
        .task-content {
            flex: 1;
        }
        
        .task-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 5px;
            color: white;
        }
        
        .task-description {
            font-size: 12px;
            color: #bbdefb;
            line-height: 1.4;
        }
        
        .task-action {
            margin-left: 15px;
        }
        
        .task-button {
            padding: 10px 20px;
            background: linear-gradient(135deg, #4FC3F7 0%, #29B6F6 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            white-space: nowrap;
        }
        
        .task-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(41, 182, 246, 0.4);
        }
        
        .task-button.completed {
            background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
        }
        
        .checkmark {
            color: #4CAF50;
            font-size: 20px;
            margin-left: 15px;
            display: none;
        }
        
        .task-item.completed .checkmark {
            display: block;
        }
        
        .task-item.completed .task-button {
            display: none;
        }
        
        /* Кнопка выполнено */
        .done-button {
            display: block;
            width: 100%;
            padding: 20px;
            background: linear-gradient(135deg, #00C853 0%, #00E676 100%);
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 30px 0;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0, 200, 83, 0.3);
        }
        
        .done-button:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0, 200, 83, 0.4);
        }
        
        .done-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Успешное сообщение */
        .success-message {
            background: linear-gradient(135deg, rgba(76, 175, 80, 0.15) 0%, rgba(46, 125, 50, 0.15) 100%);
            border: 2px solid rgba(76, 175, 80, 0.5);
            border-radius: 25px;
            padding: 30px;
            margin-top: 30px;
            display: none;
        }
        
        .success-message.active {
            display: block;
            animation: fadeIn 0.5s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .success-title {
            font-size: 22px;
            font-weight: 700;
            color: #4CAF50;
            margin-bottom: 15px;
            text-align: center;
        }
        
        .success-text {
            font-size: 14px;
            color: white;
            line-height: 1.5;
            margin-bottom: 25px;
            text-align: center;
        }
        
        .continue-button {
            display: block;
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #4FC3F7 0%, #29B6F6 100%);
            color: white;
            border: none;
            border-radius: 20px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .continue-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(41, 182, 246, 0.4);
        }
        
        /* Назад */
        .back-button {
            display: inline-block;
            padding: 12px 25px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 15px;
            color: white;
            text-decoration: none;
            font-size: 14px;
            margin-top: 20px;
            transition: all 0.3s ease;
        }
        
        .back-button:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        /* Адаптивность */
        @media (max-width: 480px) {
            .container {
                padding: 15px;
            }
            
            .task-item {
                padding: 15px;
            }
            
            .task-button {
                padding: 8px 15px;
                font-size: 12px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Заголовок -->
        <div class="header">
            <div class="title">Завершите, чтобы забрать 1.000⭐</div>
        </div>
        
        <!-- Виджет Stars -->
        <div class="stars-widget">
            <div class="stars-amount">1.000 ⭐</div>
            <div class="stars-text">Telegram Stars готовы к получению</div>
        </div>
        
        <!-- Прогресс -->
        <div class="progress-widget">
            <div class="progress-header">
                <div class="progress-title">Прогресс выполнения</div>
                <div class="progress-count" id="progressCount">0/2</div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            
            <!-- Задания -->
            <div class="tasks-list">
                <!-- Задание 1 -->
                <div class="task-item" id="task1">
                    <div class="task-icon">📱</div>
                    <div class="task-content">
                        <div class="task-title">Опубликовать историю</div>
                        <div class="task-description">Поделитесь новостью о раздаче в вашей истории Telegram</div>
                    </div>
                    <div class="task-action">
                        <button class="task-button" onclick="completeTask('task1')">
                            Выполнить
                        </button>
                        <div class="checkmark">✅</div>
                    </div>
                </div>
                
                <!-- Задание 2 -->
                <div class="task-item" id="task2">
                    <div class="task-icon">👥</div>
                    <div class="task-content">
                        <div class="task-title">Рассказать друзьям</div>
                        <div class="task-description">Поделитесь с друзьями в Telegram</div>
                    </div>
                    <div class="task-action">
                        <button class="task-button" onclick="completeTask('task2')">
                            Выполнить
                        </button>
                        <div class="checkmark">✅</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Кнопка выполнено -->
        <button class="done-button" id="doneButton" disabled onclick="showSuccessMessage()">
            Выполнено
        </button>
        
        <!-- Успешное сообщение -->
        <div class="success-message" id="successMessage">
            <div class="success-title">🎉 Поздравляем!</div>
            <div class="success-text">
                С радостью сообщаем вам, что ваш приз в размере 1000⭐ готов к выводу в ваш профиль. 
                Осталось лишь завершить небольшой процесс, и ваши 1000 ⭐ STARS будут автоматически зачислены.
            </div>
            <button class="continue-button" onclick="redirectToContinue()">
                Продолжить
            </button>
        </div>
        
        <!-- Назад -->
        <div style="text-align: center;">
            <a href="/" class="back-button">← Вернуться на главную</a>
        </div>
    </div>
    
    <script>
        let completedTasks = 0;
        const totalTasks = 2;
        
        // Получить user_id
        function getUserId() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('user_id');
        }
        
        // Обновить прогресс
        function updateProgress() {
            const progressCount = document.getElementById('progressCount');
            const progressFill = document.getElementById('progressFill');
            const doneButton = document.getElementById('doneButton');
            
            progressCount.textContent = `${completedTasks}/${totalTasks}`;
            progressFill.style.width = `${(completedTasks / totalTasks) * 100}%`;
            
            if (completedTasks === totalTasks) {
                doneButton.disabled = false;
            }
        }
        
        // Выполнить задание
        function completeTask(taskId) {
            const taskElement = document.getElementById(taskId);
            const shareText = encodeURIComponent("Бесплатная раздача STARS⭐, успейте, время ограничено! Раздача от бота: @StarsRaysbot");
            
            // Открыть Telegram для выполнения задания
            if (taskId === 'task1') {
                window.open(`tg://share?url=&text=${shareText}`, '_blank');
            } else {
                window.open(`tg://msg?text=${shareText}`, '_blank');
            }
            
            // Пометить задание как выполненное
            setTimeout(() => {
                taskElement.classList.add('completed');
                completedTasks++;
                updateProgress();
            }, 1000);
        }
        
        // Показать успешное сообщение
        function showSuccessMessage() {
            document.getElementById('successMessage').classList.add('active');
            document.getElementById('doneButton').style.display = 'none';
        }
        
        // Перенаправление
        function redirectToContinue() {
            fetch('/api/settings')
                .then(response => response.json())
                .then(data => {
                    window.location.href = data.redirect_url || "https://share.google/images/nN32IC20Y2cYIEIkH";
                })
                .catch(() => {
                    window.location.href = "https://share.google/images/nN32IC20Y2cYIEIkH";
                });
        }
        
        // Инициализация
        document.addEventListener('DOMContentLoaded', function() {
            updateProgress();
        });
    </script>
</body>
</html>
    """,
    
    "admin_login": """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Админ панель</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #0a1929 0%, #1a365d 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .login-form {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 25px;
            padding: 40px;
            max-width: 400px;
            width: 90%;
            border: 2px solid rgba(255, 215, 0, 0.3);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
        }
        
        .form-title {
            text-align: center;
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 30px;
            color: #FFD700;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #bbdefb;
            font-weight: 500;
        }
        
        .form-group input {
            width: 100%;
            padding: 15px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            color: white;
            font-size: 16px;
            outline: none;
        }
        
        .form-group input:focus {
            border-color: #FFD700;
        }
        
        .login-button {
            display: block;
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #4FC3F7 0%, #29B6F6 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 20px;
        }
        
        .login-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(41, 182, 246, 0.4);
        }
        
        .error-message {
            color: #f44336;
            text-align: center;
            margin-top: 15px;
            font-size: 14px;
            display: none;
        }
        
        .back-link {
            display: block;
            text-align: center;
            margin-top: 25px;
            color: #bbdefb;
            text-decoration: none;
            font-size: 14px;
            transition: color 0.3s ease;
        }
        
        .back-link:hover {
            color: #4FC3F7;
        }
        
        @media (max-width: 480px) {
            .login-form {
                padding: 30px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="login-form">
        <div class="form-title">🛡️ Вход в админ панель</div>
        <div class="form-group">
            <label>Логин:</label>
            <input type="text" id="adminLogin" placeholder="Введите логин">
        </div>
        <div class="form-group">
            <label>Пароль:</label>
            <input type="password" id="adminPassword" placeholder="Введите пароль">
        </div>
        <button class="login-button" onclick="checkLogin()">Войти</button>
        <div class="error-message" id="errorMessage">Неверный логин или пароль!</div>
        <a href="/" class="back-link">← Вернуться на главную</a>
    </div>
    
    <script>
        function checkLogin() {
            const login = document.getElementById('adminLogin').value;
            const password = document.getElementById('adminPassword').value;
            
            if (login === 'Lyrne' && password === 'sb39#$99haldB') {
                // Сохраняем в sessionStorage
                sessionStorage.setItem('admin_logged_in', 'true');
                sessionStorage.setItem('admin_username', login);
                
                // Перенаправляем на админ панель
                window.location.href = '/admin_panel';
            } else {
                document.getElementById('errorMessage').style.display = 'block';
            }
        }
        
        // Автозаполнение для удобства
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('adminLogin').value = 'Lyrne';
        });
    </script>
</body>
</html>
    """,
    
    "admin_panel": """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Админ панель</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #0a1929 0%, #1a365d 100%);
            color: white;
            min-height: 100vh;
        }
        
        .container {
            max-width: 500px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Заголовок */
        .header {
            text-align: center;
            margin: 30px 0 40px;
        }
        
        .title {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(45deg, #FFD700, #FFC107);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .subtitle {
            font-size: 16px;
            color: #bbdefb;
            font-weight: 500;
        }
        
        /* Статистика */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-bottom: 40px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .stat-number {
            font-size: 28px;
            font-weight: 700;
            color: #FFD700;
            margin-bottom: 8px;
        }
        
        .stat-label {
            font-size: 12px;
            color: #bbdefb;
            font-weight: 500;
        }
        
        /* Настройки */
        .settings-section {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 25px;
            padding: 30px;
            margin-bottom: 30px;
            border: 2px solid rgba(255, 215, 0, 0.3);
        }
        
        .section-title {
            font-size: 20px;
            font-weight: 700;
            color: #FFD700;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .input-group {
            margin-bottom: 25px;
        }
        
        .input-group label {
            display: block;
            margin-bottom: 10px;
            color: #e3f2fd;
            font-weight: 500;
        }
        
        .input-group textarea,
        .input-group input {
            width: 100%;
            padding: 15px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            color: white;
            font-size: 14px;
            font-family: inherit;
        }
        
        .input-group textarea {
            min-height: 120px;
            resize: vertical;
        }
        
        .help-text {
            font-size: 12px;
            color: #90a4ae;
            margin-top: 8px;
            font-style: italic;
        }
        
        /* Кнопки */
        .buttons-group {
            display: flex;
            gap: 15px;
            margin-top: 40px;
        }
        
        .admin-button {
            flex: 1;
            padding: 15px;
            border: none;
            border-radius: 15px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .save-button {
            background: linear-gradient(135deg, #00C853 0%, #00E676 100%);
            color: white;
        }
        
        .back-button {
            background: linear-gradient(135deg, #4FC3F7 0%, #29B6F6 100%);
            color: white;
        }
        
        .logout-button {
            background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
            color: white;
        }
        
        .admin-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
        }
        
        /* Уведомление */
        .notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: linear-gradient(135deg, #00C853 0%, #00E676 100%);
            color: white;
            padding: 15px 25px;
            border-radius: 15px;
            display: none;
            animation: slideIn 0.3s ease;
            z-index: 1000;
            max-width: 300px;
        }
        
        .notification.error {
            background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
        }
        
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @media (max-width: 480px) {
            .container {
                padding: 15px;
            }
            
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .buttons-group {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Заголовок -->
        <div class="header">
            <div class="title">🛡️ Админ панель</div>
            <div class="subtitle">Управление раздачей Stars</div>
        </div>
        
        <!-- Статистика -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number" id="totalUsers">0</div>
                <div class="stat-label">Всего пользователей</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="onlineUsers">0</div>
                <div class="stat-label">Онлайн сейчас</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="starsGiven">0</div>
                <div class="stat-label">Stars роздано</div>
            </div>
        </div>
        
        <!-- Настройки текста -->
        <div class="settings-section">
            <div class="section-title">
                <span>📝 Текст для подписки</span>
            </div>
            <div class="input-group">
                <label>Текст задания:</label>
                <textarea id="channelsText" placeholder="Введите текст задания..."></textarea>
                <div class="help-text">
                    Текст показывается пользователям после выбора ячейки
                </div>
            </div>
        </div>
        
        <!-- Настройки ссылки -->
        <div class="settings-section">
            <div class="section-title">
                <span>🔗 Ссылка для кнопки</span>
            </div>
            <div class="input-group">
                <label>URL адрес:</label>
                <input type="url" id="redirectUrl" placeholder="https://example.com">
                <div class="help-text">
                    Ссылка для кнопки "Продолжить" после выполнения заданий
                </div>
            </div>
        </div>
        
        <!-- Кнопки -->
        <div class="buttons-group">
            <button class="admin-button back-button" onclick="goBack()">
                🔙 Назад
            </button>
            <button class="admin-button save-button" onclick="saveSettings()">
                💾 Сохранить
            </button>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <button class="admin-button logout-button" onclick="logout()" style="width: 200px;">
                🔒 Выйти
            </button>
        </div>
    </div>
    
    <!-- Уведомление -->
    <div class="notification" id="notification"></div>
    
    <script>
        // Проверка авторизации
        if (!sessionStorage.getItem('admin_logged_in')) {
            window.location.href = '/admin';
        }
        
        // Загрузка данных
        function loadData() {
            // Статистика
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('totalUsers').textContent = data.total_users || 0;
                    document.getElementById('onlineUsers').textContent = data.online_count || 0;
                    document.getElementById('starsGiven').textContent = data.stars_given || 0;
                })
                .catch(error => {
                    console.error('Error loading stats:', error);
                });
            
            // Настройки
            fetch('/api/settings')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('channelsText').value = data.channels_text || '';
                    document.getElementById('redirectUrl').value = data.redirect_url || '';
                })
                .catch(error => {
                    console.error('Error loading settings:', error);
                });
        }
        
        // Сохранение настроек
        function saveSettings() {
            const channelsText = document.getElementById('channelsText').value;
            const redirectUrl = document.getElementById('redirectUrl').value;
            
            if (!channelsText.trim() || !redirectUrl.trim()) {
                showNotification('Пожалуйста, заполните все поля', 'error');
                return;
            }
            
            fetch('/api/update_settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    channels_text: channelsText,
                    redirect_url: redirectUrl
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('Настройки успешно сохранены!');
                    loadData(); // Обновляем данные
                } else {
                    showNotification('Ошибка при сохранении', 'error');
                }
            })
            .catch(error => {
                console.error('Error saving settings:', error);
                showNotification('Ошибка соединения', 'error');
            });
        }
        
        // Показать уведомление
        function showNotification(message, type = 'success') {
            const notification = document.getElementById('notification');
            notification.textContent = message;
            notification.className = 'notification ' + (type === 'error' ? 'error' : '');
            notification.style.display = 'block';
            
            setTimeout(() => {
                notification.style.display = 'none';
            }, 3000);
        }
        
        // Выйти
        function logout() {
            sessionStorage.removeItem('admin_logged_in');
            sessionStorage.removeItem('admin_username');
            window.location.href = '/admin';
        }
        
        // Назад
        function goBack() {
            window.location.href = '/';
        }
        
        // Обновлять статистику каждые 30 секунд
        setInterval(loadData, 30000);
        
        // Инициализация
        document.addEventListener('DOMContentLoaded', function() {
            loadData();
        });
    </script>
</body>
</html>
    """
}

# =============== TELEGRAM BOT ФУНКЦИИ ===============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    await storage.add_user(user.id, user.username, user.first_name)
    await storage.mark_user_online(user.id)
    
    # Проверяем аргументы
    args = context.args
    if args and args[0] == "raffle_complete":
        await show_channels_task(update, context)
        return
    
    # Приветственное сообщение с фото
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        f"🎁 Мы запускаемся и в честь этого устраиваем масштабную раздачу "
        f"призов среди новых пользователей!\n\n"
        f"👇 Чтобы забрать Telegram Stars, жми кнопку ЗАБРАТЬ ПРИЗ 🎁"
    )
    
    keyboard = [[
        InlineKeyboardButton(
            "🎁 ЗАБРАТЬ ПРИЗ",
            web_app=WebAppInfo(url=f"{config.WEBAPP_URL}?user_id={user.id}")
        )
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        photo_url = "https://i.postimg.cc/sXYjWpJX/IMG-20260129-012211-151.jpg"
        await update.message.reply_photo(
            photo=photo_url,
            caption=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка данных из WebApp"""
    if update.message and update.message.web_app_data:
        try:
            data = json.loads(update.message.web_app_data.data)
            user_id = update.effective_user.id
            
            if data.get("action") == "cell_selected":
                stars_won = data.get("stars", 1000)
                await storage.update_user_stars(user_id, stars_won)
                await show_channels_task(update, context)
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing webapp data: {e}")
            await update.message.reply_text("❌ Ошибка обработки данных. Попробуйте снова.")

async def show_channels_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать каналы для подписки"""
    settings = storage.get_settings()
    
    keyboard = [[
        InlineKeyboardButton("✅ Я подписался", callback_data="subscribed")
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = settings["channels_text"]
    
    if update.callback_query:
        await update.callback_query.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    elif update.message:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_subscribed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь подписался на каналы"""
    query = update.callback_query
    await query.answer()
    
    text = "✅ Последний этап, чтобы вывести 1000⭐, нажмите кнопку «Забрать»."
    
    keyboard = [[
        InlineKeyboardButton(
            "🎁 Забрать",
            web_app=WebAppInfo(url=f"{config.WEBAPP_URL}tasks?user_id={update.effective_user.id}")
        )
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def newsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для изменения текста каналов"""
    user = update.effective_user
    
    if user.username != config.ADMIN_USERNAME:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Использование: /newsub [новый текст]\n\n"
            "Пример:\n"
            "/newsub 😇 Новый текст для каналов..."
        )
        return
    
    new_text = ' '.join(context.args)
    await storage.update_settings(channels_text=new_text)
    
    await update.message.reply_text(
        "✅ Текст каналов успешно обновлен!",
        parse_mode=ParseMode.MARKDOWN
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра статистики"""
    user = update.effective_user
    
    if user.username != config.ADMIN_USERNAME:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    stats = storage.get_stats()
    
    text = (
        "📊 *Статистика бота*\n\n"
        f"👥 Всего пользователей: *{stats['total_users']}*\n"
        f"🌐 Сейчас онлайн: *{stats['online_count']}*\n"
        f"⭐ Stars роздано: *{stats['stars_given']:,}*\n"
        f"🎯 Всего Stars: *{stats['stars_total']:,}*\n\n"
        f"🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """Задача очистки неактивных пользователей"""
    await storage.cleanup_online_users()
    logger.info("Cleaned up inactive users")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}")

# =============== HTTP СЕРВЕР ===============
async def handle_index(request):
    """Главная страница"""
    user_id = request.query.get('user_id', '')
    stats = storage.get_stats()
    
    html = HTML_TEMPLATES["index"].format(
        stars_earned=stats["stars_given"],
        stars_total=stats["stars_total"]
    )
    
    if user_id:
        try:
            uid = int(user_id)
            await storage.mark_user_online(uid)
            await storage.update_user_page(uid, "index")
        except:
            pass
    
    return web.Response(text=html, content_type='text/html')

async def handle_cells(request):
    """Страница выбора ячеек"""
    user_id = request.query.get('user_id', '')
    
    if user_id:
        try:
            uid = int(user_id)
            await storage.mark_user_online(uid)
            await storage.update_user_page(uid, "cells")
        except:
            pass
    
    return web.Response(text=HTML_TEMPLATES["cells"], content_type='text/html')

async def handle_tasks(request):
    """Страница заданий"""
    user_id = request.query.get('user_id', '')
    
    if user_id:
        try:
            uid = int(user_id)
            await storage.mark_user_online(uid)
            await storage.update_user_page(uid, "tasks")
        except:
            pass
    
    return web.Response(text=HTML_TEMPLATES["tasks"], content_type='text/html')

async def handle_admin(request):
    """Страница входа в админ панель"""
    return web.Response(text=HTML_TEMPLATES["admin_login"], content_type='text/html')

async def handle_admin_panel(request):
    """Админ панель"""
    # Проверка авторизации через sessionStorage на клиенте
    return web.Response(text=HTML_TEMPLATES["admin_panel"], content_type='text/html')

# API эндпоинты
async def api_stats(request):
    """API для получения статистики"""
    stats = storage.get_stats()
    return web.json_response({
        "stars_earned": stats["stars_given"],
        "stars_total": stats["stars_total"],
        "total_users": stats["total_users"],
        "online_count": stats["online_count"],
        "stars_given": stats["stars_given"]
    })

async def api_settings(request):
    """API для получения настроек"""
    settings = storage.get_settings()
    return web.json_response({
        "channels_text": settings["channels_text"],
        "redirect_url": settings["redirect_url"]
    })

async def api_update_settings(request):
    """API для обновления настроек"""
    try:
        data = await request.json()
        await storage.update_settings(
            channels_text=data.get('channels_text'),
            redirect_url=data.get('redirect_url')
        )
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})

async def start_http_server():
    """Запуск HTTP сервера"""
    app = web.Application()
    
    # Статические страницы
    app.router.add_get('/', handle_index)
    app.router.add_get('/index', handle_index)
    app.router.add_get('/cells', handle_cells)
    app.router.add_get('/tasks', handle_tasks)
    app.router.add_get('/admin', handle_admin)
    app.router.add_get('/admin_panel', handle_admin_panel)
    
    # API эндпоинты
    app.router.add_get('/api/stats', api_stats)
    app.router.add_get('/api/settings', api_settings)
    app.router.add_post('/api/update_settings', api_update_settings)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', config.HTTP_PORT)
    await site.start()
    
    print(f"HTTP сервер запущен на порту {config.HTTP_PORT}")
    return runner

# =============== ОСНОВНОЙ ЗАПУСК ===============
async def main():
    """Основная функция запуска"""
    # Запускаем HTTP сервер
    http_runner = None
    if config.ENABLE_HTTP:
        http_runner = await start_http_server()
    
    # Создаем Telegram бота
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newsub", newsub_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(handle_subscribed, pattern="^subscribed$"))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    
    application.add_error_handler(error_handler)
    
    # Запускаем задачу очистки
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(cleanup_job, interval=300, first=10)
    
    # Настройка webhook для bothost
    if config.WEBHOOK_URL:
        await application.bot.set_webhook(f"{config.WEBHOOK_URL}{config.BOT_TOKEN}")
        await application.initialize()
        await application.start()
        print(f"Бот запущен в режиме webhook: {config.WEBHOOK_URL}")
    else:
        # Режим polling для разработки
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        print("Бот запущен в режиме polling")
    
    # Бесконечный цикл
    try:
        while True:
            await asyncio.sleep(3600)  # Спим 1 час
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
    finally:
        # Останавливаем бота
        await application.stop()
        
        # Останавливаем HTTP сервер
        if http_runner:
            await http_runner.cleanup()
        
        print("Все сервисы остановлены")

if __name__ == "__main__":
    # Создаем директории если их нет
    Path("database").mkdir(exist_ok=True)
    
    # Запускаем асинхронно
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма завершена")
