"""E1: compare marker TPS and local printed-contour correction on held-out rows.
Automatic correspondences are diagnostic pseudo-labels, NOT human ground truth.
"""
from pathlib import Path
import argparse, json, sys, subprocess, shutil
import cv2
import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.optimize import linear_sum_assignment
import edge_baseline as e0

VERSION='E1-v1'

def contours(im):
 gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY); candidates=[]
 for threshold in [140,165,185,205]:
  mask=cv2.threshold(gray,threshold,255,cv2.THRESH_BINARY_INV)[1]
  for c in cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0]:
   if len(c)<5:continue
   x,y,w,h=cv2.boundingRect(c)
   if x<im.shape[1]*.48 or y<im.shape[0]*.29:continue
   if not (16<=w<=31 and 16<=h<=31 and .72<w/h<1.38):continue
   (cx,cy),(a,b),angle=cv2.fitEllipse(c)
   if min(a,b)<15 or max(a,b)>32 or min(a,b)/max(a,b)<.70:continue
   area=cv2.contourArea(c);ellipse_area=np.pi*a*b/4
   quality=abs(1-area/ellipse_area)
   if quality>.20:continue
   candidates.append((quality,np.array([cx,cy]),(a+b)/2))
 result=[];bins={}
 for quality,p,d in sorted(candidates,key=lambda z:z[0]):
  cell=tuple((p//6).astype(int));near=[q for dx in [-1,0,1] for dy in [-1,0,1] for q in bins.get((cell[0]+dx,cell[1]+dy),[])]
  if all(np.linalg.norm(p-q)>6 for q in near):
   result.append((p,d,quality));bins.setdefault(cell,[]).append(p)
 return np.array([r[0] for r in result],np.float64).reshape(-1,2),np.array([r[1] for r in result])

def associate(pred,candidates,gate=10):
 if len(candidates)==0:return np.full((len(pred),2),np.nan),np.zeros(len(pred),bool)
 costs=np.linalg.norm(pred[:,None]-candidates[None,:],axis=2)
 ri,ci=linear_sum_assignment(costs)
 measured=np.full((len(pred),2),np.nan);valid=np.zeros(len(pred),bool)
 for r,c in zip(ri,ci):
  ordered=np.sort(costs[r]);gap=ordered[1]-ordered[0] if len(ordered)>1 else 100
  if costs[r,c]<=gate and c==np.argmin(costs[r]) and gap>=3:
   measured[r]=candidates[c];valid[r]=True
 return measured,valid

def warp(H,pts):return cv2.perspectiveTransform(np.asarray(pts,dtype=np.float64)[:,None,:],H).reshape(-1,2)

def residual_tps(src,residual,query,smoothing=.001):
 if len(src)<4 or np.linalg.matrix_rank(src-src.mean(0))<2:raise ValueError('insufficient 2D control coverage')
 return RBFInterpolator(src/1000,residual,kernel='thin_plate_spline',smoothing=smoothing)(query/1000)

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--all',action='store_true');a=p.parse_args();root=a.root.resolve();out=a.output;out.mkdir(parents=True,exist_ok=False)
 ref,_=e0.load(root/'dataset/flat_front/004.png');rm=e0.markers(ref)
 old=json.loads((root/'experiments/edge_alignment/runs/E0-v2-review/template.json').read_text())
 bubbles=old['bubbles'];pts=np.array([[b['x'],b['y']] for b in bubbles]);rc,rd=contours(ref)
 measured,valid=associate(pts,rc)
 # Refine only the 16 explicitly unresolved reference positions; E0 stays immutable.
 repairs=[]
 for i,b in enumerate(bubbles):
  if not b['contour_refined']:
   repairs.append(dict(index=i,subject=b['subject'],question=b['question'],option=b['option'],old=pts[i].tolist(),new=measured[i].tolist() if valid[i] else None))
   if valid[i]:pts[i]=measured[i];b['x'],b['y']=map(float,pts[i]);b['refinement']='multithreshold_ellipse'
 old['status']='provisional_ellipse_refined_not_ground_truth';old['repairs']=repairs
 (out/'template.json').write_text(json.dumps(old,ensure_ascii=False,indent=2))
 # Diagnostic evaluation excludes local fitting rows and uncertain reference centers.
 subjects=np.array([b['subject'] for b in bubbles]);questions=np.array([b['question'] for b in bubbles]);train_rows=(questions%5==1);ref_valid=valid
 review=[]
 for r in repairs:
  x,y=np.round(pts[r['index']]).astype(int);crop=ref[y-22:y+23,x-22:x+23].copy();cv2.drawMarker(crop,(22,22),(0,180,0),0,10,1);crop=cv2.resize(crop,(180,180))
  card=np.full((210,180,3),255,np.uint8);card[30:]=crop;cv2.putText(card,f"{r['subject']} {r['question']}{r['option']}",(3,21),0,.45,(0,0,0),1);review.append(card)
 e0.save(out/'reference_repairs.jpg',np.vstack([np.hstack(review[i:i+4]) for i in range(0,len(review),4)]))
 paths=sorted((root/'dataset').glob('*/*.png')) if a.all else [root/f'dataset/{g}/001.png' for g in e0.GROUPS]
 records=[];cards=[]
 for path in paths:
  if path==root/'dataset/flat_front/004.png':continue
  im,_=e0.load(path);cm=e0.markers(im);name=path.parent.name+'_'+path.stem
  record=dict(image=str(path.relative_to(root)),methods={})
  try:
   cost=np.linalg.norm((rm/np.array(ref.shape[1::-1]))[:,None]-(cm/np.array(im.shape[1::-1]))[None],axis=2)
   ri,ci=linear_sum_assignment(cost);keep=cost[ri,ci]<.06;ri,ci=ri[keep],ci[keep]
   if len(ri)<6:raise ValueError('fewer than six matched markers')
   cv2.setRNGSeed(42);H,mask=cv2.findHomography(rm[ri],cm[ci],cv2.RANSAC,3.)
   Hall,_=cv2.findHomography(rm[ri],cm[ci],0)
   if H is None or Hall is None:raise ValueError('homography failed')
   base=warp(H,pts);src=rm[ri].astype(float);dst=cm[ci].astype(float);inliers=mask.ravel().astype(bool)
   models={'H_all':warp(Hall,pts),'H_ransac':base}
   models['TPS_markers']=residual_tps(src,dst,pts,smoothing=0)
   mp=warp(H,src)
   models['H_TPS_all']=base+residual_tps(mp,dst-mp,base)
   models['H_TPS_inliers']=base+residual_tps(mp[inliers],(dst-mp)[inliers],base)
   candidates,diameters=contours(im)
   # Freeze automatic pseudo-labels from H BEFORE any method is evaluated.
   obs,ok=associate(base,candidates);ok &= ref_valid
   local=base.copy();local_fits={}
   for subject in e0.BLOCKS:
    block=subjects==subject;fit=block&train_rows&ok
    if fit.sum()>=10:
     delta=obs[fit]-base[fit];median=np.median(delta,axis=0)
     inds=np.where(fit)[0];inds=inds[np.linalg.norm(delta-median,axis=1)<6]
     if len(inds)>=10:
      correction=residual_tps(base[inds],obs[inds]-base[inds],base[block],smoothing=.01)
      # Reject extreme extrapolation instead of silently claiming a correction.
      good=np.linalg.norm(correction,axis=1)<=12
      loc=local[block];loc[good]+=correction[good];local[block]=loc
      local_fits[subject]=dict(anchors=len(inds),rejected_predictions=int((~good).sum()))
   models['H_local_contours']=local
   evaluation=ok&~train_rows;record.update(matched_markers=len(ri),inliers=int(mask.sum()),local_fits=local_fits,automatic_match_count=int(ok.sum()),evaluated_bubbles=int(evaluation.sum()),train_rows='question % 5 == 1',marker_pairs=[dict(reference_id=int(r),candidate_id=int(c),inlier=bool(z)) for r,c,z in zip(ri,ci,inliers)])
   record['automatic_correspondences']=[dict(index=int(i),observed=obs[i].tolist(),split='train' if train_rows[i] else 'evaluation') for i in np.where(ok)[0]]
   for method,pred in models.items():
    metrics={}
    for subject in e0.BLOCKS:
     select=evaluation&(subjects==subject);dist=np.linalg.norm(pred[select]-obs[select],axis=1)
     metrics[subject]=dict(n=int(select.sum()),median_px=float(np.median(dist)) if len(dist) else None,p95_px=float(np.percentile(dist,95)) if len(dist) else None,median_bubble_diameter_fraction=float(np.median(dist)/22) if len(dist) else None)
    record['methods'][method]=metrics
   # Save all predicted centers for reproducible method-independent reevaluation.
   record['predictions']={m:v.tolist() for m,v in models.items()}
   strips=[]
   for y in [620,1150,1700]:
    for method in ['H_ransac','TPS_markers','H_local_contours']:
     canvas=im.copy()
     for idx in np.where(evaluation)[0]:
      p1=tuple(np.round(models[method][idx]).astype(int));p2=tuple(np.round(obs[idx]).astype(int))
      cv2.circle(canvas,p2,6,(0,170,0),1);cv2.drawMarker(canvas,p1,(0,0,255),cv2.MARKER_CROSS,9,1)
     # Use same H only to display all methods in a common frame; does not fit again.
     canonical=cv2.warpPerspective(canvas,np.linalg.inv(H),(ref.shape[1],ref.shape[0]),borderValue=(255,255,255))
     strip=canonical[y-65:y+65,705:1390];band=np.full((26,strip.shape[1],3),255,np.uint8);cv2.putText(band,method,(6,19),0,.55,(0,0,0),1);strips.extend([band,strip])
   filename=name+'_comparison.jpg';e0.save(out/filename,np.vstack(strips))
   table='<table><tr><th>Yöntem</th>'+''.join('<th>'+s+'</th>' for s in e0.BLOCKS)+'</tr>'
   for method,metrics in record['methods'].items():table+='<tr><td>'+method+'</td>'+''.join('<td>'+ (f"{v['median_px']:.2f} / {v['p95_px']:.2f} ({v['n']})" if v['n'] else '—')+'</td>' for v in metrics.values())+'</tr>'
   table+='</table>'
   cards.append(f'<article><h2>{name}</h2><p>{len(ri)} marker, {int(mask.sum())} inlier. Hücreler: medyan / %95 hata px (değerlendirilen balon sayısı).</p>{table}<img loading="lazy" src="{filename}"></article>')
   record['status']='diagnostic_only';print(name,record['evaluated_bubbles'],'held-out auto matches',flush=True)
  except (ValueError,np.linalg.LinAlgError,cv2.error) as err:
   record['status']='failed';record['reason']=str(err);cards.append(f'<article><h2>{name}</h2><p>İşlenemedi: {str(err)}</p></article>');print(name,'FAILED',str(err),flush=True)
  records.append(record)
 metadata=dict(version=VERSION,source_sha256=e0.sha(Path(__file__)),baseline_source_sha256=e0.sha(Path(e0.__file__)),base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),opencv=cv2.__version__,scipy=__import__('scipy').__version__,working_height=2000,ground_truth=False,match_gate_px=10,ambiguity_margin_px=3,local_smoothing=.01,marker_residual_smoothing=.001,reference_repaired=sum(r['new'] is not None for r in repairs),results=records)
 (out/'results.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
 shutil.copy2(__file__,out/'source.py');shutil.copy2(e0.__file__,out/'edge_baseline.py')
 page='''<!doctype html><html lang="tr"><meta charset="utf-8"><title>Baykuş E1 — Geometri karşılaştırması</title><style>body{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 20px;background:#f3f5f7;color:#172331}article{background:white;border-radius:12px;padding:24px;margin:24px 0}p{line-height:1.6}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}img{width:100%;margin-top:18px}</style><h1>E1 — Marker TPS ve yerel kontur düzeltmesi</h1><p><b>Bu sonuçlar otomatik eşleşme göstergesidir; doğrulanmış ground truth veya cevap doğruluğu değildir.</b> Eşleşmeler başlangıç homografisinin 10 px çevresinden seçildiği için büyük sapmalar ve zor balonlar dışarıda kalabilir. Seçim homografiyi kayırabilir. Yöntemler aynı dondurulmuş değerlendirme noktalarında karşılaştırıldı; yerel düzeltmenin eğitildiği satırlar ölçümden çıkarıldı. Aynı fiziksel kağıdın çekimleri bağımsız test örnekleri sayılmaz.</p><p>Yeşil halka: otomatik saptanan kontur merkezi. Kırmızı artı: yöntemin tahmini. Üst, orta ve alt bölgelerde üçer yöntem gösterilir. Tüm pikseller 2000 px yüksekliğindeki çalışma uzayındadır. Çap normalizasyonu yaklaşık 22 px kullanır.</p><p><a href="reference_repairs.jpg">Referanstaki 16 merkezin incelemesi</a> · <a href="results.json">Tüm ölçümler ve koordinatlar</a></p>'''+''.join(cards)+'</html>'
 (out/'index.html').write_text(page)
 print('reference repairs',metadata['reference_repaired'],flush=True)

if __name__=='__main__':main()
