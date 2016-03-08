from os import makedirs
from os.path import exists,dirname

def fmakedirs(d):
    if not exists(d):
        makedirs(d)

def fcp(a,b):
    fmakedirs(dirname(b))
    f=open(b,"w")
    f.write(open(a).read())
    f.close()
