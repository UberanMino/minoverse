import glob, numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
B='build/clips/assets/'
U='/root/.claude/uploads/d0b0dcbb-1da6-5514-bbe7-67ef6d35f634/'
def clean(im, keep=1):
    a=np.array(im); al=a[...,3]
    lab,n=ndimage.label(al>40)
    if n>1:
        sizes=ndimage.sum(np.ones_like(al),lab,range(1,n+1))
        order=np.argsort(sizes)[::-1][:keep]+1
        mask=np.isin(lab,order)
        mask=ndimage.binary_dilation(mask,iterations=2)
        al=np.where(mask,al,0)
    a[...,3]=al
    return Image.fromarray(a)
# Mino Man anchor
mm=Image.open(U+'6614edf3-news_mino_man.png').convert('RGBA')
mm=clean(mm)
bb=mm.getbbox(); print('mm bbox',bb)
mm.crop(bb).resize(((bb[2]-bb[0])*2//3,(bb[3]-bb[1])*2//3),Image.LANCZOS).save(B+'mm_anchor.webp',quality=82)
# head: cut at collar y~1430 with fade
h=mm.copy(); a=np.array(h).astype(float)
ys=np.arange(a.shape[0])[:,None]
fade=np.clip((1460-ys)/40,0,1)
a[...,3]*=fade
head=Image.fromarray(a.astype(np.uint8)); hb=head.getbbox(); print('head',hb)
head=head.crop(hb); head=head.resize((head.width*3//5,head.height*3//5),Image.LANCZOS); head.save(B+'mm_head.webp',quality=85)
# sprite sheets
def sheet(files,out,H,cols):
    ims=[clean(Image.open(f).convert('RGBA')) for f in files]
    boxes=[i.getbbox() for i in ims]
    x0=min(b[0] for b in boxes); y0=min(b[1] for b in boxes); x1=max(b[2] for b in boxes); y1=max(b[3] for b in boxes)
    ims=[i.crop((x0,y0,x1,y1)) for i in ims]
    W=int((x1-x0)*H/(y1-y0)); rows=(len(ims)+cols-1)//cols
    S=Image.new('RGBA',(W*cols,H*rows),(0,0,0,0))
    for k,i in enumerate(ims): S.paste(i.resize((W,H),Image.LANCZOS),((k%cols)*W,(k//cols)*H))
    S.save(out,quality=80,method=6); print(out,W,H,len(ims),cols,rows)
    return W
cg=sorted(glob.glob('cg/cut/*.png'))[:40]
sheet(cg,B+'cg_dance.webp',420,8)
mmc=sorted(glob.glob('mm/cut/*.png'))[:30]
sheet(mmc,B+'mm_climb.webp',480,6)
# chicken guy head from frame 30
f=clean(Image.open(sorted(glob.glob('cg/cut/*.png'))[30]).convert('RGBA'))
f.save('cg_frame30.png')
