"""
Presiyometre Deney Raporu - HTML/PDF Web Uygulaması
"""
from flask import Flask, render_template, request, url_for, jsonify, send_from_directory, abort
import os
import sys
import uuid
import random
import json
import shutil
import datetime
import subprocess
import tempfile


def resource_path(relative_path):
    """PyInstaller ile paketlendiğinde dosya yollarını doğru çözer."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


app = Flask(__name__,
            template_folder=resource_path('templates'),
            static_folder=resource_path('static'))
app.config['UPLOAD_FOLDER'] = os.path.join(resource_path('static'), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def app_base_dir():
    """Veritabanı gibi kalıcı dosyalar için uygulamanın bulunduğu klasör."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DB_DIR = os.path.join(app_base_dir(), 'database')
os.makedirs(DB_DIR, exist_ok=True)


def sanitize_name(s):
    """Dosya/klasör adı için güvenli hale getirir."""
    s = str(s or '').strip()
    for ch in '\\/:*?"<>|':
        s = s.replace(ch, '-')
    s = s.replace('..', '.').strip('. ')
    return s or 'Adsiz'


@app.template_filter('virgul')
def virgul_filter(value):
    """Ondalık ayırıcıyı gösterimde nokta yerine virgül yapar."""
    if value is None:
        return ''
    return str(value).replace('.', ',')


def static_url_to_path(url):
    """/static/... web yolunu dosya sistemi yoluna çevirir."""
    if not url or not url.startswith('/static/'):
        return None
    rel = url[len('/static/'):]
    return os.path.join(resource_path('static'), rel)


def copy_media_to_db(folder, url, prefix):
    """Logo/imza dosyasını DB klasörüne kopyalar, kopyanın adını döndürür."""
    src = static_url_to_path(url)
    if src and os.path.isfile(src):
        ext = os.path.splitext(src)[1] or '.png'
        dst_name = prefix + ext
        try:
            shutil.copyfile(src, os.path.join(folder, dst_name))
            return dst_name
        except OSError:
            return None
    return None


def basinc_dagilimi(max_bar):
    """
    Deney basıncı dağılımını hesaplar.
    - ≤ 20 bar: 1'er bar artış (0, 1, 2, ..., max_bar) → max 21 satır
    - > 20 bar: Her zaman 21 satır (20 kademe). Önce 1'er, sonda 2'şer artış.
      Örnek: 22 bar → 0,1,...,18,20,22  |  25 bar → 0,1,...,15,17,19,21,23,25
    """
    max_bar = int(max_bar)
    
    if max_bar <= 20:
        # 1'er bar artış, max_bar+1 satır
        return [i for i in range(max_bar + 1)]
    else:
        # Her zaman 21 satır (kademe 0 dahil = 21 satır, 20 adım)
        # a adet 1-bar + b adet 2-bar = 20 adım, toplam = a + 2b = max_bar
        # a + b = 20 → a = 40 - max_bar, b = max_bar - 20
        b = max_bar - 20  # 2-bar adım sayısı
        a = 20 - b        # 1-bar adım sayısı
        
        if a < 0:
            # Çok yüksek bar değerleri: orantılı dağılım
            basinc = [0]
            current = 0
            for step in range(20):
                remaining_steps = 20 - step - 1
                remaining_bar = max_bar - current
                if remaining_steps == 0:
                    current = max_bar
                else:
                    current += int(round(remaining_bar / (remaining_steps + 1)))
                basinc.append(current)
            basinc[-1] = max_bar
            return basinc
        
        basinc = [0]
        current = 0
        # Önce 1'er bar adımlar
        for _ in range(a):
            current += 1
            basinc.append(current)
        # Sonra 2'şer bar adımlar
        for _ in range(b):
            current += 2
            basinc.append(current)
        
        return basinc


def interpolate(x, x_table, y_table):
    """Lineer interpolasyon yapar."""
    if x <= x_table[0]:
        return y_table[0]
    if x >= x_table[-1]:
        return y_table[-1]
    for i in range(len(x_table) - 1):
        if x_table[i] <= x <= x_table[i + 1]:
            ratio = (x - x_table[i]) / (x_table[i + 1] - x_table[i])
            return y_table[i] + ratio * (y_table[i + 1] - y_table[i])
    return y_table[-1]


