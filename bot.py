import os
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Dict

from flask import Flask, request, render_template_string, jsonify, redirect
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import threading
import asyncio

# =============== НАСТРОЙКИ ===============
BOT_TOKEN = "8562130677:AAFS3N3ls-POoDmq9uTC1D7XU7cijFChEg8"
BOT_USERNAME = "StarsRaysbot"
ADMIN_USERNAME = "Lyrne"
ADMIN_PASSWORD = "sb39#$99haldB"
PORT = int(os.environ.get('PORT', 5000))

# URL приветственной картинки
WELCOME_IMAGE_URL = "https://i.postimg.cc/sXYjWpJX/IMG-20260129-012211-151.jpg"

# =============== ХРАНИЛИЩЕ ДАННЫХ ===============
class DataStorage:
    def __init__(self):
        self.data_file = Path("data.json")
        self.data = self.load_data()
    
    def load_data(self):
        if self.data_file.exists():
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "users": {},
            "stats": {
                "total_users": 1250,
                "online_count": random.randint(35, 50),
                "stars_given": random.randint(25000, 35000),
                "stars_total": 50000
            },
            "settings": {
                "channels_text": "😇 Чтобы забрать приз, выполни простое задание.\n\nПодпишись на эти каналы спонсоров 👇️\n@durov\n@telegram",
                "redirect_url": "https://share.google/images/nN32IC20Y2cYIEIkH",
                "bot_return_url": f"https://t.me/{BOT_USERNAME}?start=return_back"  # НОВОЕ: URL для возврата в бота
            }
        }
    
    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def add_user(self, user_id: int, username: str, first_name: str):
        user_id_str = str(user_id)
        if user_id_str not in self.data["users"]:
            self.data["users"][user_id_str] = {
                "username": username,
                "first_name": first_name,
                "joined": datetime.now().isoformat(),
                "stars_won": 0,
                "tasks_completed": False,
                "cell_selected": False
            }
            self.data["stats"]["total_users"] = len(self.data["users"])
            self.data["stats"]["online_count"] = random.randint(35, 50)
            self.save_data()
    
    def update_user_stars(self, user_id: int, stars: int):
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["stars_won"] = stars
            self.data["users"][user_id_str]["cell_selected"] = True
            self.data["stats"]["stars_given"] = min(50000, self.data["stats"]["stars_given"] + stars)
            self.save_data()
    
    def mark_tasks_completed(self, user_id: int):
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["tasks_completed"] = True
            self.save_data()
    
    def update_online_count(self):
        self.data["stats"]["online_count"] = random.randint(35, 50)
        self.save_data()
    
    def update_settings(self, channels_text=None, redirect_url=None, bot_return_url=None):
        if channels_text:
            self.data["settings"]["channels_text"] = channels_text
        if redirect_url:
            self.data["settings"]["redirect_url"] = redirect_url
        if bot_return_url:
            self.data["settings"]["bot_return_url"] = bot_return_url
        self.save_data()
    
    def get_settings(self):
        return self.data["settings"]
    
    def get_stats(self):
        self.update_online_count()
        return self.data["stats"]

storage = DataStorage()

# =============== FLASK APP ===============
app = Flask(__name__)

