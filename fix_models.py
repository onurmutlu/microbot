#!/usr/bin/env python
import os

def fix_model_imports():
    model_dir = "app/models"
    files = os.listdir(model_dir)
    
    for file in files:
        if file.endswith(".py") and file != "base.py" and file != "__init__.py":
            file_path = os.path.join(model_dir, file)
            with open(file_path, 'r') as f:
                content = f.read()
            
            if "from app.db.base_class import Base" in content:
                print(f"Fixing {file_path}")
                content = content.replace("from app.db.base_class import Base", "from app.models.base import Base")
                
                with open(file_path, 'w') as f:
                    f.write(content)
                    
    print("All model files have been fixed.")

if __name__ == "__main__":
    fix_model_imports() 