# Kalibrasyon tabloları (SK.xls'den alınmış varsayılan değerler)
# Hacim Düzeltmesi: Basınç (kg/cm²) → Düzeltme (cm³)
HACIM_DUZ_BASINC = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 20]
HACIM_DUZ_DEGER = [0, 1, 1, 2, 3, 4, 5, 6, 6, 7, 8, 9, 8, 7, 8, 10]

# Mebran Düzeltmesi: Hacim (cm³) → Basınç (kg/cm²)
MEBRAN_HACIM = [15, 80, 140, 200, 250, 300, 350, 400, 480, 650]
MEBRAN_BASINC = [0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25]

# BAR → Elastisite Modülü tablosu (bar: (base_value, tolerance))
ELASTISITE_TABLE = {
    5: (50, 10), 6: (60, 10), 7: (70, 10), 8: (80, 10),
    9: (90, 10), 10: (100, 10), 11: (110, 10), 12: (120, 10),
    13: (130, 10), 14: (150, 20), 15: (170, 20),
    16: (200, 30), 17: (230, 30), 18: (260, 30),
    19: (300, 40), 20: (340, 40), 21: (380, 40), 22: (420, 40), 23: (460, 40),
    24: (500, 50), 25: (550, 50), 26: (600, 50), 27: (650, 50),
    28: (700, 50), 29: (750, 50), 30: (800, 50),
}


def get_elastisite_modulu(max_bar):
    """BAR-Elastisite tablosundan Elastisite Modülü değerini döndürür."""
    max_bar = int(max_bar)
    if max_bar in ELASTISITE_TABLE:
        base, tolerance = ELASTISITE_TABLE[max_bar]
        # Tolerans aralığında rastgele değer
        return round(base + random.uniform(-tolerance, tolerance), 2)
    elif max_bar < 5:
        # 5 altı için en düşük değeri kullan
        base, tolerance = ELASTISITE_TABLE[5]
        return round(base + random.uniform(-tolerance, tolerance), 2)
    else:
        # 30 üstü için en yüksek değeri kullan
        base, tolerance = ELASTISITE_TABLE[30]
        return round(base + random.uniform(-tolerance, tolerance), 2)


def get_pi_pf_indices(max_bar, n):
    """
    Max bar değerine göre Pi ve Pf indekslerini belirler.
    n = son kademe indeksi (kademe_sayisi - 1)
    
    Kurallar (0 noktasından itibaren sayılır, 0 = 1. nokta):
    - 4-5-6 bar: Pi = index 2, Pf = n-1 (sondan bir önceki)
    - 7-8 bar: Pi = index 3, Pf = n-1 (sondan bir önceki)
    - 9-10-11-12 bar: Pi = index 3, Pf = n-2 (sondan 3. nokta)
    - 13-14-15-16-17 bar: Pi = index 3, Pf = n-3 (sondan 4. nokta)
    - 18-30 bar: Pi = index 3, Pf = n-5 (sondan 6. nokta)
    """
    max_bar = int(max_bar)
    
    if max_bar <= 6:
        idx_i = min(2, n)
        idx_f = n - 1
    elif max_bar <= 8:
        idx_i = min(3, n)
        idx_f = n - 1
    elif max_bar <= 12:
        idx_i = min(3, n)
        idx_f = n - 2
    elif max_bar <= 17:
        idx_i = min(3, n)
        idx_f = n - 3
    else:  # 18+
        idx_i = min(3, n)
        idx_f = n - 5
    
    # Güvenlik: idx_f en az idx_i + 1 olmalı
    idx_f = max(idx_f, idx_i + 1)
    # idx_f son noktayı geçmemeli
    idx_f = min(idx_f, n)
    
    return idx_i, idx_f


def hesapla_hidrostatik_basinc(deney_basinci, manometre_yuk):
    """Hidrostatik Basınç = Deney Basıncı + Manometre Yüksekliği / 10"""
    return deney_basinci + manometre_yuk / 10.0


def hesapla_hacim_duzeltmesi(hidrostatik_basinc):
    """Hacim Düzeltmesi - kalibrasyon tablosundan interpolasyon"""
    return round(interpolate(hidrostatik_basinc, HACIM_DUZ_BASINC, HACIM_DUZ_DEGER))


def hesapla_mebran_duzeltmesi(duzeltilmis_hacim):
    """Mebran Düzeltmesi - kalibrasyon tablosundan interpolasyon (Hacim→Basınç)"""
    return interpolate(duzeltilmis_hacim, MEBRAN_HACIM, MEBRAN_BASINC)


