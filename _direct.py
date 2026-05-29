cd d:/CobraQ/backend
d:/CobraQ/venv2/Scripts/python.exe -c "
import uvicorn
import sys
sys.path.insert(0, '.')
from app.api.router import app
uvicorn.run(app, host='127.0.0.1', port=8001, log_level='debug')
"
