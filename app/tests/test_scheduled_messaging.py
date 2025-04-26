import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.scheduled_messaging import ScheduledMessagingService
from app.models import User, Group, MessageTemplate, MessageLog

@pytest.fixture
def mock_db():
    """Mock veritabanı session'ı için fixture"""
    return Mock(spec=Session)

@pytest.fixture
def mock_template():
    """Test için örnek mesaj şablonu oluşturur"""
    template = Mock()
    template.id = 1
    template.name = "Test Şablonu"
    template.content = "Test mesajı içeriği"
    template.interval_minutes = 60
    template.is_active = True
    template.user_id = 1
    return template

@pytest.fixture
def mock_group():
    """Test için örnek grup oluşturur"""
    group = Mock()
    group.id = 1
    group.group_id = "123456789"
    group.title = "Test Grubu"
    group.is_selected = True
    group.is_active = True
    group.user_id = 1
    return group

@pytest.fixture
def mock_log():
    """Test için örnek log kaydı oluşturur"""
    log = Mock()
    log.id = 1
    log.group_id = "123456789"
    log.group_title = "Test Grubu"
    log.message_template_id = 1
    log.status = "success"
    log.user_id = 1
    log.sent_at = datetime.utcnow() - timedelta(hours=2)  # 2 saat önce gönderilmiş
    return log

@pytest.fixture
def scheduler_service(mock_db):
    """ScheduledMessagingService instance'ı oluşturur"""
    return ScheduledMessagingService(mock_db)

@patch('app.services.scheduled_messaging.TelegramService')
async def test_start_scheduler(mock_telegram_service, scheduler_service):
    """start_scheduler_for_user fonksiyonunu test eder"""
    # Hazırlık
    user_id = 1
    
    # Eylemi gerçekleştir
    result = await scheduler_service.start_scheduler_for_user(user_id)
    
    # Sonuçları doğrula
    assert result["status"] == "started"
    assert result["user_id"] == user_id
    assert user_id in scheduler_service.running_tasks
    assert not scheduler_service.stop_flags[user_id]
    
    # Temizlik
    await scheduler_service.stop_scheduler_for_user(user_id)

@patch('app.services.scheduled_messaging.TelegramService')
async def test_stop_scheduler(mock_telegram_service, scheduler_service):
    """stop_scheduler_for_user fonksiyonunu test eder"""
    # Hazırlık
    user_id = 1
    await scheduler_service.start_scheduler_for_user(user_id)
    
    # Eylemi gerçekleştir
    result = await scheduler_service.stop_scheduler_for_user(user_id)
    
    # Sonuçları doğrula
    assert result["status"] == "stopped"
    assert result["user_id"] == user_id
    assert scheduler_service.stop_flags[user_id]

@patch('app.services.scheduled_messaging.datetime')
def test_get_scheduler_status(mock_datetime, scheduler_service, mock_db):
    """get_scheduler_status fonksiyonunu test eder"""
    # Hazırlık
    user_id = 1
    mock_now = datetime.utcnow()
    mock_datetime.utcnow.return_value = mock_now
    
    # Veritabanı sorgularını mockla
    mock_query = Mock()
    mock_filter = Mock()
    mock_count = Mock(return_value=3)  # 3 aktif şablon
    
    mock_query_logs = Mock()
    mock_filter_logs = Mock()
    mock_count_logs = Mock(return_value=5)  # Son 24 saatte 5 mesaj
    
    mock_db.query.side_effect = [mock_query, mock_query_logs]
    mock_query.filter.return_value = mock_filter
    mock_filter.count.return_value = mock_count()
    
    mock_query_logs.filter.return_value = mock_filter_logs
    mock_filter_logs.count.return_value = mock_count_logs()
    
    # Eylemi gerçekleştir
    status = scheduler_service.get_scheduler_status(user_id)
    
    # Sonuçları doğrula
    assert status["is_running"] is False  # Başlatılmadığı için False olmalı
    assert status["active_templates"] == 3
    assert status["messages_last_24h"] == 5
    assert status["user_id"] == user_id

@patch('app.services.telegram_service.TelegramService')
@patch('app.services.scheduled_messaging.asyncio.sleep', new_callable=AsyncMock)
async def test_process_scheduled_templates(mock_sleep, mock_telegram_service, scheduler_service, mock_db, mock_template, mock_group, mock_log):
    """_process_scheduled_templates fonksiyonunu test eder"""
    # Hazırlık
    user_id = 1
    
    # TelegramService mockla
    telegram_service_instance = AsyncMock()
    telegram_service_instance.send_message.return_value = {
        "success_count": 1,
        "error_count": 0
    }
    mock_telegram_service.return_value = telegram_service_instance
    
    # Veritabanı sorgularını mockla
    mock_query = Mock()
    mock_filter = Mock()
    mock_all = Mock(return_value=[mock_template])
    
    mock_query_groups = Mock()
    mock_filter_groups = Mock()
    mock_all_groups = Mock(return_value=[mock_group])
    
    mock_query_logs = Mock()
    mock_filter_logs = Mock()
    mock_order_by = Mock()
    mock_first = Mock(return_value=mock_log)
    
    mock_db.query.side_effect = [mock_query, mock_query_groups, mock_query_logs]
    mock_query.filter.return_value = mock_filter
    mock_filter.all.return_value = mock_all()
    
    mock_query_groups.filter.return_value = mock_filter_groups
    mock_filter_groups.all.return_value = mock_all_groups()
    
    mock_query_logs.filter.return_value = mock_filter_logs
    mock_filter_logs.order_by.return_value = mock_order_by
    mock_order_by.first.return_value = mock_first()
    
    # Eylemi gerçekleştir
    await scheduler_service._process_scheduled_templates(user_id, telegram_service_instance)
    
    # Sonuçları doğrula
    telegram_service_instance.send_message.assert_called_once_with(mock_template.id, [mock_group.group_id])
    mock_sleep.assert_called_once_with(3)

if __name__ == "__main__":
    pytest.main(["-xvs", "test_scheduled_messaging.py"]) 