def hacim_olcer_verisi(kademe_sayisi, sifir_vol, max_bar=20, rapor_tipi='toprak', depth_idx=0, vi_base=None, dv_kaya=None):
    """
    Hacim ölçer okuması - presiyometre S-eğrisi şeklinde veri üretir.
    3 fazlı: 
      Faz 1 (kademe 0 → idx_pi): Dik yükseliş (ilk temas - hacmin ~60%'ı)
      Faz 2 (idx_pi → idx_pf): Yavaş lineer artış (psödo-elastik bölge, ~25%)
      Faz 3 (idx_pf → n): Hızlı artış (plastik bölge, ~15%)
    """
    sifir_vol = int(sifir_vol)
    if kademe_sayisi <= 1:
        return [0]
    
    n = kademe_sayisi - 1
    idx_pi, idx_pf = get_pi_pf_indices(max_bar, n)
    
    if rapor_tipi == 'kaya':
        # Kaya: 535'e ulaşılmaz. Pi (2 bar) noktasında Vi; oradan sona kadar
        # membran genişlemesi kadar küçük (0-3) artışlarla, hemen hemen paralel.
        idx_pi = min(2, n)
        vi = int(vi_base) if vi_base else random.randint(180, 250)
        dv = int(dv_kaya) if dv_kaya else random.randint(30, 50)  # ΔV küçük → yüksek EM
        values = [0]
        # İlk temas (dik yükseliş): 0 → Vi, ilk idx_pi kademede
        for k in range(1, idx_pi + 1):
            ratio = k / idx_pi
            val = int(vi * (1 - (1 - ratio) ** 2))
            val = max(values[-1] + 5, val + random.randint(-3, 3))
            values.append(min(val, vi))
        if len(values) > idx_pi:
            values[idx_pi] = vi   # 2 bar'da tam Vi
        # Psödo-elastik bölge: küçük (0-3) artışlar, toplam ~dv
        steps = n - idx_pi
        if steps > 0:
            remaining = dv
            cur = vi
            for j in range(steps):
                left = steps - j
                inc = int(round(remaining / left + random.uniform(-0.7, 0.7)))
                inc = max(0, min(3, inc))
                remaining -= inc
                cur += inc
                values.append(cur)
        while len(values) < kademe_sayisi:
            values.append(values[-1])
        return values[:kademe_sayisi]
    
    # Faz dağılımları
    # Faz1 oranı: yüksek basınçta biraz düşür ki hem ΔV (faz2) hem faz3 yükselişi için yer kalsın
    faz1_ratio = 0.55 if max_bar <= 20 else max(0.40, 0.55 - (max_bar - 20) * 0.002)
    vol_faz1 = sifir_vol * faz1_ratio
    # Psödo-elastik ΔV: yüksek basınçta orantılı büyür ki EM aşırı yükselmesin
    faz2_base = random.randint(40, 75)
    scale = (max_bar / 20.0) ** 0.85 if max_bar > 20 else 1.0
    faz2_toplam = int(faz2_base * scale)
    vol_faz2 = vol_faz1 + faz2_toplam
    # Faz 3 (plastik yükseliş) belirgin kalsın: plato tavanı %68 (faz3 ≥ ~%32)
    max_faz2 = int(sifir_vol * 0.68)
    if vol_faz2 > max_faz2:
        vol_faz2 = max_faz2
        faz2_toplam = vol_faz2 - int(vol_faz1)
    vol_faz3 = sifir_vol           # Son faz sonunda %100
    
    values = [0]
    
    # Faz 1: Dik yükseliş (0 → idx_pi)
    for i in range(1, idx_pi + 1):
        ratio = i / idx_pi
        val = int(vol_faz1 * (1 - (1 - ratio) ** 2))
        noise = random.randint(-5, 5)
        val = max(values[-1] + 10, val + noise)
        values.append(min(val, int(vol_faz1)))
    
    # Faz 2: Neredeyse yatay artış (idx_pi → idx_pf), toplam 50-100 cm³
    faz2_steps = idx_pf - idx_pi
    if faz2_steps > 0:
        faz2_start = values[-1]
        faz2_range = faz2_toplam
        for i in range(1, faz2_steps + 1):
            ratio = i / faz2_steps
            val = int(faz2_start + faz2_range * ratio)
            noise = random.randint(-2, 2)
            val = max(values[-1] + 1, val + noise)
            values.append(min(val, int(vol_faz2)))
    
    # Faz 3: Pf sonrası ivmelenen artış (sona doğru belirgin dikleşme)
    faz3_steps = n - idx_pf
    if faz3_steps > 0:
        faz3_start = values[-1]
        faz3_range = vol_faz3 - faz3_start
        for i in range(1, faz3_steps + 1):
            ratio = i / faz3_steps
            curve_val = ratio ** 1.5
            val = int(faz3_start + faz3_range * curve_val)
            val = max(values[-1] + 10, val)
            values.append(min(val, sifir_vol))
    
    # Son değer tam sifir_vol olsun
    if len(values) > 0:
        values[-1] = sifir_vol
    
    # Kademe sayısı tutarlılığı
    while len(values) < kademe_sayisi:
        values.append(sifir_vol)
    values = values[:kademe_sayisi]
    
    return values


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/rapor', methods=['POST'])
def rapor():
    # Logo yükleme
    logo_url = '/static/logo.png'  # varsayılan
    logo_file = request.files.get('logo_dosya')
    if logo_file and logo_file.filename:
        ext = os.path.splitext(logo_file.filename)[1]
        safe_name = f"logo_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
        logo_file.save(save_path)
        logo_url = f'/static/uploads/{safe_name}'

    # İmza yükleme (opsiyonel)
    imza_url = ''
    imza_file = request.files.get('imza_dosya')
    if imza_file and imza_file.filename:
        ext = os.path.splitext(imza_file.filename)[1]
        safe_name = f"imza_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
        imza_file.save(save_path)
        imza_url = f'/static/uploads/{safe_name}'

    # Firma bilgisi
    firma_adi = request.form.get('firma_adi', 'HAN İNŞAAT & MÜHENDİSLİK')
    rapor_tipi = request.form.get('rapor_tipi', 'toprak')

    # Footer bilgileri
    footer = {
        'sorumlu_adi': request.form.get('sorumlu_adi', ''),
        'sorumlu_unvan': request.form.get('sorumlu_unvan', ''),
        'sicil_no': request.form.get('sicil_no', ''),
        'adres': request.form.get('adres', ''),
        'iletisim': request.form.get('iletisim', ''),
    }

    # Genel bilgiler
    genel = {
        'proje_adi': request.form.get('proje_adi', ''),
        'musteri_adi': request.form.get('musteri_adi', ''),
        'proje_numarasi': request.form.get('proje_numarasi', ''),
        'sonda_capi': request.form.get('sonda_capi', '76'),
        'sifir_vol_hacim': request.form.get('sifir_vol_hacim', '535'),
        'yeralti_su_seviyesi': request.form.get('yeralti_su_seviyesi', '').strip(),
        'manometre_yuksekligi': request.form.get('manometre_yuksekligi', '0.60'),
        'presiyometre_turu': request.form.get('presiyometre_turu', 'Menard GC'),
        'deney_tarih': request.form.get('deney_tarih', ''),
    }

    # Kuyu ve derinlik bilgilerini topla
    kuyu_sayisi = int(request.form.get('kuyu_sayisi', 1))
    raporlar = []

    for i in range(1, kuyu_sayisi + 1):
        kuyu_adi = request.form.get(f'kuyu_{i}_adi', f'SK-{i}')
        derinlikler_str = request.form.get(f'kuyu_{i}_derinlikler', '')
        derinlikler = [d.strip() for d in derinlikler_str.split(';') if d.strip()]
        n_der = len(derinlikler)
        vi_list_kaya = []
        dv_list_kaya = []

        if rapor_tipi == 'kaya':
            # Başlangıç hacmi: metre arttıkça 1-5 azalan (kümülatif)
            _kv = random.randint(180, 250)
            vi_list_kaya = []
            for _di in range(n_der):
                if _di > 0:
                    _kv -= random.randint(1, 5)
                vi_list_kaya.append(max(120, _kv))
            # Hedef EM: manuel girilmişse o, yoksa derinlikle artan otomatik (850→~1800)
            em_target_list = []
            for _di in range(n_der):
                _v = request.form.get(f'kuyu_{i}_em_{_di}', '').strip()
                em_target_list.append(float(_v) if _v else None)
            _auto = [850 + (1800 - 850) * _di / (n_der - 1) for _di in range(n_der)] if n_der > 1 else [1200]
            em_target_list = [em_target_list[_di] if em_target_list[_di] else _auto[_di] for _di in range(n_der)]
            # ΔV'yi hedef EM'den geri hesapla (eğri görsel tutarlı olsun)
            dv_list_kaya = []
            for _di in range(n_der):
                _mb = int(request.form.get(f'kuyu_{i}_basinc_{_di}', 20))
                _dP = max(1.0, _mb - 3.0)
                _emt = em_target_list[_di]
                _dvv = 2.66 * _dP * (535 + vi_list_kaya[_di]) / (_emt - 1.33 * _dP) if _emt > 1.33 * _dP else 40
                dv_list_kaya.append(max(6, int(round(_dvv))))
        else:
            # Toprak: EM tablo bazlı (bar→EM ± tolerans), derinlikle artan (sıralı)
            em_values = []
            for _di in range(n_der):
                _mb = int(request.form.get(f'kuyu_{i}_basinc_{_di}', 20))
                em_values.append(get_elastisite_modulu(_mb))
            em_values.sort()

        for idx, derinlik in enumerate(derinlikler):
            rapor_data = dict(genel)
            rapor_data['kuyu_no'] = kuyu_adi
            rapor_data['deney_derinligi'] = derinlik
            try:
                rapor_data['deney_derinligi_disp'] = '{:.2f}'.format(
                    float(str(derinlik).replace(',', '.'))).replace('.', ',')
            except ValueError:
                rapor_data['deney_derinligi_disp'] = str(derinlik)
            
            # Her derinlik için ayrı max basınç (yeni form yapısı)
            max_basinc = int(request.form.get(f'kuyu_{i}_basinc_{idx}', 20))
            
            # Basınç dağılımı hesapla
            basinc_listesi = basinc_dagilimi(max_basinc)
            kademe_sayisi = len(basinc_listesi)
            
            # Hacim ölçer verisi üret
            sifir_vol = int(genel.get('sifir_vol_hacim', 535))
            hacim_listesi = hacim_olcer_verisi(kademe_sayisi, sifir_vol, max_basinc, rapor_tipi, idx,
                                               vi_list_kaya[idx] if idx < len(vi_list_kaya) else None,
                                               dv_list_kaya[idx] if idx < len(dv_list_kaya) else None)
            
            # Manometre yüksekliği
            manometre_yuk = float(genel.get('manometre_yuksekligi', 0.60))
            
            # Tablo verisi oluştur - tüm sütunları hesapla
            rapor_data['tablo'] = []
            for k in range(kademe_sayisi):
                deney_bas = basinc_listesi[k]
                hacim_okuma = hacim_listesi[k]
                
                # 1. Hidrostatik Basınç
                hidrost = hesapla_hidrostatik_basinc(deney_bas, manometre_yuk)
                
                # 2. Hacim Düzeltmesi
                hacim_duz = hesapla_hacim_duzeltmesi(hidrost)
                
                # 3. Düzeltilmiş Hacim
                duz_hacim = hacim_okuma - hacim_duz
                
                # 4. Mebran Düzeltmesi
                mebran_duz = hesapla_mebran_duzeltmesi(duz_hacim)
                
                # 5. Düzeltilmiş Basınç
                duz_basinc = hidrost - mebran_duz
                
                rapor_data['tablo'].append({
                    'kademe': k,
                    'basinc': f"{deney_bas:.2f}",
                    'hacim': hacim_okuma,
                    'hidrost': f"{hidrost:.2f}",
                    'hacim_duz': hacim_duz,
                    'duz_hacim': duz_hacim,
                    'mebran_duz': f"{mebran_duz:.2f}",
                    'duz_basinc': f"{duz_basinc:.2f}",
                })
            
            # Sağ grafikteki son 3 noktayı aynı doğruya hizala (ortadaki noktayı taşı)
            t = rapor_data['tablo']
            if kademe_sayisi >= 3:
                ia, ib, ic = kademe_sayisi - 3, kademe_sayisi - 2, kademe_sayisi - 1
                pa = float(t[ia]['duz_basinc']); va = t[ia]['duz_hacim']
                pc = float(t[ic]['duz_basinc']); vc = t[ic]['duz_hacim']
                pb = float(t[ib]['duz_basinc'])
                if pc != pa:
                    vb = int(round(va + (vc - va) * (pb - pa) / (pc - pa)))
                    t[ib]['duz_hacim'] = vb
                    t[ib]['hacim'] = vb + t[ib]['hacim_duz']
            
            # Tablo her zaman 21 satır olsun (kademe 0-20)
            SABIT_SATIR_SAYISI = 21
            while len(rapor_data['tablo']) < SABIT_SATIR_SAYISI:
                rapor_data['tablo'].append({
                    'kademe': '',
                    'basinc': '',
                    'hacim': '',
                    'hidrost': '',
                    'hacim_duz': '',
                    'duz_hacim': '',
                    'mebran_duz': '',
                    'duz_basinc': '',
                })
            
            # ===== BELİRLENEN DEĞERLER HESAPLA =====
            n = kademe_sayisi - 1  # son kademe indeksi
            
            # Limit Basınç = son kademenin Düzeltilmiş Basıncı
            limit_basinc = float(rapor_data['tablo'][n]['duz_basinc'])
            
            # Pi, Pf indekslerini bar seviyesine göre belirle
            idx_i, idx_f = get_pi_pf_indices(max_basinc, n)
            if rapor_tipi == 'kaya':
                idx_i = min(2, n)   # Kaya: Pi = 2 bar (2. sıradaki), değiştirilebilir
                idx_f = n           # Kaya: Pf = son nokta
            
            pi = float(rapor_data['tablo'][idx_i]['duz_basinc'])
            vi = rapor_data['tablo'][idx_i]['duz_hacim']
            pf = float(rapor_data['tablo'][idx_f]['duz_basinc'])
            vf = rapor_data['tablo'][idx_f]['duz_hacim']
            
            # Hesaplamalar
            delta_p = pf - pi
            delta_v = vf - vi
            vm = (vi + vf) / 2.0
            v0 = sifir_vol
            
            # Elastisite Modülü: toprak → tablo (bar→EM), kaya → manuel/otomatik hedef
            if rapor_tipi == 'kaya':
                em = em_target_list[idx]
            else:
                em = em_values[idx]
            
            # Net Limit Basınç = PL* - Pi
            net_limit = limit_basinc - pi
            
            # E / PL = EM / Net Limit Basınç
            e_pl = em / net_limit if net_limit != 0 else 0
            
            rapor_data['sonuclar'] = {
                'limit_basinc': f"{limit_basinc:.2f}",
                'elastisite': f"{em:.2f}",
                'pi': f"{pi:.2f}",
                'vi': int(vi),
                'pf': f"{pf:.2f}",
                'vf': int(vf),
                'delta_p': f"{delta_p:.2f}",
                'delta_v': int(delta_v),
                'net_limit': f"{net_limit:.2f}",
                'e_pl': f"{e_pl:.2f}",
            }
            rapor_data['max_basinc'] = max_basinc
            rapor_data['rapor_tipi'] = rapor_tipi
            
            raporlar.append(rapor_data)

    return render_template('rapor.html',
                           raporlar=raporlar,
                           toplam=len(raporlar),
                           mode=os.environ.get('DEPLOY_MODE', 'desktop'),
                           firma_adi=firma_adi,
                           logo_url=logo_url,
                           imza_url=imza_url,
                           footer=footer)


