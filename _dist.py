import re
import app as A

c = A.app.test_client()
ems = []
for t in range(60):
    d = {'proje_adi': 'T', 'musteri_adi': 'M', 'sonda_capi': '76', 'sifir_vol_hacim': '535',
         'manometre_yuksekligi': '0.60', 'presiyometre_turu': 'Menard GC', 'kuyu_sayisi': '1',
         'kuyu_1_adi': 'SK-1', 'kuyu_1_derinlikler': '6', 'kuyu_1_basinc_0': '20', 'rapor_tipi': 'kaya'}
    html = c.post('/rapor', data=d).data.decode('utf-8')
    ems.append(float(re.search(r'Elastisite Mod.*?result-value">([0-9.]+)', html, re.S).group(1)))
ems.sort()
import statistics
print(f'n={len(ems)} min={ems[0]:.0f} p10={ems[len(ems)//10]:.0f} median={statistics.median(ems):.0f} p90={ems[9*len(ems)//10]:.0f} max={ems[-1]:.0f}')
print('under850:', sum(1 for e in ems if e<850), ' over2000:', sum(1 for e in ems if e>2000))
