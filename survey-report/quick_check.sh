#!/bin/bash

echo "🔍 ПРОВЕРКА СИСТЕМЫ"
echo "=================="

echo ""
echo "1. Структура проекта:"
echo "---------------------"
find /var/www/survey-report -type f -name "*.py" -o -name "*.html" -o -name "*.sh" | sort

echo ""
echo "2. Запускаем инициализацию БД:"
echo "-------------------------------"
cd /var/www/survey-report
python3 init_database.py

echo ""
echo "3. Проверяем зависимости:"
echo "--------------------------"
python3 -c "import flask, pandas, matplotlib, seaborn; print('✅ Все зависимости установлены')" || echo "❌ Нужно установить зависимости"

echo ""
echo "📋 ИНСТРУКЦИЯ:"
echo "=============="
echo ""
echo "1. Установите зависимости:"
echo "   pip install flask pandas matplotlib seaborn openpyxl"
echo ""
echo "2. Запустите сервер:"
echo "   cd /var/www/survey-report"
echo "   python3 final_with_charts.py"
echo "   или"
echo "   ./start_server.sh"
echo ""
echo "3. Откройте в браузере:"
echo "   • http://localhost:5004"
echo "   • http://10.65.93.181:5004"
echo ""
echo "4. Вкладки:"
echo "   • 📍 Локации - все локации"
echo "   • ❓ Вопросы - все вопросы опроса"
echo "   • ✅ Задачи - выполненные задачи"
echo "   • 📥 Импорт - загрузка данных из Excel"
