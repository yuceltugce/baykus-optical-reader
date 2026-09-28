"""Add explicit coverage flags and a transparent aggregate to a completed E1 run."""
from pathlib import Path
import json, statistics, argparse, html

def main():
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);args=p.parse_args();run=args.run
 j=json.loads((run/'results.json').read_text());rows=[r for r in j['results'] if r['status']=='diagnostic_only']
 subjects=['turkce','sosyal','matematik','fen'];methods=list(rows[0]['methods'])
 expected={'turkce':160,'sosyal':180,'matematik':160,'fen':160}
 aggregates={m:{s:statistics.median(r['methods'][m][s]['median_px'] for r in rows if r['methods'][m][s]['n']) for s in subjects} for m in methods}
 flags=[]
 for r in rows:
  coverage={s:r['methods']['H_ransac'][s]['n']/expected[s] for s in subjects}
  low=[s for s in subjects if coverage[s]<.8 or s not in r['local_fits']]
  if low:flags.append({'image':r['image'],'review_subjects':low,'coverage':coverage,'local_fallback_subjects':[s for s in subjects if s not in r['local_fits']]})
 summary={'aggregation':'median of per-image held-out automatic-match median distances, not ground truth','image_count':len(rows),'working_height':2000,'expected_held_out_by_subject':expected,'median_px':aggregates,'coverage_review_policy':'<80% of nominal held-out bubbles or no local fit in any subject; diagnostic threshold, not calibrated quality guarantee','review_required':flags,'unresolved_reference':[r for r in json.loads((run/'template.json').read_text())['repairs'] if r['new'] is None]}
 (run/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 table='| Yöntem | Türkçe | Sosyal | Matematik | Fen |\n|---|---:|---:|---:|---:|\n'
 for m in methods:table+='| '+m+' | '+' | '.join(f'{aggregates[m][s]:.2f}' for s in subjects)+' |\n'
 md='''# E1 — Deney sonucu

Referans dışındaki 40 görüntüde altı geometrik yöntem karşılaştırıldı. Aşağıdaki rakamlar görüntü başına medyan hataların medyanıdır; birim, yüksekliği 2000 piksele indirilmiş görüntüde pikseldir. Fiziksel form kimlikleri bilinmediği için 40 bağımsız kağıt üzerinde genelleme iddiası yoktur.

'''+table+'''
## Nasıl yorumlanmalı?

- Ölçülenler otomatik kontur eşleşmeleridir, insan etiketli ground truth değildir. Eşleşmeler başlangıç homografisinin 10 px çevresinden seçildi; büyük hatalar dışarıda kalabilir. Bütün yöntemler aynı değerlendirme noktalarında karşılaştırıldı.
- Yerel model 1, 6, 11, ... satırlarını kullanır. Bu satırlar ölçümden çıkarılmıştır. Bu bir satır ayırma deneyidir; bağımsız kağıt testi değildir.
- Yeni TPS uygulaması SciPy RBFInterpolator ile yazıldı; eski OpenCV notebook sürümünün birebir yeniden çalıştırılması değildir. Saf TPS markerlara tam oturur; residual TPS yumuşatılmıştır.
- Yerel kontur düzeltmesi bu ölçümde umut verici. Ancak yeterli kontrol noktası bulunamayan bloklarda başlangıç homografisine döner. Bu durum sessiz başarı sayılmamalıdır.
- Referanstaki 16 belirsiz merkezin 15'i çoklu eşik + elips tespitiyle düzeltildi ve yakın planları görsel olarak incelendi. Sosyal 44-E otomatik olarak doğrulanamadı; ölçümden dışlandı. Diğer otomatik merkezler de tarayıcıdan alınmış kesin koordinatlar değildir.
- Beş geometri testi geçti: projektif ileri/geri dönüşüm, görülmeyen noktalarda affine artık alanı, belirsiz/uzak aday reddi, eşleşme tekilliği, dejenere kontrol noktalarının reddi.

## Ek inceleme gereken görüntüler

Herhangi bir derste nominal ölçüm noktalarının %80'inden azı eşleşiyorsa veya yerel model kurulamıyorsa aşağıda listelenir. Bu eşik deneysel bir inceleme kuralıdır, kalibre edilmiş güven skoru değildir.

'''
 for f in flags:md+=f"- {f['image']}: {', '.join(f['review_subjects'])}; kapsama "+', '.join(f'{s} %{100*v:.0f}' for s,v in f['coverage'].items())+'\n'
 md+='''
## Sonraki adım

Özellikle düşük kapsamalı görüntülerde kontrast/bulanıklık ve eşleşme hatasını ayır; gerçek merkezleri elle işaretlenmiş küçük bir kontrol kümesi hazırla. Boş/dolu balonlar ve farklı fiziksel kağıtlar ayrı izlenmeli. Yerel yöntem ancak bu kontrolle doğrulandıktan sonra telefon–PC okuyucu akışına bağlanmalı. Hiçbir cevap doğruluğu yüzdesi bu deneyden çıkarılmadı.
'''
 (run/'SUMMARY.md').write_text(md)
 intro='<article><h2>40 görüntüde sonuç</h2><p>Görüntü başına medyan otomatik eşleşme hatalarının medyanı (px). Bu bir doğruluk yüzdesi değildir.</p><table><tr><th>Yöntem</th>'+''.join('<th>'+s+'</th>' for s in subjects)+'</tr>'
 for m in methods:intro+='<tr><td>'+m+'</td>'+''.join(f'<td>{aggregates[m][s]:.2f}</td>' for s in subjects)+'</tr>'
 intro+='</table><p><b>Kapsama incelemesi gereken '+str(len(flags))+' görüntü:</b> '+', '.join(html.escape(f['image']) for f in flags)+'</p><p>Sosyal 44-E referans merkezi otomatik olarak doğrulanamadı. <a href="SUMMARY.md">Yorumlama sınırları ve sonraki adım</a> · <a href="summary.json">Kapsama ayrıntıları</a></p></article>'
 path=run/'index.html';page=path.read_text();page=page.replace('<article>',intro+'<article>',1);path.write_text(page)
 print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
