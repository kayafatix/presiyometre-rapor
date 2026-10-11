
    const charts = {};
    const chartsRight = {};
    const originalData = {};
    const editData = {};
    const chartMaxBar = {};
    const MEBRAN_HACIM = [15, 80, 140, 200, 250, 300, 350, 400, 480, 650];
    const MEBRAN_BASINC = [0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25];
    const HACIM_DUZ_BASINC = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,15,20];
    const HACIM_DUZ_DEGER = [0,1,1,2,3,4,5,6,6,7,8,9,8,7,8,10];

    function saveSingleFoy(idx, kuyu, derinlik) {
        // Tüm föyleri gizle, sadece seçileni göster
        var allFoys = document.querySelectorAll('.rapor-sayfa');
        var topBar = document.querySelector('[style*="sticky"]');
        allFoys.forEach(function(f){ f.style.display = 'none'; });
        topBar.style.display = 'none';
        document.getElementById('foy_' + idx).style.display = 'block';
        
        // Dosya adı önerisi
        var now = new Date();
        var dd = String(now.getDate()).padStart(2,'0');
        var mm = String(now.getMonth()+1).padStart(2,'0');
        var yy = String(now.getFullYear()).slice(-2);
        var filename = kuyu + '_' + derinlik + 'm_' + dd + '_' + mm + '_' + yy;
        document.title = filename;
        
        // Yazdır
        window.print();
        
        // Geri göster
        allFoys.forEach(function(f){ f.style.display = ''; });
        topBar.style.display = '';
        document.title = 'Presiyometre Deney Raporu - 1 Föy';
    }

    function downloadFoyPDF(idx, kuyu, derinlik) {
        var element = document.getElementById('foy_' + idx);
        var now = new Date();
        var dd = String(now.getDate()).padStart(2,'0');
        var mm = String(now.getMonth()+1).padStart(2,'0');
        var yy = String(now.getFullYear()).slice(-2);
        var filename = kuyu + '_' + derinlik + 'm_' + dd + '_' + mm + '_' + yy + '.pdf';

        // Toolbar'ları geçici gizle
        var toolbars = element.querySelectorAll('.foy-toolbar, .edit-toolbar, .table-edit-toolbar');
        toolbars.forEach(function(t){ t.style.display = 'none'; });

        var opt = {
            margin: [5, 5, 5, 5],
            filename: filename,
            image: { type: 'jpeg', quality: 0.95 },
            html2canvas: { scale: 2, useCORS: true, scrollY: 0 },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
            pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
        };

        html2pdf().set(opt).from(element).save().then(function() {
            toolbars.forEach(function(t){ t.style.display = ''; });
        });
    }

    function downloadAllPDF() {
        var allFoys = document.querySelectorAll('.rapor-sayfa');
        var topBar = document.querySelector('[style*="sticky"]');

        // Toolbar'ları gizle
        document.querySelectorAll('.foy-toolbar, .edit-toolbar, .table-edit-toolbar').forEach(function(t){ t.style.display = 'none'; });
        topBar.style.display = 'none';

        // Tüm föyleri içeren bir wrapper oluştur
        var wrapper = document.createElement('div');
        allFoys.forEach(function(foy, i) {
            var clone = foy.cloneNode(true);
            if (i < allFoys.length - 1) {
                clone.style.pageBreakAfter = 'always';
            }
            wrapper.appendChild(clone);
        });

        var opt = {
            margin: [5, 5, 5, 5],
            filename: 'Presiyometre_Rapor_Tumu.pdf',
            image: { type: 'jpeg', quality: 0.95 },
            html2canvas: { scale: 2, useCORS: true, scrollY: 0 },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
            pagebreak: { mode: ['css', 'legacy'], after: '.rapor-sayfa' }
        };

        html2pdf().set(opt).from(wrapper).save().then(function() {
            document.querySelectorAll('.foy-toolbar, .edit-toolbar, .table-edit-toolbar').forEach(function(t){ t.style.display = ''; });
            topBar.style.display = '';
        });
    }

    function exportToExcel() {
        if(typeof XLSX === 'undefined'){alert('Excel kütüphanesi yüklenemedi. Lütfen internet bağlantınızı kontrol edin.');return;}
        var wb = XLSX.utils.book_new();
        var sayfalar = document.querySelectorAll('.rapor-sayfa');
        sayfalar.forEach(function(sayfa, si) {
            var rows = sayfa.querySelectorAll('.data-table tbody tr');
            var kuyu = 'Foy'+(si+1), derinlik = '';
            try {
                var labels = sayfa.querySelectorAll('.info-table .label-cell');
                for(var li=0;li<labels.length;li++){
                    var txt = labels[li].textContent||'';
                    if(txt.indexOf('Kuyu')>-1){var vc=labels[li].nextElementSibling;if(vc)kuyu=vc.textContent.trim();}
                    if(txt.indexOf('Derinli')>-1){var vc2=labels[li].nextElementSibling;if(vc2)derinlik=vc2.textContent.trim();}
                }
            } catch(ex){}
            var sheetName = (kuyu + '_' + derinlik + 'm').replace(/[\\\/\?\*\[\]]/g,'').substring(0,31);

            var header = ['Kademe', 'Deney Basıncı (bar)', 'Hacim Ölçer (cm³)', 'Hidrostatik Basınç (kg/cm²)',
                          'Hacim Düzeltmesi (cm³)', 'Düzeltilmiş Hacim (cm³)', 'Mebran Düzeltmesi (kg/cm²)', 'Düzeltilmiş Basınç (kg/cm²)'];
            var data = [header];
            rows.forEach(function(row) {
                var cells = row.querySelectorAll('td');
                if (cells.length >= 8 && cells[1].textContent.trim() !== '') {
                    data.push([
                        parseInt(cells[0].textContent) || 0,
                        parseFloat(cells[1].textContent) || 0,
                        parseInt(cells[2].textContent) || 0,
                        parseFloat(cells[3].textContent) || 0,
                        parseInt(cells[4].textContent) || 0,
                        parseInt(cells[5].textContent) || 0,
                        parseFloat(cells[6].textContent) || 0,
                        parseFloat(cells[7].textContent) || 0
                    ]);
                }
            });

            // Sonuçlar
            var cc = sayfa.querySelectorAll('.bottom-calc-table .calc-value');
            if (cc.length >= 8) {
                data.push([]);
                data.push(['Pᵢ (kg/cm²)', cc[0].textContent, 'Vᵢ (cm³)', cc[1].textContent, 'ΔP (kg/cm²)', cc[2].textContent, 'Net Limit Basınç', cc[3].textContent]);
                data.push(['Pf (kg/cm²)', cc[4].textContent, 'Vf (cm³)', cc[5].textContent, 'ΔV (cm³)', cc[6].textContent, 'E / Pl', cc[7].textContent]);
            }
            var rc = sayfa.querySelectorAll('.results-table .result-value');
            if (rc.length >= 2) {
                data.push([]);
                data.push(['Limit Basınç PL* (kg/cm²)', rc[0].textContent, 'Elastisite Modülü EM (kg/cm²)', rc[1].textContent]);
            }

            var ws = XLSX.utils.aoa_to_sheet(data);
            ws['!cols'] = header.map(function(){ return {wch:18}; });
            XLSX.utils.book_append_sheet(wb, ws, sheetName);
        });
        XLSX.writeFile(wb, 'Presiyometre_Rapor.xlsx');
    }

    function interpolate(x, xT, yT) {
        if (x <= xT[0]) return yT[0];
        if (x >= xT[xT.length-1]) return yT[xT.length-1];
        for (let i = 0; i < xT.length - 1; i++) {
            if (xT[i] <= x && x <= xT[i+1]) return yT[i] + (x - xT[i]) / (xT[i+1] - xT[i]) * (yT[i+1] - yT[i]);
        }
        return yT[yT.length-1];
    }

    function createLeftChart(idx, data, pi, vi, pf, vf) {
        var c = document.getElementById('chart_left_' + idx);
        var p = c.parentNode;
        p.removeChild(c);
        var nc = document.createElement('canvas');
        nc.id = 'chart_left_' + idx;
        p.appendChild(nc);
        var xMax = Math.ceil(data[data.length-1].x) + 1;
        charts[idx] = new Chart(nc.getContext('2d'), {
            type: 'scatter',
            data: { datasets: [
                { label: 'Presiyometre Egrisi', data: data, borderColor: '#1a5276', backgroundColor: '#1a5276', borderWidth: 1.5, pointRadius: 1.5, pointHitRadius: 6, showLine: true, tension: 0.4, fill: false },
                { label: 'Pi, Vi', data: [{x:pi,y:vi}], borderColor: '#e74c3c', backgroundColor: '#e74c3c', pointRadius: 5, pointStyle: 'triangle', showLine: false },
                { label: 'Pf, Vf', data: [{x:pf,y:vf}], borderColor: '#f39c12', backgroundColor: '#f39c12', pointRadius: 5, pointStyle: 'triangle', showLine: false }
            ]},
            options: { responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'top', labels: { font: { family: 'Times New Roman', size: 9 } } }, dragData: false },
                scales: {
                    x: { title: { display: true, text: 'Basinc, P (kg/cm2)', font: { family: 'Times New Roman', size: 10, style: 'italic' } },
                        grid: { color: '#ddd' },
                        ticks: { stepSize: 1, autoSkip: false, font: { size: 9 } },
                        min: 0, max: xMax },
                    y: { title: { display: true, text: 'Hacim, V (cm3)', font: { family: 'Times New Roman', size: 10, style: 'italic' } },
                        grid: { color: '#ddd' },
                        ticks: { stepSize: 100, autoSkip: false, includeBounds: true, font: { size: 9 } },
                        min: 0, max: 600, afterBuildTicks: function(axis){ axis.ticks = [0,100,200,300,400,500,600].map(function(v){return {value:v};});} }
                }
            }
        });
    }

    function createRightChart(idx, data, vi) {
        var c = document.getElementById('chart_right_' + idx);
        var p = c.parentNode;
        p.removeChild(c);
        var nc = document.createElement('canvas');
        nc.id = 'chart_right_' + idx;
        p.appendChild(nc);
        var vLim = 2 * vi;
        var n = data.length, last3 = data.slice(n-3);
        var sX=0,sY=0,sXY=0,sX2=0;
        last3.forEach(function(pt){sX+=pt.x;sY+=pt.y;sXY+=pt.x*pt.y;sX2+=pt.x*pt.x;});
        var m=(3*sXY-sX*sY)/(3*sX2-sX*sX), b=(sY-m*sX)/3;
        var pLim=m!==0?(vLim-b)/m:35, xMax=Math.max(35,pLim+5);
        // Kesik çizgiyi Y eksenine kadar uzat (x=0'daki y değerini hesapla)
        var yAtZero = b;  // x=0'da trend çizgisinin y değeri
        chartsRight[idx] = new Chart(nc.getContext('2d'), {
            type: 'scatter',
            data: { datasets: [
                { label: 'V_lim='+Math.round(vLim), data: [{x:0,y:vLim},{x:xMax,y:vLim}], borderColor: '#f39c12', borderWidth: 1.8, pointRadius: 0, showLine: true, tension: 0, fill: false },
                { label: 'Trend', data: [{x:0,y:yAtZero},{x:pLim,y:vLim}], borderColor: '#f39c12', borderWidth: 1.5, borderDash: [6,4], pointRadius: 0, showLine: true, tension: 0, fill: false },
                { label: 'Son 3', data: last3, borderColor: '#1a5276', backgroundColor: '#1a5276', pointRadius: 1.8, showLine: false }
            ]},
            options: { responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'top', labels: { font: { family: 'Times New Roman', size: 8 } } }, dragData: false },
                scales: { x: { title: { display: true, text: 'P (kg/cm2)', font: { size: 9, style: 'italic' } }, min: 0, max: xMax }, y: { title: { display: true, text: 'V (cm3)', font: { size: 9, style: 'italic' } }, min: 100, max: Math.max(1000, vLim+100) } }
            }
        });
    }

    // Pi/Pf indeks hesaplama (backend mantığıyla aynı)
    function getPiPfIndices(maxBar, n) {
        var idx_i, idx_f;
        if (maxBar <= 6) {
            idx_i = Math.min(2, n);
            idx_f = n - 1;
        } else if (maxBar <= 8) {
            idx_i = Math.min(3, n);
            idx_f = n - 1;
        } else if (maxBar <= 12) {
            idx_i = Math.min(3, n);
            idx_f = n - 2;
        } else if (maxBar <= 17) {
            idx_i = Math.min(3, n);
            idx_f = n - 3;
        } else {
            idx_i = Math.min(3, n);
            idx_f = n - 5;
        }
        idx_f = Math.max(idx_f, idx_i + 1);
        idx_f = Math.min(idx_f, n);
        return [idx_i, idx_f];
    }

    function rebuildCharts(idx, data) {
        var maxBar = chartMaxBar[idx] || 20;
        var n = data.length - 1;
        var indices = getPiPfIndices(maxBar, n);
        var piI = indices[0], pfI = indices[1];
        var pi=data[piI].x, vi=data[piI].y, pf=data[pfI].x, vf=data[pfI].y;
        if(charts[idx]) charts[idx].destroy();
        if(chartsRight[idx]) chartsRight[idx].destroy();
        createLeftChart(idx, JSON.parse(JSON.stringify(data)), pi, vi, pf, vf);
        createRightChart(idx, JSON.parse(JSON.stringify(data)), vi);
    }

    
    (function() {
        var idx = 1;
        chartMaxBar[idx] = 10;
        var chartData = [{ x: 0.06, y: 0 },{ x: 0.45, y: 167 },{ x: 1.04, y: 255 },{ x: 1.85, y: 292 },{ x: 2.82, y: 297 },{ x: 3.79, y: 304 },{ x: 4.75, y: 312 },{ x: 5.71, y: 321 },{ x: 6.67, y: 329 },{ x: 7.42, y: 378 },{ x: 7.99, y: 527 },];
        originalData[idx] = JSON.parse(JSON.stringify(chartData));
        editData[idx] = JSON.parse(JSON.stringify(chartData));
        var pi=1.85, vi=292, pf=6.67, vf=329;
        createLeftChart(idx, chartData, pi, vi, pf, vf);
        createRightChart(idx, chartData, vi);
    })();
    

    function enableEdit(idx) {
        var ch = charts[idx], sec = document.getElementById('chartSection_' + idx);
        sec.classList.add('edit-active');
        document.getElementById('btnSave_'+idx).style.display='inline-block';
        document.getElementById('btnCancel_'+idx).style.display='inline-block';
        sec.querySelector('.btn-edit').style.display='none';
        ch.data.datasets[0].pointRadius=6; ch.data.datasets[0].pointHoverRadius=9;
        ch.data.datasets[0].pointBackgroundColor='#3498db'; ch.data.datasets[0].borderColor='#85c1e9';
        ch.options.scales.y.max = 550; ch.options.scales.y.min = 0;
        ch.options.plugins.dragData = {
            round: 1, showTooltip: false, dragX: true,
            onDragStart: function(e,di){return di===0;},
            onDrag: function(e,di,i,v){
                if(di!==0)return false;
                if(v.y<0)v.y=0; if(v.y>535)v.y=535; if(v.x<0)v.x=0;
                var tt=document.getElementById('dragTooltip');
                tt.style.display='block'; tt.style.left=(e.clientX||e.x)+15+'px'; tt.style.top=(e.clientY||e.y)-30+'px';
                tt.textContent='P: '+v.x.toFixed(2)+' | V: '+v.y.toFixed(0);
                return v;
            },
            onDragEnd: function(e,di,i,v){ document.getElementById('dragTooltip').style.display='none'; editData[idx][i]={x:v.x,y:v.y}; }
        };
        setTimeout(function(){ ch.resize(); ch.update(); if(chartsRight[idx]){chartsRight[idx].resize();} }, 50);
    }

    function cancelEdit(idx) {
        var sec = document.getElementById('chartSection_' + idx);
        sec.classList.remove('edit-active');
        document.getElementById('btnSave_'+idx).style.display='none';
        document.getElementById('btnCancel_'+idx).style.display='none';
        sec.querySelector('.btn-edit').style.display='inline-block';
        editData[idx] = JSON.parse(JSON.stringify(originalData[idx]));
        document.getElementById('dragTooltip').style.display='none';
        rebuildCharts(idx, originalData[idx]);
    }

    function saveEdit(idx) {
        var sec = document.getElementById('chartSection_' + idx);
        var nd = editData[idx];
        var rapor = sec.closest('.rapor-sayfa');
        var rows = rapor.querySelectorAll('.data-table tbody tr');
        var maxBar = chartMaxBar[idx] || 20;
        var n = nd.length - 1;
        var indices = getPiPfIndices(maxBar, n);
        var piI = indices[0], pfI = indices[1];
        nd.forEach(function(pt,i){ if(i<rows.length){ var c=rows[i].querySelectorAll('td'); c[5].textContent=Math.round(pt.y); c[7].textContent=pt.x.toFixed(2); c[6].textContent=interpolate(pt.y,MEBRAN_HACIM,MEBRAN_BASINC).toFixed(2); }});
        var pi=nd[piI].x,vi=nd[piI].y,pf=nd[pfI].x,vf=nd[pfI].y;
        var lim=nd[nd.length-1].x, dP=pf-pi, dV=vf-vi, vm=(vi+vf)/2;
        var em=dV!==0?2.66*(535+vm)*dP/dV:0, nl=lim-pi, epl=nl!==0?em/nl:0;
        var rc=rapor.querySelectorAll('.results-table .result-value');
        if(rc.length>=2){rc[0].textContent=lim.toFixed(2);rc[1].textContent=em.toFixed(2);}
        var cc=rapor.querySelectorAll('.bottom-calc-table .calc-value');
        if(cc.length>=8){cc[0].textContent=pi.toFixed(2);cc[1].textContent=Math.round(vi);cc[2].textContent=dP.toFixed(2);cc[3].textContent=nl.toFixed(2);cc[4].textContent=pf.toFixed(2);cc[5].textContent=Math.round(vf);cc[6].textContent=Math.round(dV);cc[7].textContent=epl.toFixed(2);}
        sec.classList.remove('edit-active');
        document.getElementById('btnSave_'+idx).style.display='none';
        document.getElementById('btnCancel_'+idx).style.display='none';
        sec.querySelector('.btn-edit').style.display='inline-block';
        originalData[idx] = JSON.parse(JSON.stringify(nd));
        document.getElementById('dragTooltip').style.display='none';
        rebuildCharts(idx, nd);
    }

    function enableTableEdit(idx) {
        var rapor = document.querySelectorAll('.rapor-sayfa')[idx-1];
        var rows = rapor.querySelectorAll('.data-table tbody tr');
        var toolbar = rapor.querySelector('.table-edit-toolbar');
        toolbar.querySelector('.btn-edit').style.display='none';
        toolbar.querySelector('.btn-save').style.display='inline-block';
        toolbar.querySelector('.btn-cancel').style.display='inline-block';
        rows.forEach(function(row){ var cell=row.querySelectorAll('td')[2]; cell.setAttribute('contenteditable','true'); cell.classList.add('editable-cell'); cell.dataset.original=cell.textContent; });
    }
    function cancelTableEdit(idx) {
        var rapor = document.querySelectorAll('.rapor-sayfa')[idx-1];
        var rows = rapor.querySelectorAll('.data-table tbody tr');
        var toolbar = rapor.querySelector('.table-edit-toolbar');
        toolbar.querySelector('.btn-edit').style.display='inline-block';
        toolbar.querySelector('.btn-save').style.display='none';
        toolbar.querySelector('.btn-cancel').style.display='none';
        rows.forEach(function(row){ var cell=row.querySelectorAll('td')[2]; cell.textContent=cell.dataset.original; cell.removeAttribute('contenteditable'); cell.classList.remove('editable-cell'); });
    }
    function saveTableEdit(idx) {
        var rapor = document.querySelectorAll('.rapor-sayfa')[idx-1];
        var rows = rapor.querySelectorAll('.data-table tbody tr');
        var toolbar = rapor.querySelector('.table-edit-toolbar');
        toolbar.querySelector('.btn-edit').style.display='inline-block';
        toolbar.querySelector('.btn-save').style.display='none';
        toolbar.querySelector('.btn-cancel').style.display='none';
        var manYuk=0.60, newData=[];
        rows.forEach(function(row,i){
            var cells=row.querySelectorAll('td');
            var hac=parseInt(cells[2].textContent)||0;
            if(hac<0)hac=0; if(hac>535)hac=535;
            cells[2].textContent=hac; cells[2].removeAttribute('contenteditable'); cells[2].classList.remove('editable-cell');
            var bas=parseFloat(cells[1].textContent)||0;
            var hid=bas+manYuk/10; cells[3].textContent=hid.toFixed(2);
            var hd=Math.round(interpolate(hid,HACIM_DUZ_BASINC,HACIM_DUZ_DEGER)); cells[4].textContent=hd;
            var dh=hac-hd; cells[5].textContent=dh;
            var md=interpolate(dh,MEBRAN_HACIM,MEBRAN_BASINC); cells[6].textContent=md.toFixed(2);
            var db=hid-md; cells[7].textContent=db.toFixed(2);
            newData.push({x:db,y:dh});
        });
        var n=newData.length, piI=Math.min(3,n-1), pfI=Math.max(n-2,piI+1);
        var pi=newData[piI].x,vi=newData[piI].y,pf=newData[pfI].x,vf=newData[pfI].y;
        var lim=newData[n-1].x, dP=pf-pi, dV=vf-vi, vm=(vi+vf)/2;
        var em=dV!==0?2.66*(535+vm)*dP/dV:0, nl=lim-pi, epl=nl!==0?em/nl:0;
        var rc=rapor.querySelectorAll('.results-table .result-value');
        if(rc.length>=2){rc[0].textContent=lim.toFixed(2);rc[1].textContent=em.toFixed(2);}
        var cc=rapor.querySelectorAll('.bottom-calc-table .calc-value');
        if(cc.length>=8){cc[0].textContent=pi.toFixed(2);cc[1].textContent=Math.round(vi);cc[2].textContent=dP.toFixed(2);cc[3].textContent=nl.toFixed(2);cc[4].textContent=pf.toFixed(2);cc[5].textContent=Math.round(vf);cc[6].textContent=Math.round(dV);cc[7].textContent=epl.toFixed(2);}
        originalData[idx]=JSON.parse(JSON.stringify(newData));
        editData[idx]=JSON.parse(JSON.stringify(newData));
        rebuildCharts(idx, newData);
    }
    