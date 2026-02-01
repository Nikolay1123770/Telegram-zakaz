import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

from flask import Flask, request, render_template_string, jsonify, redirect
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import threading
import asyncio

# =============== НАСТРОЙКИ ===============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8562130677:AAFS3N3ls-POoDmq9uTC1D7XU7cijFChEg8")
BOT_USERNAME = "StarsRaysbot"
ADMIN_USERNAME = "Lyrne"
ADMIN_PASSWORD = "sb39#$99haldB"
PORT = int(os.environ.get('PORT', 5000))

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
                "online_count": 42,
                "stars_given": 26500,
                "stars_total": 50000
            },
            "settings": {
                "channels_text": "😇 Чтобы забрать приз, выполни простое задание.\n\nПодпишись на эти каналы спонсоров 👇️\n@durov\n@telegram",
                "redirect_url": "https://share.google/images/nN32IC20Y2cYIEIkH",
                "channel_link": "@StarsRaysbot"  # НОВОЕ: Ссылка на канал для кнопки "Забрать приз"
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
                "tasks_completed": False
            }
            self.data["stats"]["total_users"] = len(self.data["users"])
            self.save_data()
    
    def update_user_stars(self, user_id: int, stars: int):
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["stars_won"] = stars
            self.data["stats"]["stars_given"] += stars
            self.save_data()
    
    def update_settings(self, channels_text=None, redirect_url=None, channel_link=None):
        if channels_text:
            self.data["settings"]["channels_text"] = channels_text
        if redirect_url:
            self.data["settings"]["redirect_url"] = redirect_url
        if channel_link:
            self.data["settings"]["channel_link"] = channel_link
        self.save_data()
    
    def get_settings(self):
        return self.data["settings"]
    
    def get_stats(self):
        return self.data["stats"]

storage = DataStorage()

# =============== FLASK APP ===============
app = Flask(__name__)