# HTML шаблоны с красивым дизайном
HTML_TEMPLATES = {
    "index": """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Stars - Бесплатная раздача</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Montserrat', sans-serif;
            background: linear-gradient(135deg, #0a0e29 0%, #101a40 100%); 
            color: white; 
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Анимированный фон с звездами */
        .stars-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }
        
        .star {
            position: absolute;
            background: rgba(255, 255, 255, 0.8);
            border-radius: 50%;
            animation: twinkle 3s infinite;
        }
        
        @keyframes twinkle {
            0%, 100% { opacity: 0.3; transform: scale(1); }
            50% { opacity: 1; transform: scale(1.2); }
        }
        
        .container { 
            max-width: 450px; 
            margin: 0 auto; 
            padding: 20px;
            position: relative;
            z-index: 1;
        }
        
        /* Онлайн статус */
        .online-status {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(64, 156, 255, 0.2);
            border-radius: 15px;
            padding: 15px 20px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .online-dot {
            width: 10px;
            height: 10px;
            background: #4CAF50;
            border-radius: 50%;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
            100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
        }
        
        /* Виджет статистики */
        .stats-widget {
            background: linear-gradient(135deg, rgba(41, 128, 185, 0.9), rgba(41, 128, 185, 0.7));
            backdrop-filter: blur(10px);
            border: 2px solid rgba(255, 215, 0, 0.3);
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 25px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        }
        
        .stats-widget::before {
            content: '⭐';
            position: absolute;
            top: 15px;
            left: 20px;
            font-size: 24px;
            color: rgba(255, 215, 0, 0.8);
        }
        
        .stars-count {
            text-align: center;
            margin-bottom: 25px;
        }
        
        .stars-number {
            font-size: 42px;
            font-weight: 700;
            background: linear-gradient(45deg, #FFD700, #FFA500);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 2px 10px rgba(255, 215, 0, 0.3);
        }
        
        .stars-label {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.8);
            margin-top: 5px;
        }
        
        /* Таймер */
        .timer-container {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
        }
        
        .timer-title {
            font-size: 16px;
            color: rgba(255, 255, 255, 0.9);
            margin-bottom: 15px;
        }
        
        .timer {
            display: flex;
            justify-content: center;
            gap: 15px;
        }
        
        .time-box {
            background: rgba(0, 0, 0, 0.3);
            border: 2px solid rgba(79, 195, 247, 0.3);
            border-radius: 12px;
            padding: 15px;
            min-width: 80px;
        }
        
        .time-value {
            font-size: 32px;
            font-weight: 700;
            color: #4FC3F7;
            text-shadow: 0 0 10px rgba(79, 195, 247, 0.5);
        }
        
        .time-label {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.7);
            margin-top: 5px;
        }
        
        /* Заголовок с звездами */
        .main-title {
            text-align: center;
            margin: 30px 0;
            position: relative;
        }
        
        .title-text {
            font-size: 36px;
            font-weight: 700;
            background: linear-gradient(45deg, #4FC3F7, #0288D1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            position: relative;
            display: inline-block;
        }
        
        .title-text::after {
            content: '⭐ ⭐ ⭐';
            position: absolute;
            top: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 20px;
            opacity: 0.7;
        }
        
        /* Виджет функций */
        .features-widget {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(64, 156, 255, 0.2);
            border-radius: 20px;
            padding: 25px;
            margin: 30px 0;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .feature-item {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 15px;
            transition: transform 0.3s;
        }
        
        .feature-item:hover {
            transform: translateX(5px);
            background: rgba(255, 255, 255, 0.05);
        }
        
        .feature-item:last-child {
            margin-bottom: 0;
        }
        
        .feature-icon {
            font-size: 28px;
            margin-right: 20px;
            width: 50px;
            height: 50px;
            background: rgba(79, 195, 247, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .feature-content h3 {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 5px;
            color: #FFFFFF;
        }
        
        .feature-content p {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        /* Кнопка */
        .start-button {
            display: block;
            width: 100%;
            padding: 22px;
            background: linear-gradient(135deg, #00C853, #00E676);
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 20px;
            font-weight: 700;
            cursor: pointer;
            margin: 40px 0 30px;
            text-align: center;
            text-decoration: none;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(0, 200, 83, 0.3);
            position: relative;
            overflow: hidden;
        }
        
        .start-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0, 200, 83, 0.4);
        }
        
        .start-button:active {
            transform: translateY(1px);
        }
        
        .start-button::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 5px;
            height: 5px;
            background: rgba(255, 255, 255, 0.5);
            opacity: 0;
            border-radius: 100%;
            transform: scale(1, 1) translate(-50%);
            transform-origin: 50% 50%;
        }
        
        .start-button:focus:not(:active)::after {
            animation: ripple 1s ease-out;
        }
        
        @keyframes ripple {
            0% { transform: scale(0, 0); opacity: 0.5; }
            100% { transform: scale(20, 20); opacity: 0; }
        }
        
        /* Футер */
        .footer {
            text-align: center;
            margin-top: 40px;
            color: rgba(255, 255, 255, 0.5);
            font-size: 12px;
        }
        
        .admin-link {
            display: inline-block;
            padding: 12px 25px;
            background: rgba(255, 215, 0, 0.1);
            border: 1px solid rgba(255, 215, 0, 0.3);
            border-radius: 15px;
            color: #FFD700;
            text-decoration: none;
            margin-top: 20px;
            transition: all 0.3s;
        }
        
        .admin-link:hover {
            background: rgba(255, 215, 0, 0.2);
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <!-- Анимированные звезды на фоне -->
    <div class="stars-bg" id="starsBg"></div>
    
    <div class="container">
        <!-- Онлайн статус -->
        <div class="online-status">
            <div style="display: flex; align-items: center;">
                <div class="online-dot"></div>
                <span style="font-weight: 600;">Онлайн</span>
            </div>
            <div style="font-size: 18px; font-weight: 700; color: #4FC3F7;">
                {{ stats.online_count }}
            </div>
        </div>
        
        <!-- Виджет статистики -->
        <div class="stats-widget">
            <div class="stars-count">
                <div class="stars-number">{{ "{:,}".format(stats.stars_given) }}</div>
                <div class="stars-label">Звезд разыграно рандомно от 250 до 35.000</div>
            </div>
            
            <div class="timer-container">
                <div class="timer-title">До конца раздачи</div>
                <div class="timer">
                    <div class="time-box">
                        <div class="time-value" id="hours">06</div>
                        <div class="time-label">часов</div>
                    </div>
                    <div class="time-box">
                        <div class="time-value" id="minutes">59</div>
                        <div class="time-label">минут</div>
                    </div>
                    <div class="time-box">
                        <div class="time-value" id="seconds">59</div>
                        <div class="time-label">секунд</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Заголовок -->
        <div class="main-title">
            <div class="title-text">Telegram Stars</div>
        </div>
        
        <!-- Виджет функций -->
        <div class="features-widget">
            <div class="feature-item">
                <div class="feature-icon">🎁</div>
                <div class="feature-content">
                    <h3>Бесплатные Stars</h3>
                    <p>Получите Telegram Stars бесплатно</p>
                </div>
            </div>
            
            <div class="feature-item">
                <div class="feature-icon">⚡</div>
                <div class="feature-content">
                    <h3>Мгновенный вывод</h3>
                    <p>Быстрое получение ваших Stars</p>
                </div>
            </div>
            
            <div class="feature-item">
                <div class="feature-icon">▶️</div>
                <div class="feature-content">
                    <h3>Простые задания</h3>
                    <p>Легкие шаги для получения приза</p>
                </div>
            </div>
        </div>
        
        <!-- Кнопка -->
        <button class="start-button" onclick="startRaffle()">Начать раздачу</button>
        
        <!-- Футер -->
        <div class="footer">
            <div>Схема ограничена по времени • Только для пользователей Telegram</div>
            <a href="/admin" class="admin-link">🛡️ Админ панель</a>
        </div>
    </div>
    
    <script>
        // Создаем звезды на фоне
        function createStars() {
            const starsBg = document.getElementById('starsBg');
            const starCount = 50;
            
            for (let i = 0; i < starCount; i++) {
                const star = document.createElement('div');
                star.className = 'star';
                
                const size = Math.random() * 3 + 1;
                star.style.width = `${size}px`;
                star.style.height = `${size}px`;
                star.style.left = `${Math.random() * 100}%`;
                star.style.top = `${Math.random() * 100}%`;
                star.style.animationDelay = `${Math.random() * 3}s`;
                
                starsBg.appendChild(star);
            }
        }
        
        // Таймер обратного отсчета
        function startTimer() {
            let hours = 6, minutes = 59, seconds = 59;
            
            function updateTimer() {
                seconds--;
                if (seconds < 0) {
                    seconds = 59;
                    minutes--;
                }
                if (minutes < 0) {
                    minutes = 59;
                    hours--;
                }
                if (hours < 0) {
                    hours = 6;
                    minutes = 59;
                    seconds = 59;
                }
                
                document.getElementById('hours').textContent = hours.toString().padStart(2, '0');
                document.getElementById('minutes').textContent = minutes.toString().padStart(2, '0');
                document.getElementById('seconds').textContent = seconds.toString().padStart(2, '0');
            }
            
            updateTimer();
            setInterval(updateTimer, 1000);
        }
        
        // Начать раздачу
        function startRaffle() {
            const userId = new URLSearchParams(window.location.search).get('user_id') || 'demo';
            window.location.href = '/cells?user_id=' + userId;
        }
        
        // Инициализация
        document.addEventListener('DOMContentLoaded', () => {
            createStars();
            startTimer();
        });
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
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Montserrat', sans-serif;
            background: linear-gradient(135deg, #0a0e29 0%, #101a40 100%); 
            color: white; 
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .stars-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }
        
        .star {
            position: absolute;
            background: rgba(255, 255, 255, 0.8);
            border-radius: 50%;
            animation: twinkle 3s infinite;
        }
        
        @keyframes twinkle {
            0%, 100% { opacity: 0.3; transform: scale(1); }
            50% { opacity: 1; transform: scale(1.2); }
        }
        
        .container { 
            max-width: 450px; 
            margin: 0 auto; 
            padding: 20px;
            position: relative;
            z-index: 1;
        }
        
        .header { 
            text-align: center; 
            margin: 40px 0;
            position: relative;
        }
        
        .title {
            font-size: 42px;
            font-weight: 700;
            background: linear-gradient(45deg, #FFD700, #FFA500);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
            text-shadow: 0 2px 10px rgba(255, 215, 0, 0.3);
            position: relative;
            display: inline-block;
        }
        
        .title::before {
            content: '⭐';
            position: absolute;
            top: -15px;
            left: -25px;
            font-size: 24px;
        }
        
        .title::after {
            content: '⭐';
            position: absolute;
            top: -15px;
            right: -25px;
            font-size: 24px;
        }
        
        .subtitle {
            font-size: 18px;
            color: #4FC3F7;
            margin-bottom: 10px;
            font-weight: 600;
        }
        
        .info-text {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.7);
            line-height: 1.6;
            max-width: 350px;
            margin: 0 auto;
        }
        
        /* Сетка ячеек */
        .cells-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 50px 0;
        }
        
        .cell {
            aspect-ratio: 1;
            background: linear-gradient(135deg, rgba(41, 128, 185, 0.8), rgba(41, 128, 185, 0.6));
            backdrop-filter: blur(10px);
            border: 2px solid rgba(79, 195, 247, 0.4);
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            position: relative;
            overflow: hidden;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        
        .cell:hover {
            transform: translateY(-5px) scale(1.05);
            border-color: #FFD700;
            box-shadow: 0 15px 40px rgba(255, 215, 0, 0.3);
        }
        
        .cell::before {
            content: '?';
            font-size: 42px;
            font-weight: 700;
            color: rgba(255, 255, 255, 0.9);
            transition: all 0.3s;
        }
        
        .cell.opened {
            background: linear-gradient(135deg, rgba(255, 215, 0, 0.9), rgba(255, 165, 0, 0.8));
            border-color: rgba(255, 215, 0, 0.8);
            transform: scale(1);
        }
        
        .cell.opened::before {
            content: '';
            opacity: 0;
        }
        
        .cell-content {
            display: none;
            text-align: center;
            animation: fadeIn 0.5s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.8); }
            to { opacity: 1; transform: scale(1); }
        }
        
        .cell.opened .cell-content {
            display: block;
        }
        
        .cell-stars {
            font-size: 24px;
            font-weight: 700;
            color: #1a237e;
            text-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        
        /* Кнопка */
        .claim-button {
            display: block;
            width: 100%;
            padding: 22px;
            background: linear-gradient(135deg, #00C853, #00E676);
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 20px;
            font-weight: 700;
            cursor: pointer;
            margin: 40px 0 30px;
            text-align: center;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(0, 200, 83, 0.3);
            opacity: 1;
        }
        
        .claim-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
        }
        
        .claim-button:not(:disabled):hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0, 200, 83, 0.4);
        }
        
        .back-button {
            display: inline-block;
            padding: 15px 30px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 15px;
            color: white;
            text-decoration: none;
            margin-top: 20px;
            transition: all 0.3s;
            text-align: center;
        }
        
        .back-button:hover {
            background: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
        }
        
        /* Оверлей с результатом */
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
            display: none;
        }
        
        .result-box {
            background: linear-gradient(135deg, rgba(26, 35, 126, 0.95), rgba(40, 53, 147, 0.95));
            backdrop-filter: blur(20px);
            padding: 50px 40px;
            border-radius: 30px;
            text-align: center;
            max-width: 400px;
            width: 90%;
            border: 3px solid rgba(255, 215, 0, 0.5);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
            animation: popIn 0.5s;
        }
        
        @keyframes popIn {
            0% { transform: scale(0.8); opacity: 0; }
            100% { transform: scale(1); opacity: 1; }
        }
        
        .result-icon {
            font-size: 80px;
            margin-bottom: 30px;
            animation: bounce 1s infinite alternate;
        }
        
        @keyframes bounce {
            from { transform: translateY(0); }
            to { transform: translateY(-20px); }
        }
        
        .result-title {
            font-size: 32px;
            font-weight: 700;
            color: #FFD700;
            margin-bottom: 20px;
            text-shadow: 0 2px 10px rgba(255, 215, 0, 0.3);
        }
        
        .result-stars {
            font-size: 60px;
            font-weight: 700;
            color: white;
            margin: 30px 0;
            text-shadow: 0 2px 20px rgba(255, 215, 0, 0.5);
        }
        
        .result-message {
            font-size: 16px;
            color: rgba(255, 255, 255, 0.9);
            line-height: 1.6;
            margin-bottom: 35px;
        }
        
        .continue-button {
            padding: 18px 40px;
            background: linear-gradient(135deg, #4FC3F7, #0288D1);
            color: white;
            border: none;
            border-radius: 20px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(79, 195, 247, 0.3);
        }
        
        .continue-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(79, 195, 247, 0.4);
        }
        
        .center {
            text-align: center;
        }
    </style>
</head>
<body>
    <!-- Анимированные звезды на фоне -->
    <div class="stars-bg" id="starsBg"></div>
    
    <div class="container">
        <div class="header">
            <div class="title">Выберите 1 ячейку</div>
            <div class="subtitle">Удача улыбается вам!</div>
            <div class="info-text">Нажмите на любую из 9 ячеек и получите награду в Telegram Stars. Ваш приз уже ждет вас!</div>
        </div>
        
        <div class="cells-grid" id="cellsGrid"></div>
        
        <button class="claim-button" id="claimButton" disabled>Забрать приз</button>
        
        <div class="center">
            <a href="/" class="back-button">← Вернуться назад</a>
        </div>
    </div>
    
    <div class="result-overlay" id="resultOverlay">
        <div class="result-box">
            <div class="result-icon">🎉</div>
            <div class="result-title">Поздравляем!</div>
            <div class="result-stars" id="resultStars">1000 ⭐</div>
            <div class="result-message">Вы выиграли <span id="wonStars">1000</span> Telegram Stars!<br>Все ячейки теперь открыты и вы можете увидеть какие призы были в каждой из них.</div>
            <button class="continue-button" id="continueButton">Забрать приз</button>
        </div>
    </div>
    
    <script>
        // Призы в ячейках
        const prizes = [50, 250, 250, 500, 300, 400, 350, 550, 1000];
        let shuffledPrizes = [...prizes];
        let selectedCell = null;
        
        // Создаем звезды на фоне
        function createStars() {
            const starsBg = document.getElementById('starsBg');
            const starCount = 60;
            
            for (let i = 0; i < starCount; i++) {
                const star = document.createElement('div');
                star.className = 'star';
                
                const size = Math.random() * 4 + 1;
                star.style.width = `${size}px`;
                star.style.height = `${size}px`;
                star.style.left = `${Math.random() * 100}%`;
                star.style.top = `${Math.random() * 100}%`;
                star.style.animationDelay = `${Math.random() * 3}s`;
                
                starsBg.appendChild(star);
            }
        }
        
        // Создаем сетку ячеек
        function createCells() {
            const grid = document.getElementById('cellsGrid');
            grid.innerHTML = '';
            
            // Перемешиваем призы
            shuffledPrizes = shuffledPrizes.sort(() => Math.random() - 0.5);
            
            shuffledPrizes.forEach((prize, index) => {
                const cell = document.createElement('div');
                cell.className = 'cell';
                cell.dataset.prize = prize;
                cell.innerHTML = `
                    <div class="cell-content">
                        <div class="cell-stars">${prize} ⭐</div>
                    </div>
                `;
                
                cell.onclick = () => selectCell(cell, prize);
                grid.appendChild(cell);
            });
        }
        
        // Выбор ячейки
        function selectCell(cell, prize) {
            if (selectedCell) return;
            
            selectedCell = cell;
            cell.classList.add('opened');
            
            // Показываем результат через 1 секунду
            setTimeout(() => {
                // Открываем все ячейки
                document.querySelectorAll('.cell').forEach(c => {
                    c.classList.add('opened');
                });
                
                // Показываем оверлей с результатом
                document.getElementById('wonStars').textContent = prize;
                document.getElementById('resultStars').textContent = prize + ' ⭐';
                document.getElementById('resultOverlay').style.display = 'flex';
                
                // Активируем кнопку
                document.getElementById('claimButton').disabled = false;
            }, 1000);
        }
        
        // Отправка данных в Telegram
        document.getElementById('claimButton').onclick = async function() {
            if (!selectedCell) return;
            
            const prize = selectedCell.dataset.prize;
            const userId = new URLSearchParams(window.location.search).get('user_id');
            
            if (window.Telegram && window.Telegram.WebApp) {
                // Отправляем данные в бота
                Telegram.WebApp.sendData(JSON.stringify({
                    action: "cell_selected",
                    stars: parseInt(prize),
                    user_id: userId
                }));
                
                // Получаем URL для возврата из настроек
                try {
                    const response = await fetch('/api/settings');
                    const settings = await response.json();
                    
                    // Перенаправляем на URL возврата в бота
                    setTimeout(() => {
                        window.location.href = settings.bot_return_url;
                    }, 300);
                } catch (error) {
                    // Если не удалось получить настройки, используем стандартный URL
                    setTimeout(() => {
                        window.location.href = 'https://t.me/StarsRaysbot?start=return_back';
                    }, 300);
                }
            } else {
                // Для тестирования в браузере
                try {
                    const response = await fetch('/api/settings');
                    const settings = await response.json();
                    alert(`Вы выиграли ${prize} Stars! Вы будете перенаправлены в бота.`);
                    window.location.href = settings.bot_return_url;
                } catch (error) {
                    alert(`Вы выиграли ${prize} Stars! В реальном боте вы будете перенаправлены.`);
                }
            }
        };
        
        // Обработка кнопки в оверлее
        document.getElementById('continueButton').onclick = function() {
            document.getElementById('resultOverlay').style.display = 'none';
            document.getElementById('claimButton').click();
        };
        
        // Инициализация
        document.addEventListener('DOMContentLoaded', () => {
            createStars();
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
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Montserrat', sans-serif;
            background: linear-gradient(135deg, #0a0e29 0%, #101a40 100%); 
            color: white; 
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .stars-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }
        
        .star {
            position: absolute;
            background: rgba(255, 255, 255, 0.8);
            border-radius: 50%;
            animation: twinkle 3s infinite;
        }
        
        @keyframes twinkle {
            0%, 100% { opacity: 0.3; transform: scale(1); }
            50% { opacity: 1; transform: scale(1.2); }
        }
        
        .container { 
            max-width: 450px; 
            margin: 0 auto; 
            padding: 20px;
            position: relative;
            z-index: 1;
        }
        
        .header { 
            text-align: center; 
            margin: 40px 0 30px;
        }
        
        .title {
            font-size: 36px;
            font-weight: 700;
            background: linear-gradient(45deg, #FFD700, #FFA500);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
            text-shadow: 0 2px 10px rgba(255, 215, 0, 0.3);
        }
        
        /* Виджет с призом */
        .prize-widget {
            background: linear-gradient(135deg, rgba(255, 215, 0, 0.15), rgba(255, 165, 0, 0.1));
            backdrop-filter: blur(10px);
            border: 2px solid rgba(255, 215, 0, 0.3);
            border-radius: 25px;
            padding: 35px 30px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 15px 40px rgba(255, 215, 0, 0.1);
        }
        
        .prize-amount {
            font-size: 48px;
            font-weight: 700;
            background: linear-gradient(45deg, #FFD700, #FFA500);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
            text-shadow: 0 2px 15px rgba(255, 215, 0, 0.3);
        }
        
        .prize-text {
            font-size: 18px;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 500;
        }
        
        /* Виджет прогресса */
        .progress-widget {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(79, 195, 247, 0.2);
            border-radius: 25px;
            padding: 35px 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        
        .progress-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }
        
        .progress-title {
            font-size: 22px;
            font-weight: 600;
            color: #FFFFFF;
        }
        
        .progress-count {
            font-size: 28px;
            font-weight: 700;
            color: #4CAF50;
        }
        
        .progress-bar {
            height: 12px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            margin-bottom: 40px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #2E7D32);
            width: 0%;
            border-radius: 6px;
            transition: width 0.5s ease;
        }
        
        /* Список заданий */
        .tasks-list {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .task-item {
            display: flex;
            align-items: center;
            padding: 25px;
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            transition: all 0.3s;
        }
        
        .task-item:hover {
            background: rgba(255, 255, 255, 0.12);
            transform: translateY(-2px);
        }
        
        .task-item.completed {
            background: rgba(76, 175, 80, 0.15);
            border-color: rgba(76, 175, 80, 0.5);
        }
        
        .task-icon {
            font-size: 32px;
            margin-right: 25px;
            width: 60px;
            height: 60px;
            background: rgba(79, 195, 247, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .task-content {
            flex: 1;
        }
        
        .task-title {
            font-size: 18px;
            font-weight: 600;
            color: #FFFFFF;
            margin-bottom: 8px;
        }
        
        .task-description {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.7);
            line-height: 1.5;
        }
        
        .task-button {
            padding: 12px 24px;
            background: linear-gradient(135deg, #4FC3F7, #0288D1);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 5px 20px rgba(79, 195, 247, 0.3);
        }
        
        .task-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(79, 195, 247, 0.4);
        }
        
        .checkmark {
            color: #4CAF50;
            font-size: 24px;
            margin-left: 20px;
            opacity: 0;
            transform: scale(0);
            transition: all 0.3s;
        }
        
        .task-item.completed .checkmark {
            opacity: 1;
            transform: scale(1);
        }
        
        .task-item.completed .task-button {
            display: none;
        }
        
        /* Кнопка выполнения */
        .done-button {
            display: block;
            width: 100%;
            padding: 25px;
            background: linear-gradient(135deg, #00C853, #00E676);
            color: white;
            border: none;
            border-radius: 25px;
            font-size: 22px;
            font-weight: 700;
            cursor: pointer;
            margin: 40px 0 30px;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(0, 200, 83, 0.3);
        }
        
        .done-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
        }
        
        .done-button:not(:disabled):hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0, 200, 83, 0.4);
        }
        
        /* Сообщение об успехе */
        .success-message {
            background: linear-gradient(135deg, rgba(76, 175, 80, 0.15), rgba(46, 125, 50, 0.1));
            backdrop-filter: blur(10px);
            border: 2px solid rgba(76, 175, 80, 0.5);
            border-radius: 25px;
            padding: 40px 35px;
            margin-top: 30px;
            display: none;
            animation: slideUp 0.5s;
        }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .success-title {
            font-size: 28px;
            font-weight: 700;
            color: #4CAF50;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .success-text {
            font-size: 16px;
            color: rgba(255, 255, 255, 0.9);
            line-height: 1.6;
            margin-bottom: 30px;
            text-align: center;
        }
        
        .continue-button {
            display: block;
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, #4FC3F7, #0288D1);
            color: white;
            border: none;
            border-radius: 20px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(79, 195, 247, 0.3);
        }
        
        .continue-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 40px rgba(79, 195, 247, 0.4);
        }
        
        .back-button {
            display: inline-block;
            padding: 15px 30px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 15px;
            color: white;
            text-decoration: none;
            margin-top: 20px;
            transition: all 0.3s;
        }
        
        .back-button:hover {
            background: rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
        }
        
        .center {
            text-align: center;
        }
    </style>
</head>
<body>
    <!-- Анимированные звезды на фоне -->
    <div class="stars-bg" id="starsBg"></div>
    
    <div class="container">
        <div class="header">
            <div class="title">Завершите, чтобы забрать 1.000⭐</div>
        </div>
        
        <div class="prize-widget">
            <div class="prize-amount">1.000 ⭐</div>
            <div class="prize-text">Telegram Stars готовы к получению</div>
        </div>
        
        <div class="progress-widget">
            <div class="progress-header">
                <div class="progress-title">Прогресс выполнения</div>
                <div class="progress-count" id="progressCount">0/2</div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            
            <div class="tasks-list">
                <div class="task-item" id="task1">
                    <div class="task-icon">📱</div>
                    <div class="task-content">
                        <div class="task-title">Опубликовать историю</div>
                        <div class="task-description">Поделитесь новостью о раздаче в вашей истории Telegram</div>
                    </div>
                    <button class="task-button" onclick="completeTask('task1')">Выполнить</button>
                    <div class="checkmark">✅</div>
                </div>
                
                <div class="task-item" id="task2">
                    <div class="task-icon">👥</div>
                    <div class="task-content">
                        <div class="task-title">Рассказать друзьям</div>
                        <div class="task-description">Поделитесь с друзьями в Telegram</div>
                    </div>
                    <button class="task-button" onclick="completeTask('task2')">Выполнить</button>
                    <div class="checkmark">✅</div>
                </div>
            </div>
        </div>
        
        <button class="done-button" id="doneButton" disabled onclick="showSuccessMessage()">Выполнено</button>
        
        <div class="success-message" id="successMessage">
            <div class="success-title">🎉 Поздравляем!</div>
            <div class="success-text">
                С радостью сообщаем вам, что ваш приз в размере 1000⭐ готов к выводу в ваш профиль. 
                Осталось лишь завершить небольшой процесс, и ваши 1000 ⭐ STARS будут автоматически зачислены.
            </div>
            <button class="continue-button" onclick="redirectToContinue()">Продолжить</button>
        </div>
        
        <div class="center">
            <a href="/" class="back-button">← Вернуться на главную</a>
        </div>
    </div>
    
    <script>
        let completedTasks = 0;
        
        // Создаем звезды на фоне
        function createStars() {
            const starsBg = document.getElementById('starsBg');
            const starCount = 50;
            
            for (let i = 0; i < starCount; i++) {
                const star = document.createElement('div');
                star.className = 'star';
                
                const size = Math.random() * 3 + 1;
                star.style.width = `${size}px`;
                star.style.height = `${size}px`;
                star.style.left = `${Math.random() * 100}%`;
                star.style.top = `${Math.random() * 100}%`;
                star.style.animationDelay = `${Math.random() * 3}s`;
                
                starsBg.appendChild(star);
            }
        }
        
        // Обновляем прогресс
        function updateProgress() {
            document.getElementById('progressCount').textContent = completedTasks + '/2';
            document.getElementById('progressFill').style.width = (completedTasks * 50) + '%';
            document.getElementById('doneButton').disabled = completedTasks < 2;
        }
        
        // Выполнение задания
        function completeTask(taskId) {
            const taskElement = document.getElementById(taskId);
            const shareText = encodeURIComponent("Бесплатная раздача STARS⭐, успейте, время ограничено! Раздача от бота: @StarsRaysbot");
            
            if (taskId === 'task1') {
                // Открываем публикацию истории
                window.open('tg://share?url=&text=' + shareText, '_blank');
            } else {
                // Открываем пересылку друзьям
                window.open('tg://msg?text=' + shareText, '_blank');
            }
            
            // Через 1 секунду отмечаем задание выполненным
            setTimeout(() => {
                taskElement.classList.add('completed');
                completedTasks++;
                updateProgress();
                
                // Сохраняем в localStorage
                localStorage.setItem(taskId, 'completed');
            }, 1000);
        }
        
        // Проверяем выполненные задания
        function checkCompletedTasks() {
            const task1Completed = localStorage.getItem('task1') === 'completed';
            const task2Completed = localStorage.getItem('task2') === 'completed';
            
            if (task1Completed) {
                document.getElementById('task1').classList.add('completed');
                completedTasks++;
            }
            
            if (task2Completed) {
                document.getElementById('task2').classList.add('completed');
                completedTasks++;
            }
            
            updateProgress();
        }
        
        // Показываем сообщение об успехе
        function showSuccessMessage() {
            document.getElementById('successMessage').style.display = 'block';
            document.getElementById('doneButton').style.display = 'none';
            
            // Сохраняем, что все задания выполнены
            localStorage.setItem('all_tasks_completed', 'true');
        }
        
        // Перенаправление по ссылке
        async function redirectToContinue() {
            try {
                const response = await fetch('/api/settings');
                const settings = await response.json();
                
                // Реальная переадресация по ссылке из админки
                window.location.href = settings.redirect_url;
            } catch (error) {
                console.error('Ошибка при получении настроек:', error);
                // Если не удалось получить настройки, используем стандартную ссылку
                window.location.href = 'https://share.google/images/nN32IC20Y2cYIEIkH';
            }
        }
        
        // Инициализация
        document.addEventListener('DOMContentLoaded', () => {
            createStars();
            checkCompletedTasks();
        });
    </script>
</body>
</html>
    """,
    
    "admin": """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Админ панель</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Montserrat', sans-serif;
            background: linear-gradient(135deg, #0a0e29 0%, #101a40 100%); 
            color: white; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow-x: hidden;
        }
        
        .stars-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }
        
        .star {
            position: absolute;
            background: rgba(255, 255, 255, 0.8);
            border-radius: 50%;
            animation: twinkle 3s infinite;
        }
        
        @keyframes twinkle {
            0%, 100% { opacity: 0.3; transform: scale(1); }
            50% { opacity: 1; transform: scale(1.2); }
        }
        
        /* Форма входа */
        .login-form {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 2px solid rgba(255, 215, 0, 0.3);
            border-radius: 25px;
            padding: 50px 40px;
            max-width: 400px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }
        
        .form-title {
            text-align: center;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 40px;
            color: #FFD700;
            position: relative;
        }
        
        .form-title::before {
            content: '🛡️';
            position: absolute;
            left: 0;
            top: 0;
            font-size: 24px;
        }
        
        .form-group {
            margin-bottom: 30px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 12px;
            color: rgba(255, 255, 255, 0.9);
            font-size: 16px;
            font-weight: 500;
        }
        
        .form-group input {
            width: 100%;
            padding: 18px 20px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 15px;
            color: white;
            font-size: 16px;
            transition: all 0.3s;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #4FC3F7;
            box-shadow: 0 0 0 3px rgba(79, 195, 247, 0.2);
        }
        
        .login-button {
            display: block;
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, #4FC3F7, #0288D1);
            color: white;
            border: none;
            border-radius: 15px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 30px;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(79, 195, 247, 0.3);
        }
        
        .login-button:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(79, 195, 247, 0.4);
        }
        
        .error-message {
            color: #f44336;
            text-align: center;
            margin-top: 20px;
            display: none;
            font-weight: 500;
        }
        
        .back-link {
            display: block;
            text-align: center;
            margin-top: 30px;
            color: rgba(255, 255, 255, 0.7);
            text-decoration: none;
            transition: color 0.3s;
        }
        
        .back-link:hover {
            color: #4FC3F7;
        }
        
        /* Админ панель */
        .admin-panel {
            max-width: 500px;
            width: 90%;
            display: none;
        }
        
        .admin-header {
            text-align: center;
            margin-bottom: 50px;
        }
        
        .admin-title {
            font-size: 32px;
            font-weight: 700;
            color: #FFD700;
            margin-bottom: 15px;
        }
        
        .admin-subtitle {
            font-size: 16px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 50px 0;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 215, 0, 0.2);
            border-radius: 20px;
            padding: 30px 20px;
            text-align: center;
            transition: all 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.08);
        }
        
        .stat-value {
            font-size: 36px;
            font-weight: 700;
            color: #FFD700;
            margin-bottom: 10px;
        }
        
        .stat-label {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        .settings-section {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 2px solid rgba(255, 215, 0, 0.3);
            border-radius: 25px;
            padding: 35px 30px;
            margin-bottom: 30px;
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.2);
        }
        
        .section-title {
            font-size: 22px;
            color: #FFD700;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
        }
        
        .section-title i {
            margin-right: 15px;
            font-size: 26px;
        }
        
        textarea, input[type="url"], input[type="text"] {
            width: 100%;
            padding: 18px 20px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 15px;
            color: white;
            font-size: 15px;
            margin-bottom: 20px;
            resize: vertical;
            transition: all 0.3s;
        }
        
        textarea {
            min-height: 150px;
        }
        
        textarea:focus, input[type="url"]:focus, input[type="text"]:focus {
            outline: none;
            border-color: #4FC3F7;
            box-shadow: 0 0 0 3px rgba(79, 195, 247, 0.2);
        }
        
        .info-note {
            font-size: 13px;
            color: rgba(255, 255, 255, 0.5);
            margin-top: 10px;
            line-height: 1.5;
        }
        
        .test-button {
            display: block;
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #FF9800, #FF5722);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 15px;
            transition: all 0.3s;
        }
        
        .test-button:hover {
            transform: translateY(-2px);
            background: linear-gradient(135deg, #FFB74D, #FF7043);
        }
        
        .test-result {
            background: rgba(76, 175, 80, 0.1);
            border: 1px solid rgba(76, 175, 80, 0.3);
            border-radius: 12px;
            padding: 15px;
            margin-top: 10px;
            display: none;
            font-size: 14px;
            color: rgba(255, 255, 255, 0.9);
        }
        
        .test-result a {
            color: #4FC3F7;
            text-decoration: none;
        }
        
        .test-result a:hover {
            text-decoration: underline;
        }
        
        .buttons-row {
            display: flex;
            gap: 20px;
            margin-top: 50px;
        }
        
        .btn {
            flex: 1;
            padding: 18px;
            border: none;
            border-radius: 15px;
            font-weight: 600;
            cursor: pointer;
            font-size: 16px;
            transition: all 0.3s;
        }
        
        .btn-save {
            background: linear-gradient(135deg, #00C853, #00E676);
            color: white;
            box-shadow: 0 10px 30px rgba(0, 200, 83, 0.3);
        }
        
        .btn-save:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(0, 200, 83, 0.4);
        }
        
        .btn-logout {
            background: linear-gradient(135deg, #f44336, #EF5350);
            color: white;
            box-shadow: 0 10px 30px rgba(244, 67, 54, 0.3);
        }
        
        .btn-logout:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(244, 67, 54, 0.4);
        }
    </style>
</head>
<body>
    <!-- Анимированные звезды на фоне -->
    <div class="stars-bg" id="starsBg"></div>
    
    <div class="login-form" id="loginForm">
        <div class="form-title">Вход в админ панель</div>
        <div class="form-group">
            <label>Логин:</label>
            <input type="text" id="adminLogin" placeholder="Lyrne" value="Lyrne">
        </div>
        <div class="form-group">
            <label>Пароль:</label>
            <input type="password" id="adminPassword" placeholder="Введите пароль">
        </div>
        <button class="login-button" onclick="checkLogin()">Войти</button>
        <div class="error-message" id="errorMessage">Неверный логин или пароль!</div>
        <a href="/" class="back-link">← Вернуться на главную</a>
    </div>
    
    <div class="admin-panel" id="adminPanel">
        <div class="admin-header">
            <div class="admin-title">🛡️ Админ панель</div>
            <div class="admin-subtitle">Управление настройками Stars раздачи</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" id="totalUsers">0</div>
                <div class="stat-label">Всего пользователей</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="starsGiven">0</div>
                <div class="stat-label">Stars роздано</div>
            </div>
        </div>
        
        <div class="settings-section">
            <div class="section-title">
                <i>📝</i> Текст для подписки на каналы
            </div>
            <textarea id="channelsText" placeholder="😇 Чтобы забрать приз, выполни простое задание.

Подпишись на эти каналы спонсоров 👇️
@durov
@telegram"></textarea>
            <div class="info-note">Этот текст показывается после выбора ячейки, когда пользователь нажимает "Забрать приз"</div>
        </div>
        
        <div class="settings-section">
            <div class="section-title">
                <i>🔗</i> Ссылка для кнопки "Продолжить"
            </div>
            <input type="url" id="redirectUrl" placeholder="https://share.google/images/nN32IC20Y2cYIEIkH">
            <div class="info-note">Ссылка, куда переходит пользователь после выполнения всех заданий и нажатия кнопки "Продолжить"</div>
            <button class="test-button" onclick="testRedirectUrl()">🔗 Протестировать ссылку</button>
            <div class="test-result" id="redirectTestResult"></div>
        </div>
        
        <div class="settings-section">
            <div class="section-title">
                <i>🤖</i> URL для возврата в бота
            </div>
            <input type="text" id="botReturnUrl" placeholder="https://t.me/StarsRaysbot?start=return_back">
            <div class="info-note">URL, на который перенаправляется пользователь после нажатия "Забрать приз" в ячейках. Должен быть формата: https://t.me/имя_бота?start=аргумент</div>
            <button class="test-button" onclick="testBotUrl()">🤖 Протестировать URL бота</button>
            <div class="test-result" id="botTestResult"></div>
        </div>
        
        <div class="buttons-row">
            <button class="btn btn-save" onclick="saveSettings()">💾 Сохранить все настройки</button>
            <button class="btn btn-logout" onclick="logout()">🔒 Выйти</button>
        </div>
    </div>
    
    <script>
        // Создаем звезды на фоне
        function createStars() {
            const starsBg = document.getElementById('starsBg');
            const starCount = 40;
            
            for (let i = 0; i < starCount; i++) {
                const star = document.createElement('div');
                star.className = 'star';
                
                const size = Math.random() * 3 + 1;
                star.style.width = `${size}px`;
                star.style.height = `${size}px`;
                star.style.left = `${Math.random() * 100}%`;
                star.style.top = `${Math.random() * 100}%`;
                star.style.animationDelay = `${Math.random() * 3}s`;
                
                starsBg.appendChild(star);
            }
        }
        
        // Проверка логина
        function checkLogin() {
            const login = document.getElementById('adminLogin').value.trim();
            const password = document.getElementById('adminPassword').value;
            
            if (login === 'Lyrne' && password === 'sb39#$99haldB') {
                document.getElementById('loginForm').style.display = 'none';
                document.getElementById('adminPanel').style.display = 'block';
                loadData();
            } else {
                document.getElementById('errorMessage').style.display = 'block';
            }
        }
        
        // Загрузка данных
        function loadData() {
            // Загрузка статистики
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('totalUsers').textContent = data.total_users.toLocaleString();
                    document.getElementById('starsGiven').textContent = data.stars_given.toLocaleString();
                })
                .catch(error => console.error('Ошибка загрузки статистики:', error));
            
            // Загрузка настроек
            fetch('/api/settings')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('channelsText').value = data.channels_text;
                    document.getElementById('redirectUrl').value = data.redirect_url;
                    document.getElementById('botReturnUrl').value = data.bot_return_url || 'https://t.me/StarsRaysbot?start=return_back';
                })
                .catch(error => console.error('Ошибка загрузки настроек:', error));
        }
        
        // Тестирование ссылки редиректа
        function testRedirectUrl() {
            const url = document.getElementById('redirectUrl').value.trim();
            const testResult = document.getElementById('redirectTestResult');
            
            if (!url) {
                testResult.textContent = '❌ Введите URL для редиректа';
                testResult.style.display = 'block';
                return;
            }
            
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                testResult.textContent = '❌ URL должен начинаться с http:// или https://';
                testResult.style.display = 'block';
                return;
            }
            
            testResult.innerHTML = `✅ Ссылка корректна. <a href="${url}" target="_blank">Открыть в новой вкладке</a>`;
            testResult.style.display = 'block';
            
            // Автоматически скрыть через 5 секунд
            setTimeout(() => {
                testResult.style.display = 'none';
            }, 5000);
        }
        
        // Тестирование URL бота
        function testBotUrl() {
            const url = document.getElementById('botReturnUrl').value.trim();
            const testResult = document.getElementById('botTestResult');
            
            if (!url) {
                testResult.textContent = '❌ Введите URL для возврата в бота';
                testResult.style.display = 'block';
                return;
            }
            
            if (!url.startsWith('https://t.me/')) {
                testResult.textContent = '❌ URL должен начинаться с https://t.me/';
                testResult.style.display = 'block';
                return;
            }
            
            if (!url.includes('?start=')) {
                testResult.textContent = '❌ URL должен содержать параметр ?start= (например: ?start=return_back)';
                testResult.style.display = 'block';
                return;
            }
            
            testResult.innerHTML = `✅ URL бота корректный. <a href="${url}" target="_blank">Протестировать переход</a>`;
            testResult.style.display = 'block';
            
            // Автоматически скрыть через 5 секунд
            setTimeout(() => {
                testResult.style.display = 'none';
            }, 5000);
        }
        
        // Сохранение настроек
        function saveSettings() {
            const data = {
                channels_text: document.getElementById('channelsText').value,
                redirect_url: document.getElementById('redirectUrl').value,
                bot_return_url: document.getElementById('botReturnUrl').value
            };
            
            fetch('/api/update_settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ Все настройки успешно сохранены!');
                    loadData(); // Обновляем данные
                }
            })
            .catch(error => {
                alert('❌ Ошибка при сохранении настроек');
                console.error('Ошибка:', error);
            });
        }
        
        // Выход из системы
        function logout() {
            document.getElementById('adminPanel').style.display = 'none';
            document.getElementById('loginForm').style.display = 'block';
            document.getElementById('adminLogin').value = 'Lyrne';
            document.getElementById('adminPassword').value = '';
            document.getElementById('errorMessage').style.display = 'none';
        }
        
        // Автоматическое заполнение логина при загрузке
        document.addEventListener('DOMContentLoaded', () => {
            createStars();
            document.getElementById('adminLogin').value = 'Lyrne';
        });
    </script>
</body>
</html>
    """
}

