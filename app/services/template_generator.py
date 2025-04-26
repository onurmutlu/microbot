from typing import List, Dict, Any, Optional
import openai
from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.response_template import ResponseTemplate
from sqlalchemy.orm import Session
import json
import re
from datetime import datetime

class TemplateGenerator:
    def __init__(self) -> None:
        self.db: Session = SessionLocal()
        openai.api_key = settings.OPENAI_API_KEY
        
    async def generate_templates(self, count: int = 3) -> List[Dict[str, Any]]:
        """GPT ile şablonlar oluştur"""
        try:
            categories = ["question", "support", "feedback", "information"]
            sentiments = ["positive", "negative", "neutral"]
            
            generated_templates = []
            
            for category in categories:
                for sentiment in sentiments:
                    for _ in range(count):
                        template = await self._generate_template(category, sentiment)
                        if template:
                            db_template = ResponseTemplate(
                                name=template["name"],
                                content=template["content"],
                                category=category,
                                sentiment=sentiment,
                                variables=template["variables"],
                                metadata=template.get("metadata", {})
                            )
                            self.db.add(db_template)
                            generated_templates.append(template)
            
            self.db.commit()
            return generated_templates
            
        except Exception as e:
            logger.error(f"Error generating templates: {str(e)}")
            self.db.rollback()
            return []

    async def _generate_template(self, category: str, sentiment: str) -> Optional[Dict[str, Any]]:
        """GPT ile tek bir şablon oluştur"""
        try:
            system_message = f"""
            Sen bir Telegram mesaj şablonu oluşturucususun.
            Kategori: {category}
            Duygu durumu: {sentiment}
            
            Lütfen aşağıdaki formatta bir şablon oluştur:
            1. Şablon adı (Türkçe, kısa ve açıklayıcı)
            2. Şablon içeriği (Türkçe, doğal ve samimi)
            3. Kullanılacak değişkenler
            4. Metadata (JSON formatında)
            
            Örnek değişkenler:
            - {{user}}: Kullanıcı adı
            - {{date}}: Tarih
            - {{time}}: Saat
            - {{group}}: Grup adı
            - {{admin}}: Admin adı
            
            Metadata örnekleri:
            - priority: öncelik seviyesi (1-5)
            - tags: ilgili etiketler
            - context: kullanım bağlamı
            - examples: örnek kullanımlar
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": "Lütfen bir şablon oluştur."}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            
            # Şablon bilgilerini çıkar
            lines = content.split("\n")
            name = lines[0].strip()
            template_content = lines[1].strip()
            variables = self._extract_variables(template_content)
            
            # Metadata'yı çıkar
            metadata = {}
            metadata_section = "\n".join(lines[3:])
            try:
                metadata = json.loads(metadata_section)
            except:
                metadata = self._parse_metadata(metadata_section)
            
            return {
                "name": name,
                "content": template_content,
                "variables": variables,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error generating template: {str(e)}")
            return None

    def _extract_variables(self, content: str) -> List[str]:
        """Şablon içeriğinden değişkenleri çıkar"""
        variables = re.findall(r"\{([^}]+)\}", content)
        return list(set(variables))

    def _parse_metadata(self, text: str) -> Dict[str, Any]:
        """Metin formatındaki metadata'yı JSON'a çevir"""
        metadata = {}
        lines = text.split("\n")
        
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key in ["priority", "tags", "context", "examples"]:
                    if key == "priority":
                        metadata[key] = int(value)
                    elif key == "tags":
                        metadata[key] = [tag.strip() for tag in value.split(",")]
                    else:
                        metadata[key] = value
        
        return metadata

    async def generate_category_templates(self, category: str, count: int = 3) -> List[Dict[str, Any]]:
        """Belirli bir kategori için şablonlar oluştur"""
        try:
            templates = []
            sentiments = ["positive", "negative", "neutral"]
            
            for sentiment in sentiments:
                for _ in range(count):
                    template = await self._generate_template(category, sentiment)
                    if template:
                        db_template = ResponseTemplate(
                            name=template["name"],
                            content=template["content"],
                            category=category,
                            sentiment=sentiment,
                            variables=template["variables"],
                            metadata=template.get("metadata", {})
                        )
                        self.db.add(db_template)
                        templates.append(template)
            
            self.db.commit()
            return templates
            
        except Exception as e:
            logger.error(f"Error generating category templates: {str(e)}")
            self.db.rollback()
            return []

    async def update_existing_templates(self) -> List[Dict[str, Any]]:
        """Mevcut şablonları güncelle"""
        try:
            updated_templates = []
            templates = self.db.query(ResponseTemplate).all()
            
            for template in templates:
                new_template = await self._generate_template(
                    template.category,
                    template.sentiment
                )
                
                if new_template:
                    template.name = new_template["name"]
                    template.content = new_template["content"]
                    template.variables = new_template["variables"]
                    template.metadata = new_template.get("metadata", {})
                    template.updated_at = datetime.utcnow()
                    updated_templates.append(new_template)
            
            self.db.commit()
            return updated_templates
            
        except Exception as e:
            logger.error(f"Error updating templates: {str(e)}")
            self.db.rollback()
            return []

    async def analyze_template_quality(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Şablon kalitesini analiz et"""
        try:
            system_message = """
            Sen bir şablon kalite analizcisisin.
            Lütfen verilen şablonu aşağıdaki kriterlere göre değerlendir:
            1. Doğallık (1-5)
            2. Etkililik (1-5)
            3. Uygunluk (1-5)
            4. Öneriler
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": json.dumps(template, ensure_ascii=False)}
                ]
            )
            
            analysis = response.choices[0].message.content
            return self._parse_analysis(analysis)
            
        except Exception as e:
            logger.error(f"Error analyzing template quality: {str(e)}")
            return {}

    def _parse_analysis(self, text: str) -> Dict[str, Any]:
        """Analiz metnini JSON'a çevir"""
        analysis = {}
        lines = text.split("\n")
        
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key in ["doğallık", "etkililik", "uygunluk"]:
                    analysis[key] = int(value)
                elif key == "öneriler":
                    analysis[key] = [s.strip() for s in value.split(",")]
        
        return analysis 