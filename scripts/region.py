"""(Used with handcut.py.) Page region around an instance, with block-coordinate ticks and component boxes numbered.
Usage: python -I -X utf8 scripts/region.py <config> <copy> <instance file> <out.png> [left right up down]"""
import sys, json, cv2, numpy as np
C=json.load(open(sys.argv[1],encoding='utf-8')); p=sys.argv[2]; nm=C['name']
J=json.load(open(f'work/{nm}_al_p{p}/instances.json',encoding='utf-8'))
it=next(i for i in J['instances'] if i['file']==sys.argv[3])
L,R,U,D=(list(map(int,sys.argv[5:9]))+[350,350,90,60])[:4] if len(sys.argv)>=9 else (350,350,90,60)
bx=C['boxes'][p]; g=cv2.imread(C['images'][p],0)[bx[1]:bx[3],bx[0]:bx[2]]
X0,X1,Y0,Y1=max(0,it['x0']-L),min(g.shape[1],it['x1']+R),max(0,it['y0']-U),min(g.shape[0],it['y1']+D)
bw=(g<J['otsu']).astype(np.uint8); n,lab,st,_=cv2.connectedComponentsWithStats(bw,8)
r=cv2.cvtColor(g[Y0:Y1,X0:X1],cv2.COLOR_GRAY2BGR); r=cv2.resize(r,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
for k in range(1,n):
    x,y,w,h,a=st[k]
    if a<25 or x+w<X0 or x>X1 or y+h<Y0 or y>Y1: continue
    cv2.rectangle(r,(2*(x-X0),2*(y-Y0)),(2*(x+w-X0),2*(y+h-Y0)),(0,160,0),1)
    cv2.putText(r,str(k),(2*(x-X0),2*(y-Y0)-3),cv2.FONT_HERSHEY_SIMPLEX,0.45,(200,0,0),1)
cv2.rectangle(r,(2*(it['x0']-X0),2*(it['y0']-Y0)),(2*(it['x1']-X0),2*(it['y1']-Y0)),(0,0,255),1)
cv2.imwrite(sys.argv[4],r); print(sys.argv[4],it['ch'],it['line'],it['word'],it['pos'])