@app.route('/db_save', methods=['POST'])
def db_save():
    """Yazdır/Kaydet anında gönderilen föyleri veritabanına yazar."""
    payload = request.get_json(silent=True) or {}
    globals_ = payload.get('globals', {})
    foys = payload.get('foys', [])
    saved = 0
    names = []
    for foy in foys:
        musteri = sanitize_name(foy.get('musteri_adi'))
        proje = sanitize_name(foy.get('proje_adi'))
        kuyu = sanitize_name(foy.get('kuyu_no'))
        derinlik = sanitize_name(foy.get('deney_derinligi'))
        folder = os.path.join(DB_DIR, musteri, proje)
        os.makedirs(folder, exist_ok=True)
        rel_media = '{}/{}'.format(musteri, proje)
        # Logo/imza görsellerini DB klasörüne kopyala (yollar kalıcı olsun)
        g = dict(globals_)
        logo_name = copy_media_to_db(folder, globals_.get('logo_url'), 'logo')
        if logo_name:
            g['logo_url'] = '/db_media/{}/{}'.format(rel_media, logo_name)
        imza_name = copy_media_to_db(folder, globals_.get('imza_url'), 'imza')
        if imza_name:
            g['imza_url'] = '/db_media/{}/{}'.format(rel_media, imza_name)
        # Dosya adı: {Kuyu No}_{Deney Derinligi}m ; aynı ad varsa sona artan numara ekle
        base = '{}_{}m'.format(kuyu, derinlik)
        name = base
        suffix = 0
        n = 1
        while os.path.exists(os.path.join(folder, name + '.json')):
            name = '{}_{}'.format(base, n)
            suffix = n
            n += 1
        with open(os.path.join(folder, name + '.json'), 'w', encoding='utf-8') as f:
            json.dump({'globals': g, 'data': foy}, f, ensure_ascii=False, indent=2)
        names.append(suffix)
        saved += 1
    return jsonify({'ok': True, 'saved': saved, 'names': names})