# HTML шаблоны
HTML_TEMPLATES = {
    "index": """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Stars - Бесплатная раздача</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: Arial, sans-serif; }
        body { background: linear-gradient(135deg, #0a1929 0%, #1a365d 100%); color: white; min-height: 100vh; }
        .container { max-width: 450px; margin: 0 auto; padding: 20px; }
        .status-bar { background: rgba(255,255,255,0.1); border-radius: 15px; padding: 15px; margin-bottom: 20px; text-align: center; }
        .stars-count { font-size: 28px; font-weight: bold; color: #FFD700; }
        .stars-label { font-size: 12px; color: #90a4ae; }
        .timer { display: flex; justify-content: center; gap: 10px; margin: 30px 0; }
        .time-unit { background: rgba(0,0,0,0.3); padding: 15px; border-radius: 10px; min-width: 70px; }
        .time-number { font-size: 28px; font-weight: bold; color: #4FC3F7; }
        .time-label { font-size: 11px; color: #90a4ae; }
        .main-title { text-align: center; font-size: 32px; font-weight: bold; margin: 20px 0; background: linear-gradient(45deg, #4FC3F7, #0288D1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .subtitle { text-align: center; color: #bbdefb; margin-bottom: 30px; }
        .features-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 30px 0; }
        .feature-card { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; text-align: center; border: 1px solid rgba(64,156,255,0.2); }
        .feature-icon { font-size: 32px; margin-bottom: 10px; }
        .feature-title { font-weight: bold; margin-bottom: 5px; }
        .feature-desc { font-size: 12px; color: #90a4ae; }
        .start-button { display: block; width: 100%; padding: 20px; background: linear-gradient(135deg, #00C853 0%, #00E676 100%); color: white; border: none; border-radius: 25px; font-size: 18px; font-weight: bold; cursor: pointer; margin: 30px 0; text-align: center; text-decoration: none; }
        .start-button:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(0,200,83,0.3); }
        .footer { text-align: center; margin-top: 40px; color: #90a4ae; font-size: 12px; }
        .admin-link { display: inline-block; padding: 10px 20px; background: rgba(255,215,0,0.1); border: 1px solid rgba(255,215,0,0.3); border-radius: 15px; color: #FFD700; text-decoration: none; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="status-bar">
            <div class="stars-count">{{ stats.stars_given }}/{{ stats.stars_total }}</div>
            <div class="stars-label">звёзд заработано</div>
        </div>
        
        <div style="text-align: center; margin: 20px 0;">
            <div style="font-size: 14px; color: #bbdefb; margin-bottom: 15px;">Осталось времени</div>
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
        
        <div class="main-title">Telegram Stars</div>
        <div class="subtitle">В честь наступления 2026 года</div>
        
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
        
        <button class="start-button" onclick="startRaffle()">Начать заработок</button>
        
        <div class="footer">
            <div>Схема ограничена по времени • Только для пользователей Telegram</div>
            <a href="/admin" class="admin-link">🛡️ Админ панель</a>
        </div>
    </div>
    
    <script>
        function startTimer() {
            let hours = 6, minutes = 34, seconds = 41;
            setInterval(() => {
                seconds--;
                if (seconds < 0) { seconds = 59; minutes--; }
                if (minutes < 0) { minutes = 59; hours--; }
                if (hours < 0) { hours = 6; minutes = 34; seconds = 41; }
                document.getElementById('hours').textContent = hours.toString().padStart(2, '0');
                document.getElementById('minutes').textContent = minutes.toString().padStart(2, '0');
                document.getElementById('seconds').textContent = seconds.toString().padStart(2, '0');
            }, 1000);
        }
        
        function startRaffle() {
            const userId = new URLSearchParams(window.location.search).get('user_id') || 'demo';
            window.location.href = '/cells?user_id=' + userId;
        }
        
        document.addEventListener('DOMContentLoaded', startTimer);
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
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: Arial, sans-serif; }
        body { background: linear-gradient(135deg, #0a1929 0%, #1a365d 100%); color: white; min-height: 100vh; }
        .container { max-width: 450px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin: 30px 0; }
        .title { font-size: 32px; font-weight: bold; color: #FFD700; margin-bottom: 15px; }
        .subtitle { font-size: 16px; color: #bbdefb; margin-bottom: 10px; }
        .info-text { font-size: 14px; color: #90a4ae; line-height: 1.5; }
        .cells-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 40px 0; }
        .cell { aspect-ratio: 1; background: rgba(41,182,246,0.2); border-radius: 15px; display: flex; align-items: center; justify-content: center; cursor: pointer; border: 2px solid rgba(79,195,247,0.3); }
        .cell:hover { border-color: #FFD700; transform: translateY(-5px); }
        .cell::before { content: '?'; font-size: 32px; font-weight: bold; }
        .cell.opened { background: rgba(255,215,0,0.9); }
        .cell.opened::before { content: ''; }
        .cell-content { display: none; text-align: center; }
        .cell.opened .cell-content { display: block; }
        .cell-stars { font-size: 20px; font-weight: bold; color: #1a237e; }
        .claim-button { display: block; width: 100%; padding: 20px; background: linear-gradient(135deg, #00C853 0%, #00E676 100%); color: white; border: none; border-radius: 25px; font-size: 18px; font-weight: bold; cursor: pointer; margin: 20px 0; }
        .claim-button:disabled { opacity: 0.5; cursor: not-allowed; }
        .back-button { display: inline-block; padding: 12px 25px; background: rgba(255,255,255,0.1); border-radius: 15px; color: white; text-decoration: none; margin-top: 20px; }
        .result-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); display: flex; align-items: center; justify-content: center; z-index: 1000; display: none; }
        .result-box { background: linear-gradient(135deg, #1a237e 0%, #283593 100%); padding: 40px 30px; border-radius: 25px; text-align: center; max-width: 350px; width: 90%; border: 3px solid rgba(255,215,0,0.5); }
        .result-icon { font-size: 60px; margin-bottom: 20px; }
        .result-title { font-size: 24px; font-weight: bold; color: #FFD700; margin-bottom: 10px; }
        .result-stars { font-size: 42px; font-weight: bold; color: white; margin: 20px 0; }
        .result-message { font-size: 14px; color: #bbdefb; margin-bottom: 25px; }
        .continue-button { padding: 15px 30px; background: #4FC3F7; color: white; border: none; border-radius: 20px; font-size: 16px; font-weight: bold; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">Выберите ячейку</div>
            <div class="subtitle">Игра началась!</div>
            <div class="info-text">Выберите одну из 9 ячеек и получите награду!<br>Схема ограничена по времени • Только для пользователей Telegram</div>
        </div>
        
        <div class="cells-grid" id="cellsGrid"></div>
        
        <button class="claim-button" id="claimButton" disabled>Забрать приз</button>
        
        <div style="text-align: center;">
            <a href="/" class="back-button">← Вернуться назад</a>
        </div>
    </div>
    
    <div class="result-overlay" id="resultOverlay">
        <div class="result-box">
            <div class="result-icon">🎉</div>
            <div class="result-title">Поздравляем!</div>
            <div class="result-stars" id="resultStars">1000 ⭐</div>
            <div class="result-message">Вы выиграли <span id="wonStars">1000</span> Telegram Stars!<br>Все ячейки теперь открыты.</div>
            <button class="continue-button" id="continueButton">Забрать приз</button>
        </div>
    </div>
    
    <script>
        const prizes = [50, 250, 250, 500, 300, 400, 350, 550, 1000];
        let shuffledPrizes = [...prizes].sort((a, b) => a - b);
        let selectedCell = null;
        
        function createCells() {
            const grid = document.getElementById('cellsGrid');
            grid.innerHTML = '';
            shuffledPrizes.forEach((prize, index) => {
                const cell = document.createElement('div');
                cell.className = 'cell';
                cell.dataset.prize = prize;
                cell.innerHTML = '<div class="cell-content">' + prize + ' ⭐</div>';
                cell.onclick = () => selectCell(cell, prize);
                grid.appendChild(cell);
            });
        }
        
        function selectCell(cell, prize) {
            if (selectedCell) return;
            selectedCell = cell;
            cell.classList.add('opened');
            setTimeout(() => {
                document.querySelectorAll('.cell').forEach(c => c.classList.add('opened'));
                document.getElementById('wonStars').textContent = prize;
                document.getElementById('resultStars').textContent = prize + ' ⭐';
                document.getElementById('resultOverlay').style.display = 'flex';
                document.getElementById('claimButton').disabled = false;
            }, 1000);
        }
        
        document.getElementById('claimButton').onclick = function() {
            if (!selectedCell) return;
            const prize = selectedCell.dataset.prize;
            const userId = new URLSearchParams(window.location.search).get('user_id');
            
            if (window.Telegram && window.Telegram.WebApp) {
                Telegram.WebApp.sendData(JSON.stringify({
                    action: "cell_selected",
                    stars: parseInt(prize),
                    user_id: userId
                }));
                setTimeout(() => Telegram.WebApp.close(), 500);
            }
        };
        
        document.getElementById('continueButton').onclick = function() {
            document.getElementById('resultOverlay').style.display = 'none';
            document.getElementById('claimButton').click();
        };
        
        document.addEventListener('DOMContentLoaded', createCells);
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
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: Arial, sans-serif; }
        body { background: linear-gradient(135deg, #0a1929 0%, #1a365d 100%); color: white; min-height: 100vh; }
        .container { max-width: 450px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin: 30px 0; }
        .title { font-size: 28px; font-weight: bold; color: #FFD700; margin-bottom: 15px; }
        .stars-widget { background: rgba(255,215,0,0.15); border-radius: 25px; padding: 25px; margin-bottom: 30px; text-align: center; border: 2px solid rgba(255,215,0,0.3); }
        .stars-amount { font-size: 36px; font-weight: bold; color: #FFD700; margin-bottom: 10px; }
        .stars-text { font-size: 16px; color: white; }
        .progress-widget { background: rgba(255,255,255,0.05); border-radius: 25px; padding: 25px; margin-bottom: 30px; border: 1px solid rgba(79,195,247,0.2); }
        .progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .progress-title { font-size: 18px; font-weight: bold; }
        .progress-count { font-size: 22px; font-weight: bold; color: #4CAF50; }
        .progress-bar { height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; margin-bottom: 30px; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #4CAF50, #2E7D32); width: 0%; border-radius: 4px; }
        .tasks-list { display: flex; flex-direction: column; gap: 20px; }
        .task-item { display: flex; align-items: center; padding: 20px; background: rgba(255,255,255,0.08); border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); }
        .task-item.completed { background: rgba(76,175,80,0.15); border-color: rgba(76,175,80,0.5); }
        .task-icon { font-size: 28px; margin-right: 20px; }
        .task-content { flex: 1; }
        .task-title { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
        .task-description { font-size: 12px; color: #bbdefb; }
        .task-button { padding: 10px 20px; background: #4FC3F7; color: white; border: none; border-radius: 12px; font-weight: bold; cursor: pointer; }
        .checkmark { color: #4CAF50; font-size: 20px; margin-left: 15px; display: none; }
        .task-item.completed .checkmark { display: block; }
        .task-item.completed .task-button { display: none; }
        .done-button { display: block; width: 100%; padding: 20px; background: linear-gradient(135deg, #00C853 0%, #00E676 100%); color: white; border: none; border-radius: 25px; font-size: 18px; font-weight: bold; cursor: pointer; margin: 30px 0; }
        .done-button:disabled { opacity: 0.5; cursor: not-allowed; }
        .success-message { background: rgba(76,175,80,0.15); border: 2px solid rgba(76,175,80,0.5); border-radius: 25px; padding: 30px; margin-top: 30px; display: none; }
        .success-title { font-size: 22px; font-weight: bold; color: #4CAF50; margin-bottom: 15px; text-align: center; }
        .success-text { font-size: 14px; color: white; line-height: 1.5; margin-bottom: 25px; text-align: center; }
        .continue-button { display: block; width: 100%; padding: 15px; background: #4FC3F7; color: white; border: none; border-radius: 20px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .back-button { display: inline-block; padding: 12px 25px; background: rgba(255,255,255,0.1); border-radius: 15px; color: white; text-decoration: none; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">Завершите, чтобы забрать 1.000⭐</div>
        </div>
        
        <div class="stars-widget">
            <div class="stars-amount">1.000 ⭐</div>
            <div class="stars-text">Telegram Stars готовы к получению</div>
        </div>
        
        <div class="progress-widget">
            <div class="progress-header">
                <div class="progress-title">Прогресс выполнения</div>
                <div class="progress-count" id="progressCount">0/2</div>
            </div>
            <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
            
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
        
        <div style="text-align: center;">
            <a href="/" class="back-button">← Вернуться на главную</a>
        </div>
    </div>
    
    <script>
        let completedTasks = 0;
        
        function updateProgress() {
            document.getElementById('progressCount').textContent = completedTasks + '/2';
            document.getElementById('progressFill').style.width = (completedTasks * 50) + '%';
            document.getElementById('doneButton').disabled = completedTasks < 2;
        }
        
        function completeTask(taskId) {
            const taskElement = document.getElementById(taskId);
            const shareText = encodeURIComponent("Бесплатная раздача STARS⭐, успейте, время ограничено! Раздача от бота: @StarsRaysbot");
            
            if (taskId === 'task1') {
                window.open('tg://share?url=&text=' + shareText, '_blank');
            } else {
                window.open('tg://msg?text=' + shareText, '_blank');
            }
            
            setTimeout(() => {
                taskElement.classList.add('completed');
                completedTasks++;
                updateProgress();
            }, 1000);
        }
        
        function showSuccessMessage() {
            document.getElementById('successMessage').style.display = 'block';
            document.getElementById('doneButton').style.display = 'none';
        }
        
        function redirectToContinue() {
            fetch('/api/settings')
                .then(r => r.json())
                .then(data => {
                    window.location.href = data.redirect_url;
                });
        }
        
        document.addEventListener('DOMContentLoaded', updateProgress);
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
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: Arial, sans-serif; }
        body { background: linear-gradient(135deg, #0a1929 0%, #1a365d 100%); color: white; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .login-form { background: rgba(255,255,255,0.05); border-radius: 25px; padding: 40px; max-width: 400px; width: 90%; border: 2px solid rgba(255,215,0,0.3); }
        .form-title { text-align: center; font-size: 24px; font-weight: bold; margin-bottom: 30px; color: #FFD700; }
        .form-group { margin-bottom: 25px; }
        .form-group label { display: block; margin-bottom: 8px; color: #bbdefb; }
        .form-group input { width: 100%; padding: 15px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 12px; color: white; font-size: 16px; }
        .login-button { display: block; width: 100%; padding: 15px; background: #4FC3F7; color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 20px; }
        .error-message { color: #f44336; text-align: center; margin-top: 15px; display: none; }
        .back-link { display: block; text-align: center; margin-top: 25px; color: #bbdefb; text-decoration: none; }
        
        /* Admin Panel Styles */
        .admin-panel { max-width: 500px; margin: 0 auto; padding: 20px; width: 100%; }
        .admin-header { text-align: center; margin-bottom: 40px; }
        .admin-title { font-size: 28px; font-weight: bold; color: #FFD700; margin-bottom: 10px; }
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 40px 0; }
        .stat-card { background: rgba(255,255,255,0.05); border-radius: 20px; padding: 20px; text-align: center; border: 1px solid rgba(255,215,0,0.2); }
        .stat-value { font-size: 28px; font-weight: bold; color: #FFD700; }
        .stat-label { font-size: 12px; color: #bbdefb; margin-top: 5px; }
        .settings-section { background: rgba(255,255,255,0.05); border-radius: 25px; padding: 30px; margin-bottom: 30px; border: 2px solid rgba(255,215,0,0.3); }
        .section-title { font-size: 20px; color: #FFD700; margin-bottom: 25px; display: flex; align-items: center; }
        .section-title i { margin-right: 10px; font-size: 24px; }
        textarea, input { width: 100%; padding: 15px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 12px; color: white; font-size: 14px; margin-bottom: 15px; }
        textarea { min-height: 120px; resize: vertical; }
        .buttons-row { display: flex; gap: 15px; margin-top: 40px; }
        .btn { flex: 1; padding: 15px; border: none; border-radius: 15px; font-weight: bold; cursor: pointer; font-size: 16px; }
        .btn-save { background: #00C853; color: white; }
        .btn-save:hover { background: #00E676; }
        .btn-logout { background: #f44336; color: white; }
        .btn-logout:hover { background: #EF5350; }
        .btn-test { background: #4FC3F7; color: white; }
        .btn-test:hover { background: #29B6F6; }
        .info-note { font-size: 12px; color: #bbdefb; margin-top: 10px; }
        .test-result { background: rgba(76,175,80,0.1); border: 1px solid rgba(76,175,80,0.3); border-radius: 12px; padding: 15px; margin-top: 15px; display: none; }
        .test-result.error { background: rgba(244,67,54,0.1); border-color: rgba(244,67,54,0.3); }
    </style>
</head>
<body>
    <div class="login-form" id="loginForm">
        <div class="form-title">🛡️ Вход в админ панель</div>
        <div class="form-group">
            <label>Логин:</label>
            <input type="text" id="adminLogin" placeholder="Lyrne">
        </div>
        <div class="form-group">
            <label>Пароль:</label>
            <input type="password" id="adminPassword" placeholder="Введите пароль">
        </div>
        <button class="login-button" onclick="checkLogin()">Войти</button>
        <div class="error-message" id="errorMessage">Неверный логин или пароль!</div>
        <a href="/" class="back-link">← Вернуться на главную</a>
    </div>
    
    <div class="admin-panel" id="adminPanel" style="display: none;">
        <div class="admin-header">
            <div class="admin-title">🛡️ Админ панель</div>
            <div style="color: #bbdefb; font-size: 14px;">Управление настройками Stars раздачи</div>
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
            <div class="section-title">📝 Текст для подписки на каналы</div>
            <textarea id="channelsText" placeholder="😇 Чтобы забрать приз, выполни простое задание.

Подпишись на эти каналы спонсоров 👇️
@durov
@telegram"></textarea>
            <div class="info-note">Этот текст показывается после выбора ячейки</div>
        </div>
        
        <div class="settings-section">
            <div class="section-title">🔗 Ссылка для кнопки "Продолжить"</div>
            <input type="url" id="redirectUrl" placeholder="https://share.google/images/nN32IC20Y2cYIEIkH">
            <div class="info-note">Ссылка, куда переходит пользователь после выполнения заданий</div>
        </div>
        
        <div class="settings-section">
            <div class="section-title">🎯 Ссылка на канал для кнопки "Забрать приз"</div>
            <input type="text" id="channelLink" placeholder="@StarsRaysbot">
            <div class="info-note">Эта ссылка используется в кнопке "🎁 ЗАБРАТЬ ПРИЗ" в боте</div>
            <button class="btn btn-test" onclick="testChannelLink()">🔗 Проверить ссылку</button>
            <div class="test-result" id="testResult">Ссылка будет работать как: https://t.me/StarsRaysbot</div>
        </div>
        
        <div class="buttons-row">
            <button class="btn btn-save" onclick="saveSettings()">💾 Сохранить все настройки</button>
            <button class="btn btn-logout" onclick="logout()">🔒 Выйти</button>
        </div>
    </div>
    
    <script>
        function checkLogin() {
            const login = document.getElementById('adminLogin').value;
            const password = document.getElementById('adminPassword').value;
            
            if (login === 'Lyrne' && password === 'sb39#$99haldB') {
                document.getElementById('loginForm').style.display = 'none';
                document.getElementById('adminPanel').style.display = 'block';
                loadData();
            } else {
                document.getElementById('errorMessage').style.display = 'block';
            }
        }
        
        function loadData() {
            // Загружаем статистику
            fetch('/api/stats').then(r => r.json()).then(data => {
                document.getElementById('totalUsers').textContent = data.total_users.toLocaleString();
                document.getElementById('starsGiven').textContent = data.stars_given.toLocaleString();
            });
            
            // Загружаем настройки
            fetch('/api/settings').then(r => r.json()).then(data => {
                document.getElementById('channelsText').value = data.channels_text;
                document.getElementById('redirectUrl').value = data.redirect_url;
                document.getElementById('channelLink').value = data.channel_link || '@StarsRaysbot';
            });
        }
        
        function testChannelLink() {
            const channelLink = document.getElementById('channelLink').value.trim();
            const testResult = document.getElementById('testResult');
            
            if (!channelLink) {
                testResult.textContent = "❌ Введите ссылку на канал";
                testResult.className = "test-result error";
                testResult.style.display = "block";
                return;
            }
            
            // Форматируем ссылку
            let formattedLink = channelLink;
            if (channelLink.startsWith('@')) {
                formattedLink = `https://t.me/${channelLink.substring(1)}`;
            } else if (channelLink.startsWith('https://t.me/')) {
                formattedLink = channelLink;
            } else if (channelLink.startsWith('t.me/')) {
                formattedLink = `https://${channelLink}`;
            } else {
                formattedLink = `https://t.me/${channelLink.replace('@', '')}`;
            }
            
            testResult.innerHTML = `✅ Ссылка будет работать как: <a href="${formattedLink}" target="_blank" style="color: #4FC3F7;">${formattedLink}</a><br>В боте будет кнопка с текстом: 🎁 ЗАБРАТЬ ПРИЗ`;
            testResult.className = "test-result";
            testResult.style.display = "block";
        }
        
        function saveSettings() {
            const data = {
                channels_text: document.getElementById('channelsText').value,
                redirect_url: document.getElementById('redirectUrl').value,
                channel_link: document.getElementById('channelLink').value
            };
            
            fetch('/api/update_settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    alert('✅ Настройки успешно сохранены!');
                    loadData(); // Обновляем данные
                }
            }).catch(error => {
                alert('❌ Ошибка при сохранении настроек');
                console.error(error);
            });
        }
        
        function logout() {
            document.getElementById('adminPanel').style.display = 'none';
            document.getElementById('loginForm').style.display = 'block';
            document.getElementById('adminLogin').value = 'Lyrne';
            document.getElementById('adminPassword').value = '';
            document.getElementById('errorMessage').style.display = 'none';
        }
        
        // Автозаполнение логина при загрузке
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('adminLogin').value = 'Lyrne';
        });
    </script>
</body>
</html>
    """
}

