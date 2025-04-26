import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.services.auto_reply_service import (
    get_matching_reply,
    find_replies_for_message,
    process_template_variables,
    find_regex_matches,
    get_best_reply
)
from app.models import AutoReplyRule

@pytest.fixture
def mock_db():
    """Mock veritabanı session'ı için fixture"""
    return Mock(spec=Session)

@pytest.fixture
def mock_rules():
    """Test için örnek kurallar oluşturur"""
    rule1 = Mock(spec=AutoReplyRule)
    rule1.id = 1
    rule1.trigger_keywords = "merhaba,selam,hi"
    rule1.response_text = "Merhaba, nasıl yardımcı olabilirim?"
    rule1.is_active = True
    
    rule2 = Mock(spec=AutoReplyRule)
    rule2.id = 2
    rule2.trigger_keywords = "fiyat,ücret,price"
    rule2.response_text = "Fiyat listesi için web sitemizi ziyaret edin."
    rule2.is_active = True
    
    rule3 = Mock(spec=AutoReplyRule)
    rule3.id = 3
    rule3.trigger_keywords = "r:telefon.*numar"
    rule3.response_text = "Telefonumuz: 0212 123 45 67"
    rule3.is_active = True
    
    rule4 = Mock(spec=AutoReplyRule)
    rule4.id = 4
    rule4.trigger_keywords = "r:merhaba\\s*(?P<name>\\w+)"
    rule4.response_text = "Merhaba {name}, nasılsın?"
    rule4.is_active = True
    
    return [rule1, rule2, rule3, rule4]

def test_process_template_variables():
    """Şablon değişkenlerinin işlenmesini test eder"""
    template = "Merhaba {name}, {group} grubuna hoş geldiniz!"
    variables = {
        "name": "Ahmet",
        "group": "Mikrobot Kullanıcıları"
    }
    
    result = process_template_variables(template, variables)
    expected = "Merhaba Ahmet, Mikrobot Kullanıcıları grubuna hoş geldiniz!"
    
    assert result == expected

@patch('app.crud.auto_reply_rule.get_active_rules_by_user')
def test_get_matching_reply(mock_get_active_rules, mock_db, mock_rules):
    """get_matching_reply fonksiyonunu test eder"""
    # Mock ayarları
    mock_get_active_rules.return_value = mock_rules
    
    # Test 1: Basit anahtar kelime eşleşmesi
    reply = get_matching_reply(mock_db, 1, "Merhaba, yardım eder misiniz?")
    assert reply == "Merhaba, nasıl yardımcı olabilirim?"
    
    # Test 2: Farklı bir anahtar kelime
    reply = get_matching_reply(mock_db, 1, "Ürün fiyatları nedir?")
    assert reply == "Fiyat listesi için web sitemizi ziyaret edin."
    
    # Test 3: Eşleşme olmaması durumu
    reply = get_matching_reply(mock_db, 1, "Bu bir test mesajıdır.")
    assert reply is None

@patch('app.crud.auto_reply_rule.get_active_rules_by_user')
def test_find_replies_for_message(mock_get_active_rules, mock_db, mock_rules):
    """find_replies_for_message fonksiyonunu test eder"""
    # Mock ayarları
    mock_get_active_rules.return_value = mock_rules
    
    # Test: Birden fazla eşleşme olan durumda ilk eşleşmeyi döndürmeli
    replies = find_replies_for_message(mock_db, 1, "Merhaba ve selamlar. Fiyat listesi var mı?")
    
    assert len(replies) == 2
    assert replies[0]["rule_id"] == 1
    assert replies[0]["trigger_keyword"] == "merhaba"
    assert replies[0]["response_text"] == "Merhaba, nasıl yardımcı olabilirim?"
    
    assert replies[1]["rule_id"] == 2
    assert replies[1]["trigger_keyword"] == "fiyat"

