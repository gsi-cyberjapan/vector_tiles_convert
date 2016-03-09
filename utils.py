from os import makedirs,rmdir,walk,remove,chdir,curdir
from os.path import exists,dirname,join,normpath,abspath

def u_makedirs(d):
    if not exists(d):
        makedirs(d)

def u_cp(a,b):
    u_makedirs(dirname(b))
    f=open(b,"w")
    f.write(open(a).read())
    f.close()

def u_rm(x):
    if exists(d):
        remove(x)

def u_rmall(path):
    rm = []
    drm = []
    for root,dirs,files in walk(path):
        rm += [normpath(join(root,x)) for x in files]
        drm += [normpath(join(root,x)) for x in dirs]
    for x in rm:
        remove(x)
    for x in sorted(drm,key=lambda x:-len(x)):
        rmdir(x)

def u_tmpdir(path,name):
    n = 0
    while exists(join(path,name,str(n).zfill(3))):
        n += 1
    dpath = join(path,name,str(n).zfill(3))
    u_makedirs(dpath)
    return dpath

def u_getfiles(path,ext):
    save = abspath(curdir)
    chdir(path)
    ret = []
    for root,dirs,files in walk("."):
        ret += [normpath(join(root,x)) for x in files if x.endswith(ext)]
    chdir(save)
    return ret