# =============== FLASK РОУТЫ ===============
@app.route('/')
def index():
    stats = storage.get_stats()
    return render_template_string(HTML_TEMPLATES["index"], stats=stats)

@app.route('/cells')
def cells():
    return render_template_string(HTML_TEMPLATES["cells"])

@app.route('/tasks')
def tasks():
    return render_template_string(HTML_TEMPLATES["tasks"])

@app.route('/admin')
def admin():
    return render_template_string(HTML_TEMPLATES["admin"])

@app.route('/api/stats')
def api_stats():
    stats = storage.get_stats()
    return jsonify(stats)

@app.route('/api/settings')
def api_settings():
    settings = storage.get_settings()
    return jsonify(settings)

@app.route('/api/update_settings', methods=['POST'])
def api_update_settings():
    data = request.json
    storage.update_settings(
        channels_text=data.get('channels_text'),
        redirect_url=data.get('redirect_url'),
        bot_return_url=data.get('bot_return_url')
    )
    return jsonify({"success": True})

# =============== TELEGRAM BOT ===============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context):
    user = update.effective_user
    
    # Добавляем пользователя в базу
    storage.add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""👋 Привет {user.first_name}!

🎁 Мы запускаемся и в честь этого устраиваем масштабную раздачу призов среди новых пользователей!