@patch('app.services.auto_reply_service.re')
@patch('app.crud.auto_reply_rule.get_active_rules_by_user')
def test_find_regex_matches(mock_get_active_rules, mock_re, mock_db, mock_rules):
    """find_regex_matches fonksiyonunu test eder"""
    # Mock ayarları
    mock_get_active_rules.return_value = mock_rules
    
    # Override re.compile davranışı - sadece belirli kuralları eşleştir
    def mock_compile_side_effect(pattern, flags):
        mock_compiled = Mock()
        
        # Telefon pattern testi
        if pattern == "telefon.*numar":
            def search_side_effect(text):
                if "telefon" in text.lower() and "numar" in text.lower():
                    mock_match = Mock()
                    mock_match.groups.return_value = tuple()
                    mock_match.groupdict.return_value = {}
                    return mock_match
                return None
            mock_compiled.search = Mock(side_effect=search_side_effect)
        
        # Merhaba pattern testi
        elif "merhaba" in pattern:
            def search_side_effect(text):
                if "merhaba ahmet" in text.lower():
                    mock_match = Mock()
                    mock_match.groups.return_value = ("ahmet",)
                    mock_match.groupdict.return_value = {"name": "ahmet"}
                    return mock_match
                return None
            mock_compiled.search = Mock(side_effect=search_side_effect)
        
        # Eşleşmeyen pattern
        else:
            mock_compiled.search.return_value = None
            
        return mock_compiled
    
    mock_re.compile.side_effect = mock_compile_side_effect
    mock_re.IGNORECASE = 2  # Gerçek değer önemli değil
    
    # Test 1: Sadece telefon paterni eşleşmeli
    matches = find_regex_matches(mock_db, 1, "Telefon numaranız nedir?")
    
    assert len(matches) == 1, f"Eşleşme sayısı 1 olmalı, bulunan: {len(matches)}"
    assert matches[0]["rule_id"] == 3
    assert matches[0]["response_text"] == "Telefonumuz: 0212 123 45 67"
    
    # Test 2: Sadece merhaba paterni eşleşmeli
    matches = find_regex_matches(mock_db, 1, "merhaba ahmet")
    
    assert len(matches) == 1, f"Eşleşme sayısı 1 olmalı, bulunan: {len(matches)}"
    assert matches[0]["rule_id"] == 4
    assert matches[0]["response_text"] == "Merhaba ahmet, nasılsın?"
    assert matches[0]["named_matches"] == {"name": "ahmet"}
    
    # Test 3: Hiçbir pattern eşleşmemeli
    matches = find_regex_matches(mock_db, 1, "Bu bir test mesajıdır")
    assert len(matches) == 0

@patch('app.services.auto_reply_service.find_regex_matches')
@patch('app.services.auto_reply_service.find_replies_for_message')
def test_get_best_reply(mock_find_replies, mock_find_regex, mock_db):
    """get_best_reply fonksiyonunu test eder"""
    # Test 1: Regex eşleşmesi varsa onu önceliklendirir
    mock_find_regex.return_value = [{
        "rule_id": 3,
        "trigger_pattern": "telefon\\s*numarası",
        "response_text": "Telefonumuz: 0212 123 45 67",
        "matches": (),
        "named_matches": {}
    }]
    mock_find_replies.return_value = [{
        "rule_id": 1,
        "trigger_keyword": "telefon",
        "response_text": "Telefonla ilgili bilgi almak için..."
    }]
    
    reply, meta = get_best_reply(mock_db, 1, "Telefon numaranız nedir?")
    
    assert reply == "Telefonumuz: 0212 123 45 67"
    assert meta["match_type"] == "regex"
    assert meta["rule_id"] == 3
    
    # Test 2: Regex eşleşmesi yoksa keyword eşleşmesini kullanır
    mock_find_regex.return_value = []
    
    reply, meta = get_best_reply(mock_db, 1, "Telefon almak istiyorum")
    
    assert reply == "Telefonla ilgili bilgi almak için..."
    assert meta["match_type"] == "keyword"
    assert meta["rule_id"] == 1
    
    # Test 3: Hiç eşleşme yoksa None döner
    mock_find_replies.return_value = []
    
    reply, meta = get_best_reply(mock_db, 1, "Bu mesaj hiçbir kuralla eşleşmiyor")
    
    assert reply is None
    assert meta == {} 