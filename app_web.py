"""
Presiyometre Deney Raporu - Web/Mobil Versiyonu (Render.com deploy)
Sadece DEPLOY_MODE='web' ayarlar ve app.py'yi kullanır.
"""
import os
os.environ['DEPLOY_MODE'] = 'web'

from app import app  # noqa: E402

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)