@app.route('/db_list')
def db_list():
    """Kayıtlı proje klasörlerini ve föyleri listeler."""
    projects = []
    if os.path.isdir(DB_DIR):
        for proje in sorted(os.listdir(DB_DIR)):
            pdir = os.path.join(DB_DIR, proje)
            if not os.path.isdir(pdir):
                continue
            foys = sorted(fn for fn in os.listdir(pdir) if fn.endswith('.json'))
            if foys:
                projects.append({'proje': proje, 'foys': foys})
    return jsonify({'projects': projects})


@app.route('/db_media/<path:subpath>')
def db_media(subpath):
    """DB klasöründeki logo/imza görsellerini sunar."""
    parts = [sanitize_name(p) for p in subpath.replace('\\', '/').split('/') if p]
    if not parts:
        abort(404)
    filename = os.path.basename(parts[-1])
    folder = os.path.join(DB_DIR, *parts[:-1])
    if not os.path.isfile(os.path.join(folder, filename)):
        abort(404)
    return send_from_directory(folder, filename)


@app.route('/db_open', methods=['POST'])
def db_open():
    """Seçili kayıtlı föyleri yükleyip rapor sayfasını yeniden oluşturur."""
    proje = sanitize_name(request.form.get('proje', ''))
    secili = request.form.getlist('foylar')
    pdir = os.path.join(DB_DIR, proje)
    raporlar = []
    globals_ = {}
    if os.path.isdir(pdir):
        if secili:
            files = [os.path.basename(fn) for fn in secili]
        else:
            files = sorted(fn for fn in os.listdir(pdir) if fn.endswith('.json'))
        for fn in files:
            if not fn.endswith('.json'):
                continue
            fp = os.path.join(pdir, fn)
            if os.path.isfile(fp):
                with open(fp, 'r', encoding='utf-8') as f:
                    obj = json.load(f)
                raporlar.append(obj.get('data', {}))
                if not globals_:
                    globals_ = obj.get('globals', {})
    return render_template('rapor.html',
                           raporlar=raporlar,
                           toplam=len(raporlar),
                           mode=os.environ.get('DEPLOY_MODE', 'desktop'),
                           firma_adi=globals_.get('firma_adi', 'HAN İNŞAAT & MÜHENDİSLİK'),
                           logo_url=globals_.get('logo_url', '/static/logo.png'),
                           imza_url=globals_.get('imza_url', ''),
                           footer=globals_.get('footer', {}))


