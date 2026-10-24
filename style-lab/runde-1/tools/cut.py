import sys, glob, os
from rembg import remove, new_session
from PIL import Image
model, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
s = new_session(model)
fs = sorted(glob.glob(src+'/*.png'))
step = int(sys.argv[4]) if len(sys.argv)>4 else 1
for f in fs[::step]:
    im = Image.open(f).convert('RGB')
    out = remove(im, session=s, alpha_matting=False)
    out.save(os.path.join(dst, os.path.basename(f)))
print('done', len(fs[::step]))
