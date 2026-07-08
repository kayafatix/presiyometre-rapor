"""
Presiyometre Deney Raporu - Web/Mobil Versiyonu (Render.com deploy)
app.py'den tüm mantığı alır, sadece mode='web' ile çalıştırır.
"""
from app import app, render_template, request, rapor as _rapor_func
import os

# Web modunda rapor endpoint'ini override et
@app.route('/rapor', methods=['POST'], endpoint='rapor_web')
def rapor_web():
    """rapor() fonksiyonunu web modunda çağırır."""
    # app.py'deki rapor fonksiyonu mode='desktop' kullanıyor
    # Burada template'e mode='web' göndermek için monkey-patch
    pass


# Daha temiz yaklaşım: app.py'deki render_template çağrısını override etmek yerine
# doğrudan aynı hesaplama mantığını kullan ama mode='web' gönder
app.config['DEPLOY_MODE'] = 'web'

# Original rapor route'unu kaldır ve yenisini ekle
app.view_functions.pop('rapor', None)

from flask import url_for
import uuid
import random
from app import (basinc_dagilimi, hacim_olcer_verisi, hesapla_hidrostatik_basinc,
                 hesapla_hacim_duzeltmesi, hesapla_mebran_duzeltmesi)


@app.route('/rapor', methods=['POST'])
def rapor():
    # Logo yükleme
    logo_url = '/static/logo.png'
    logo_file = request.files.get('logo_dosya')
    if logo_file and logo_file.filename:
        ext = os.path.splitext(logo_file.filename)[1]
        safe_name = f"logo_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
        logo_file.save(save_path)
        logo_url = f'/static/uploads/{safe_name}'

    firma_adi = request.form.get('firma_adi', 'HAN İNŞAAT & MÜHENDİSLİK')

    footer = {
        'sorumlu_adi': request.form.get('sorumlu_adi', ''),
        'sorumlu_unvan': request.form.get('sorumlu_unvan', ''),
        'sicil_no': request.form.get('sicil_no', ''),
        'adres': request.form.get('adres', ''),
        'iletisim': request.form.get('iletisim', ''),
    }

    genel = {
        'proje_adi': request.form.get('proje_adi', ''),
        'musteri_adi': request.form.get('musteri_adi', ''),
        'proje_numarasi': request.form.get('proje_numarasi', ''),
        'sonda_capi': request.form.get('sonda_capi', '76'),
        'sifir_vol_hacim': request.form.get('sifir_vol_hacim', '535'),
        'manometre_yuksekligi': request.form.get('manometre_yuksekligi', '0.60'),
        'presiyometre_turu': request.form.get('presiyometre_turu', 'Menard GC'),
        'deney_tarih': request.form.get('deney_tarih', ''),
    }

    kuyu_sayisi = int(request.form.get('kuyu_sayisi', 1))
    raporlar = []

    for i in range(1, kuyu_sayisi + 1):
        kuyu_adi = request.form.get(f'kuyu_{i}_adi', f'SK-{i}')
        derinlikler_str = request.form.get(f'kuyu_{i}_derinlikler', '')
        derinlikler = [d.strip() for d in derinlikler_str.split(',') if d.strip()]

        for idx, derinlik in enumerate(derinlikler):
            rapor_data = dict(genel)
            rapor_data['kuyu_no'] = kuyu_adi
            rapor_data['deney_derinligi'] = derinlik

            max_basinc = int(request.form.get(f'kuyu_{i}_basinc_{idx}', 20))
            basinc_listesi = basinc_dagilimi(max_basinc)
            kademe_sayisi = len(basinc_listesi)

            sifir_vol = int(genel.get('sifir_vol_hacim', 535))
            hacim_listesi = hacim_olcer_verisi(kademe_sayisi, sifir_vol)
            manometre_yuk = float(genel.get('manometre_yuksekligi', 0.60))

            rapor_data['tablo'] = []
            for k in range(kademe_sayisi):
                deney_bas = basinc_listesi[k]
                hacim_okuma = hacim_listesi[k]
                hidrost = hesapla_hidrostatik_basinc(deney_bas, manometre_yuk)
                hacim_duz = hesapla_hacim_duzeltmesi(hidrost)
                duz_hacim = hacim_okuma - hacim_duz
                mebran_duz = hesapla_mebran_duzeltmesi(duz_hacim)
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

            n = kademe_sayisi - 1
            limit_basinc = float(rapor_data['tablo'][n]['duz_basinc'])
            idx_i = min(3, n)
            pi = float(rapor_data['tablo'][idx_i]['duz_basinc'])
            vi = rapor_data['tablo'][idx_i]['duz_hacim']
            idx_f = max(n - 1, idx_i + 1)
            pf = float(rapor_data['tablo'][idx_f]['duz_basinc'])
            vf = rapor_data['tablo'][idx_f]['duz_hacim']

            delta_p = pf - pi
            delta_v = vf - vi
            vm = (vi + vf) / 2.0
            em = 2.66 * (sifir_vol + vm) * delta_p / delta_v if delta_v != 0 else 0
            net_limit = limit_basinc - pi
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

            raporlar.append(rapor_data)

    return render_template('rapor.html',
                           raporlar=raporlar,
                           toplam=len(raporlar),
                           mode='web',
                           firma_adi=firma_adi,
                           logo_url=logo_url,
                           footer=footer)


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