# Tarayıcı (Edge/Chrome) ile native "piksel-mükemmel" PDF üretimi için geçici sayfa deposu
PRINT_PAGES = {}


def find_chromium():
    """Windows'ta yüklü Edge veya Chrome çalıştırılabilirini bulur."""
    pf = os.environ.get('ProgramFiles', r'C:\Program Files')
    pfx = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
    lad = os.environ.get('LocalAppData', '')
    candidates = [
        os.path.join(pfx, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        os.path.join(pf, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        os.path.join(pf, 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(pfx, 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(lad, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


@app.route('/print_page/<token>')
def print_page(token):
    """Native PDF çıktısı için hazırlanan tekil föy HTML sayfasını döndürür."""
    html = PRINT_PAGES.get(token)
    if html is None:
        abort(404)
    return html


@app.route('/pdf_prepare', methods=['POST'])
def pdf_prepare():
    """İstemciden gelen tekil föy HTML'lerini geçici olarak saklar, token döndürür."""
    data = request.get_json(force=True, silent=True) or {}
    pages = data.get('pages', [])
    tokens = []
    for p in pages:
        tok = uuid.uuid4().hex
        PRINT_PAGES[tok] = p.get('html', '')
        tokens.append(tok)
    return jsonify(ok=True, tokens=tokens)


@app.route('/pdf_export', methods=['POST'])
def pdf_export():
    """Her token için Edge/Chrome ile ayrı bir piksel-mükemmel PDF üretir."""
    data = request.get_json(force=True, silent=True) or {}
    items = data.get('items', [])
    musteri = sanitize_name(data.get('musteri') or 'Musteri')
    proje = sanitize_name(data.get('proje') or 'Rapor')
    browser = find_chromium()
    if not browser:
        for it in items:
            PRINT_PAGES.pop(it.get('token'), None)
        return jsonify(ok=False, error='no_browser')

    out_dir = os.path.join(DB_DIR, musteri, proje)
    os.makedirs(out_dir, exist_ok=True)
    base = request.host_url  # ör: http://localhost:8777/
    saved = []
    for it in items:
        tok = it.get('token')
        name = sanitize_name(it.get('filename') or (tok or 'foy'))
        if not tok or tok not in PRINT_PAGES:
            continue
        pdf_path = os.path.join(out_dir, name + '.pdf')
        url = base + 'print_page/' + tok
        profile = tempfile.mkdtemp(prefix='pmpdf_')
        cmd = [
            browser, '--headless', '--disable-gpu', '--no-first-run',
            '--no-default-browser-check', '--user-data-dir=' + profile,
            '--no-pdf-header-footer', '--virtual-time-budget=5000',
            '--print-to-pdf=' + pdf_path, url,
        ]
        try:
            subprocess.run(cmd, timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.isfile(pdf_path):
                saved.append(pdf_path)
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            shutil.rmtree(profile, ignore_errors=True)

    for it in items:
        PRINT_PAGES.pop(it.get('token'), None)

    try:
        if saved and sys.platform.startswith('win'):
            os.startfile(out_dir)  # noqa: S606
    except OSError:
        pass

    return jsonify(ok=True, count=len(saved), total=len(items), dir=out_dir)


@app.route('/db_open_folder', methods=['POST'])
def db_open_folder():
    """Veritabanı klasörünü işletim sisteminin dosya gezgininde açar."""
    try:
        if sys.platform.startswith('win'):
            os.startfile(DB_DIR)  # noqa: S606
        elif sys.platform == 'darwin':
            import subprocess
            subprocess.Popen(['open', DB_DIR])
        else:
            import subprocess
            subprocess.Popen(['xdg-open', DB_DIR])
        return jsonify({'ok': True, 'path': DB_DIR})
    except OSError:
        return jsonify({'ok': False, 'path': DB_DIR})


@app.route('/db_open_upload', methods=['POST'])
def db_open_upload():
    """Seçilen .json föy dosyalarını okuyup rapor sayfasını yeniden oluşturur."""
    files = request.files.getlist('foydosyalari')
    raporlar = []
    globals_ = {}
    for fs in files:
        if not fs or not fs.filename:
            continue
        try:
            obj = json.loads(fs.read().decode('utf-8'))
        except (ValueError, OSError, UnicodeDecodeError):
            continue
        if isinstance(obj, dict):
            raporlar.append(obj.get('data', {}))
            if not globals_:
                globals_ = obj.get('globals', {})
    return render_template('rapor.html',
                           raporlar=raporlar,
                           toplam=len(raporlar),
                           mode=os.environ.get('DEPLOY_MODE', 'desktop'),
                           firma_adi=globals_.get('firma_adi', 'HAN İNŞAAT & MÜHENDİSLİK'),
                           logo_url=globals_.get('logo_url', '/static/logo.png'),
                           imza_url=globals_.get('imza_url', ''),
                           footer=globals_.get('footer', {}))


if __name__ == '__main__':
    import webbrowser
    import threading

    print("=" * 50)
    print("  Presiyometre Deney Raporu Uygulaması")
    print("  http://localhost:5000")
    print("=" * 50)

    # Exe olarak çalıştırıldığında tarayıcıyı otomatik aç
    if getattr(sys, 'frozen', False):
        threading.Timer(1.5, lambda: webbrowser.open('http://localhost:5000')).start()

    app.run(debug=False, port=5000, threaded=True)