# Flask роуты
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
        channel_link=data.get('channel_link')
    )
    return jsonify({"success": True})

# =============== TELEGRAM BOT ===============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context):
    user = update.effective_user
    storage.add_user(user.id, user.username, user.first_name)
    
    # Получаем настройки из хранилища
    settings = storage.get_settings()
    channel_link = settings.get("channel_link", "@StarsRaysbot")
    
    # Форматируем ссылку для кнопки
    if channel_link.startswith('@'):
        webapp_url = f"https://t.me/{channel_link[1:]}"
    elif channel_link.startswith('https://'):
        webapp_url = channel_link
    else:
        webapp_url = f"https://t.me/{channel_link}"
    
    welcome_text = f"👋 Привет, {user.first_name}!\n\n🎁 Мы запускаемся и в честь этого устраиваем масштабную раздачу призов среди новых пользователей!\n\n👇 Чтобы забрать Telegram Stars, жми кнопку ЗАБРАТЬ ПРИЗ 🎁"
    
    # Создаем кнопку с ссылкой на канал из настроек
    keyboard = [[
        InlineKeyboardButton(
            "🎁 ЗАБРАТЬ ПРИЗ",
            url=webapp_url  # ИСПРАВЛЕНО: используем ссылку из настроек
        )
    ]]
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_webapp_data(update: Update, context):
    if update.message and update.message.web_app_data:
        try:
            data = json.loads(update.message.web_app_data.data)
            user_id = update.effective_user.id
            
            if data.get("action") == "cell_selected":
                stars_won = data.get("stars", 1000)
                storage.update_user_stars(user_id, stars_won)
                
                settings = storage.get_settings()
                keyboard = [[InlineKeyboardButton("✅ Я подписался", callback_data="subscribed")]]
                
                await update.message.reply_text(
                    settings["channels_text"],
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
        except Exception as e:
            logger.error(f"Error: {e}")

async def handle_subscribed(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    text = "✅ Последний этап, чтобы вывести 1000⭐, нажмите кнопку «Забрать»."
    
    keyboard = [[
        InlineKeyboardButton(
            "🎁 Забрать",
            web_app=WebAppInfo(url=f"https://telegramstar.bothost.ru/tasks?user_id={query.from_user.id}")
        )
    ]]
    
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def newsub_command(update: Update, context):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ Нет прав")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /newsub [текст]")
        return
    
    storage.update_settings(channels_text=' '.join(context.args))
    await update.message.reply_text("✅ Текст обновлен!")

async def stats_command(update: Update, context):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ Нет прав")
        return
    
    stats = storage.get_stats()
    text = f"📊 Статистика:\n👥 Пользователей: {stats['total_users']}\n⭐ Stars роздано: {stats['stars_given']:,}"
    await update.message.reply_text(text)

async def setchannel_command(update: Update, context):
    """Команда для установки канала через бота"""
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ Нет прав")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /setchannel [ссылка_на_канал]\nПример: /setchannel @StarsRaysbot")
        return
    
    channel_link = ' '.join(context.args)
    storage.update_settings(channel_link=channel_link)
    await update.message.reply_text(f"✅ Канал обновлен: {channel_link}")

def run_bot():
    """Запуск Telegram бота в отдельном потоке"""
    async def _run():
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("newsub", newsub_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("setchannel", setchannel_command))
        application.add_handler(CallbackQueryHandler(handle_subscribed, pattern="^subscribed$"))
        application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        print("Telegram бот запущен!")
        
        # Бесконечный цикл
        while True:
            await asyncio.sleep(3600)
    
    asyncio.run(_run())

# =============== ЗАПУСК ===============
if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask сервер
    print(f"Flask сервер запущен на порту {PORT}")
    print(f"Админ панель: http://localhost:{PORT}/admin")
    print(f"Логин: Lyrne")
    print(f"Пароль: sb39#$99haldB")
    app.run(host='0.0.0.0', port=PORT, debug=False)
