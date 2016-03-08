from clipping import main as clip
from os import listdir,walk,system,chdir,curdir
from os.path import join,isdir,exists,abspath,dirname,normpath
import geojson

from utils import fmakedirs as makedirs, fcp as cp

def get_geojson(path):
    save = abspath(curdir)
    chdir(path)
    ret = []
    for root,dirs,files in walk("."):
        ret += [normpath(join(root,x)) for x in files if x.endswith("geojson")]
    chdir(save)        
    return ret

def run(cmd,path,zoom,base,features,test,code):
    ext = ".tmp"
    if cmd == "add": # extract geojson from file
        clip(zoom,path,base,features,test)
    elif cmd == "update":
        code = clip(zoom,path,base+ext,features,test)        
        diffs = get_diffs(base,base+ext,code)
        print "CHANGED:",len(diffs) 
        merge_diffs(base,base+ext,code,diffs,path)
    else:
        assert(cmd == "merge")
        merge(path,base,features,test=test)

def get_diffs(base1,base2,code):
    old = get_geojson(join(base1,code))
    tmp = get_geojson(join(base2,code))

    changed = []
    for x in tmp:
        xtmp = join(base2,code,x)
        xold = join(base1,code,x)
        
        if x in old:
            if open(xtmp).read() != open(xold).read():
                changed.append(x)
                cp(xtmp,xold)
        else:
            changed.append(x)
            cp(xtmp,xold)
    return changed

def merge_diffs(base1,base2,code,diffs,out):
    M = {}
    for x in diffs:
        for c in dirs: #code 
            path = join(base,c,x)
            if exists(path):
                M.setdefault(x,[]).append(c)
    merge_json(M,base,out)
        
def merge(out,base,features,prefix="M_",test=False):
    dirs = [x
            for x in listdir(base)
            if isdir(join(base,x)) and not x.startswith(prefix)]
    M = {}
    print("TEST",test)

    for x in dirs: #code 
        path = join(base,x)
        for y in get_geojson(path):
            print("XY",x,y)
            if test:
                ys = y.split("/")
                newy = "/".join(ys[1:])
                newx = x+"/"+ys[0]
                print("NEWXY",newx,newy)
                M.setdefault(newy,[]).append(newx)
            else:
                M.setdefault(y,[]).append(x)
    merge_json(M,base,prefix+out)
        
def merge_json(M,base,out):
    for k in M:
        new = join(base,out,k)
        makedirs(dirname(new))
        if len(M[k]) == 1:
            old = join(base,M[k][0],k)
            cp(old,new)
        else:
            gs = [(x,geojson.load(open(join(base,x,k)))) for x in M[k]]
            x0,g = gs[0]
            for x,h in gs[1:]:
                print "merging",x0,x
                g["features"] += h["features"]
            f = open(new,"w")
            geojson.dump(g,f)
            f.close()

def help(name,ret):
    print "usage:"
    print name,"[-h]"
    print "    this help message"
    print name,"app path | update path | merge path [-b base] [-c code] [-f features] [-z zoom]"
    print "where"
    print "path    => path to gml/shp data for add/update; mergedir otherwise "
    print "base    => path to root directory                            (default '.')"
    print "code    => date code (only needed for irregular filenames)"
    print "feature => comma-separated list of features, e.g AdmArea,... (default all)"
    print "zoom    => zoom factor                                       (default 18)"
    exit(ret)

if __name__ == "__main__":
    from sys import argv,exit

    base = "."
    code = None
    features = []
    zoom = 18
    test = False
    
    n = len(argv)
    if n == 1:
        help(argv[0],1)
    elif n == 2 and argv[1] == "-h":
        help(argv[0],0)
    else:
        cmd = argv[1]

    try:
        cmd = argv[1]
        path = argv[2]        
        assert(cmd in ("add","update","merge"))
        
        for i,opt in enumerate(argv[3:]):
            if opt == "-b":
                base = argv[3+i+1]
            elif opt == "-c":
                code = argv[3+i+1]
            elif opt == "-f":
                features = argv[3+i+1].split(",")
            elif opt == "-z":
                zoom = int(argv[3+i+1])
            elif opt == "-t":
                test = True
        if exists(base):
            assert(isdir(base))
        if cmd == "merge" and not exists(path):
            makedirs(path)
        assert(path is None or exists(path))
        assert(10 <= zoom and zoom <= 24)
    except:
        raise
        help(argv[0],1)
        
    run(cmd=cmd,path=path,zoom=zoom,code=code,base=base,features=features,test=test)

