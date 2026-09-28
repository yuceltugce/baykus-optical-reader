"""E0: reproducible marker homography audit. No answer grading or ground-truth claims."""
from pathlib import Path
import argparse, hashlib, json, subprocess, html
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

VERSION = 'E0-v2'
GROUPS = ['flat_front','flat_angled','curved_front','curved_angled']
# Manually seeded on a 1500px-high preview; refined against printed contours.
# Each block: A first row, E first row, A last row, E last row, row count.
BLOCKS = {
 'turkce': ((552,462),(636,462),(549,1291),(635,1291),40),
 'sosyal': ((678,461),(763,460),(675,1418),(762,1418),46),
 'matematik': ((805,459),(890,458),(802,1289),(890,1289),40),
 'fen': ((933,457),(1018,456),(932,1288),(1020,1288),40),
}

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()

def load(path):
 im=cv2.imread(str(path))
 if im is None: raise ValueError(f'Cannot read {path}')
 h,w=im.shape[:2]; scale=2000/h
 return cv2.resize(im,(round(w*scale),2000),interpolation=cv2.INTER_AREA),[w,h]

def markers(im):
 gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
 mask=cv2.threshold(cv2.GaussianBlur(gray,(3,3),0),140,255,cv2.THRESH_BINARY_INV)[1]
 mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
 candidates=[]
 for c in cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0]:
  area=cv2.contourArea(c);x,y,w,h=cv2.boundingRect(c)
  extent=area/(w*h)
  if not 0.00003<=area/(im.shape[0]*im.shape[1])<=0.0008:continue
  if not 0.6<=w/h<=1.6 or extent<0.82:continue
  if len(cv2.approxPolyDP(c,0.03*cv2.arcLength(c,True),True))>6:continue
  candidates.append((np.array([x+w/2,y+h/2]),extent))
 dedup=[]
 for p,e in sorted(candidates,key=lambda z:-z[1]):
  if all(np.linalg.norm(p-q)>15 for q in dedup): dedup.append(p)
 isolated=[p for i,p in enumerate(dedup) if all(i==j or np.linalg.norm(p-q)>=60 for j,q in enumerate(dedup))]
 return np.array(sorted(isolated,key=lambda p:(p[1],p[0])),dtype=np.float32).reshape(-1,2)

def template(im):
 gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
 mask=cv2.threshold(gray,185,255,cv2.THRESH_BINARY_INV)[1]
 centers=[]
 for c in cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0]:
  x,y,w,h=cv2.boundingRect(c);a=cv2.contourArea(c);per=cv2.arcLength(c,True)
  if 17<=w<=28 and 17<=h<=28 and 0.75<w/h<1.3 and per and 4*np.pi*a/per**2>0.65:
   centers.append([x+(w-1)/2,y+(h-1)/2])
 centers=np.array(centers); rows=[]
 for subject,(a,e,b,f,n) in BLOCKS.items():
  a,e,b,f=np.array([a,e,b,f])*2000/1500
  for q in range(n):
   t=q/(n-1)
   for k in range(5):
    u=k/4;seed=(1-t)*((1-u)*a+u*e)+t*((1-u)*b+u*f)
    distances=np.linalg.norm(centers-seed,axis=1)
    idx=int(np.argmin(distances));snap=distances[idx]<=10
    pt=centers[idx] if snap else seed
    rows.append(dict(subject=subject,question=q+1,option='ABCDE'[k],x=float(pt[0]),y=float(pt[1]),contour_refined=bool(snap),seed_shift=float(distances[idx]) if snap else None))
 return rows

def draw(im,points,refs,mask=None):
 out=im.copy()
 for p in points:cv2.circle(out,tuple(np.round(p).astype(int)),4,(30,170,20),1,cv2.LINE_AA)
 for i,p in enumerate(refs):
  c=(255,100,0) if mask is None or mask[i] else (0,0,255)
  cv2.circle(out,tuple(np.round(p).astype(int)),12,c,2)
  cv2.putText(out,str(i),tuple(np.round(p+[12,-8]).astype(int)),cv2.FONT_HERSHEY_SIMPLEX,.5,c,1)
 return out