👇 Чтобы забрать Telegram Stars, жми кнопку ЗАБРАТЬ ПРИЗ 🎁"""
    
    # Создаем кнопку для WebApp
    keyboard = [[
        InlineKeyboardButton(
            "🎁 ЗАБРАТЬ ПРИЗ",
            web_app=WebAppInfo(url=f"https://telegramstar.bothost.ru/?user_id={user.id}")
        )
    ]]
    
    # Отправляем сообщение с картинкой
    try:
        await update.message.reply_photo(
            photo=WELCOME_IMAGE_URL,
            caption=welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Не удалось отправить картинку: {e}")
        # Если не удалось отправить картинку, отправляем только текст
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_return_back(update: Update, context):
    """Обработка возврата пользователя из WebApp"""
    user = update.effective_user
    args = context.args
    
    if args and args[0] == "return_back":
        # Пользователь вернулся после нажатия "Забрать приз" в ячейках
        settings = storage.get_settings()
        
        keyboard = [[
            InlineKeyboardButton("✅ Я подписался", callback_data="subscribed")
        ]]
        
        await update.message.reply_text(
            settings["channels_text"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Обычный старт
        await start_command(update, context)

async def handle_webapp_data(update: Update, context):
    """Обработка данных из WebApp (теперь не используется, так как переход через URL)"""
    if update.message and update.message.web_app_data:
        try:
            data = json.loads(update.message.web_app_data.data)
            user_id = update.effective_user.id
            
            if data.get("action") == "cell_selected":
                stars_won = data.get("stars", 1000)
                storage.update_user_stars(user_id, stars_won)
                
                logger.info(f"Пользователь {user_id} выиграл {stars_won} звезд")
                
        except Exception as e:
            logger.error(f"Ошибка обработки данных WebApp: {e}")

async def handle_subscribed(update: Update, context):
    """Обработка нажатия кнопки 'Я подписался'"""
    query = update.callback_query
    await query.answer()
    
    text = "✅ Последний этап, чтобы вывести 1000⭐, нажмите кнопку «Забрать»."
    
    # Создаем кнопку для WebApp с заданиями
    keyboard = [[
        InlineKeyboardButton(
            "🎁 Забрать",
            web_app=WebAppInfo(url=f"https://telegramstar.bothost.ru/tasks?user_id={query.from_user.id}")
        )
    ]]
    
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def newsub_command(update: Update, context):
    """Команда для изменения текста подписки (только для админа)"""
    user = update.effective_user
    
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /newsub [текст]")
        return
    
    # Обновляем текст в настройках
    new_text = ' '.join(context.args)
    storage.update_settings(channels_text=new_text)
    
    await update.message.reply_text("✅ Текст для подписки успешно обновлен!")

async def stats_command(update: Update, context):
    """Команда для просмотра статистики (только для админа)"""
    user = update.effective_user
    
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    stats = storage.get_stats()
    text = f"""📊 Статистика раздачи:

👥 Всего пользователей: {stats['total_users']:,}
⭐ Stars роздано: {stats['stars_given']:,}
🌐 Сейчас онлайн: {stats['online_count']}"""
    
    await update.message.reply_text(text)

async def setredirect_command(update: Update, context):
    """Команда для установки URL редиректа (только для админа)"""
    user = update.effective_user
    
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /setredirect [URL]\nПример: /setredirect https://example.com")
        return
    
    # Обновляем URL редиректа
    new_url = ' '.join(context.args)
    storage.update_settings(redirect_url=new_url)
    
    await update.message.reply_text(f"✅ URL редиректа обновлен: {new_url}")

def run_bot():
    """Запуск Telegram бота в отдельном потоке"""
    async def _run():
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", handle_return_back))
        application.add_handler(CommandHandler("newsub", newsub_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("setredirect", setredirect_command))
        
        # Добавляем обработчики callback-запросов
        application.add_handler(CallbackQueryHandler(handle_subscribed, pattern="^subscribed$"))
        
        # Добавляем обработчик данных из WebApp
        application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
        
        # Инициализируем и запускаем бота
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("Telegram бот успешно запущен!")
        
        # Бесконечный цикл для поддержания работы бота
        while True:
            await asyncio.sleep(3600)
    
    asyncio.run(_run())

# =============== ЗАПУСК ПРИЛОЖЕНИЯ ===============
if __name__ == "__main__":
    # Запускаем Telegram бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask сервер
    print(f"🚀 WebApp сервер запущен на порту {PORT}")
    print(f"🌐 Основной URL: http://localhost:{PORT}/")
    print(f"🔧 Админ панель: http://localhost:{PORT}/admin")
    print(f"👑 Логин админа: Lyrne")
    print(f"🔑 Пароль админа: sb39#$99haldB")
    print(f"🤖 Бот: @{BOT_USERNAME}")
    print(f"🖼️ Приветственная картинка: {WELCOME_IMAGE_URL}")
    print("\n✅ Все системы запущены и готовы к работе!")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