def save(path,im):
 if not cv2.imwrite(str(path),im):raise IOError(path)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--all',action='store_true');args=parser.parse_args()
 root=args.root;out=args.output
 out.mkdir(parents=True,exist_ok=False)
 reference=root/'dataset/flat_front/004.png';ref,original=load(reference);rm=markers(ref);bubbles=template(ref);pts=np.array([[r['x'],r['y']] for r in bubbles],np.float32)
 refvis=draw(ref,pts,rm)
 cv2.polylines(refvis,[cv2.convexHull(rm).astype(np.int32)],True,(0,180,255),2)
 for row,p in zip(bubbles,pts):
  if not row['contour_refined']:cv2.circle(refvis,tuple(np.round(p).astype(int)),9,(0,0,255),2)
 save(out/'reference.jpg',refvis)
 (out/'template.json').write_text(json.dumps(dict(status='provisional_not_ground_truth',reference=str(reference.relative_to(root)),working_height=2000,original_size=original,bubbles=bubbles,markers=rm.tolist()),ensure_ascii=False,indent=2))
 manifest=[]
 for p in sorted((root/'dataset').glob('*/*.png')):
  manifest.append(dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p),physical_form_id=None))
 (out/'dataset_manifest.json').write_text(json.dumps(manifest,indent=2))
 paths=sorted((root/'dataset').glob('*/*.png')) if args.all else [root/f'dataset/{g}/001.png' for g in GROUPS]
 paths=[reference]+[p for p in paths if p!=reference]
 records=[];cards=[]
 for path in paths:
  im,size=load(path);cm=markers(im);name=path.parent.name+'_'+path.stem
  record=dict(image=str(path.relative_to(root)),original_size=size,detected_markers=len(cm),status='failed',methods={})
  if len(cm)<4:record['reason']='fewer than 4 candidates';records.append(record);continue
  cost=np.linalg.norm((rm/np.array(ref.shape[1::-1]))[:,None,:]-(cm/np.array(im.shape[1::-1]))[None,:,:],axis=2)
  ri,ci=linear_sum_assignment(cost);keep=cost[ri,ci]<0.06;ri,ci=ri[keep],ci[keep]
  record['matched_markers']=len(ri);record['pairs']=[dict(reference_id=int(r),candidate_id=int(c),normalized_distance=float(cost[r,c])) for r,c in zip(ri,ci)]
  if len(ri)<4:record['reason']='fewer than 4 gated matches';records.append(record);continue
  # Explicit identity control prevents fitting noise from obscuring template QA.
  cv2.setRNGSeed(42)
  for method,flag in [('homography_all',0),('homography_ransac',cv2.RANSAC)]:
   H,inliers=cv2.findHomography(rm[ri],cm[ci],flag,3.0)
   if H is None or not np.isfinite(H).all():record['methods'][method]={'status':'failed'};continue
   pred=cv2.perspectiveTransform(pts[:,None,:],H).reshape(-1,2)
   mp=cv2.perspectiveTransform(rm[ri,None,:],H).reshape(-1,2)
   residual=np.linalg.norm(mp-cm[ci],axis=1)
   hull=cv2.convexHull(rm[ri][inliers.ravel().astype(bool)])
   outside={s:sum(cv2.pointPolygonTest(hull,(float(p[0]),float(p[1])),False)<0 for p,r in zip(pts,bubbles) if r['subject']==s) for s in BLOCKS}
   warped=cv2.warpPerspective(im,np.linalg.inv(H),(ref.shape[1],ref.shape[0]),borderValue=(255,255,255))
   overlay=draw(im,pred,cm)
   flags=np.zeros(len(cm),dtype=bool);flags[ci]=inliers.ravel().astype(bool)
   overlay=draw(im,pred,cm,flags)
   cv2.polylines(overlay,[cv2.convexHull(cm[ci][inliers.ravel().astype(bool)]).astype(np.int32)],True,(0,180,255),2)
   filename=f'{name}_{method}.jpg';save(out/filename,overlay)
   strips=[]
   for y in [615,1150,1695]:
    left=draw(ref,pts,rm)[y-55:y+55,705:1380]
    right=draw(warped,pts,np.empty((0,2)))[y-55:y+55,705:1380]
    for label,strip in [('REFERENCE',left),('ALIGNED SAMPLE',right)]:
     band=np.full((24,strip.shape[1],3),255,np.uint8)
     cv2.putText(band,label,(8,17),cv2.FONT_HERSHEY_SIMPLEX,.5,(30,30,30),1)
     strips.extend([band,strip])
   crops=np.vstack(strips);cropfile=f'{name}_{method}_details.jpg';save(out/cropfile,crops)
   record['methods'][method]=dict(status='diagnostic_only',inliers=int(inliers.sum()),H=H.tolist(),marker_residual_px=residual.tolist(),median_marker_residual_px=float(np.median(residual)),p95_marker_residual_px=float(np.percentile(residual,95)),bubbles_outside_inlier_hull=outside,bubble_ground_truth_error=None,overlay=filename,details=cropfile)
   cards.append(f'<article><h3>{html.escape(name)} / {method}</h3><p>{len(cm)} aday; {len(ri)} eşleşme; {int(inliers.sum())} inlier. Marker medyan hata: {np.median(residual):.2f} px. Bu, balon doğruluğu değildir.</p><p>Her çiftte üst referans, alt hizalanmış örnek. Sırasıyla üst / orta / alt satırlar. Soldan sağa Türkçe, Sosyal, Matematik, Fen.</p><a href="{filename}">Tüm görüntü ve markerlar</a><img loading="lazy" src="{cropfile}"></article>')
  record['status']='diagnostic_only';records.append(record);print(name,len(cm),'markers',len(ri),'matches',flush=True)
 summary=dict(version=VERSION,commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),opencv=cv2.__version__,reference=str(reference.relative_to(root)),working_height=2000,match_gate_normalized=0.06,ransac_threshold_px=3.0,seed=42,reference_marker_count=len(rm),template_bubbles=len(bubbles),contour_refined=sum(r['contour_refined'] for r in bubbles),ground_truth_available=False,source_sha256=sha(Path(__file__)),results=records)
 (out/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 page='''<!doctype html><html lang="tr"><meta charset="utf-8"><title>Baykuş — E0 kenar hizalama</title><style>body{font:17px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;background:#f4f5f7;color:#172331}article{background:white;padding:24px;margin:24px 0;border-radius:12px}img{width:100%;margin-top:16px}a{color:#176ca4}p{line-height:1.6}</style><h1>Baykuş — E0: Kenar hizalama</h1><p>Referans: flat_front/004.png. Yalnız geometrik teşhis; cevap okuma yapılmadı. Yeşil halkalar şablon merkezleri. Referanstaki kırmızı halkalar konturla doğrulanamayan merkezlerdir. Sarı çokgen marker destek alanıdır; dışı ekstrapolasyondur. Şablon geçicidir; elle doğrulanmış ground truth değildir. Farklı formlardaki dolu şıkların değişmesi hata sayılmaz.</p><p>İki yöntem aynı marker eşleşmelerini kullanır. RANSAC dışında kalan marker gerçek eğrilik de gösterebilir. Marker hatası, modelin uydurulduğu noktalardaki hatadır; bağımsız başarı ölçütü değildir. Tüm ölçüler 2000 px yüksekliğindeki görüntüdedir.</p><p><a href="reference.jpg">Referansı ve geçici balon şablonunu aç</a> · <a href="results.json">Sayısal kayıt</a> · <a href="template.json">Şablon</a></p>'''+''.join(cards)+'</html>'
 (out/'index.html').write_text(page)
 print(json.dumps({k:summary[k] for k in ['reference_marker_count','template_bubbles','contour_refined']},ensure_ascii=False))

if __name__=='__main__':main()
