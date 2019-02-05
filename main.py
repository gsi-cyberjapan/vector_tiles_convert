from clipping import main as clip
from os import listdir,walk,system,chdir,curdir,rmdir,getpid
from os.path import join,isdir,exists,abspath,dirname,normpath
import geojson
import codecs

from utils import u_makedirs as makedirs, u_cp as cp, u_rm as rm, u_getfiles as getfiles, u_rmall as rmall

def get_geojson(path,zoom=None):
    ret = getfiles(path,".geojson")
    if zoom is not None:
        ret = [x
               for x in ret
               if x.split("/")[1:2] == [zoom]]
    return ret

def run(cmd,path,zoom,base,features,test,code,shpfile,mergedir):
    if cmd == "add": 
        clip(zoom,path,base,features,test,code,shpfile)
    elif cmd == "update":
        ext = ".tmp"+str(getpid())
        code = clip(zoom,path,base+ext,features,test,code,shpfile)        
        diffs = get_diffs(base,base+ext,code[1],zoom)
        rmall(base+ext)
        rmdir(base+ext)
        print "CHANGED:",len(diffs) 
        merge_diffs(base,mergedir,diffs)
    else:
        assert(cmd == "merge")
        merge(base,mergedir,zoom)

def get_diffs(base1,base2,code,zoom):
    old = get_geojson(join(base1,code),zoom)
    tmp = get_geojson(join(base2,code),zoom)

    changed = []
    for x in tmp:
        xtmp = join(base2,code,x)
        xold = join(base1,code,x)
        
        if x in old:
            if codecs.open(xtmp,encoding="utf8").read() != codecs.open(xold,encoding="utf8").read():
                changed.append(x)
                cp(xtmp,xold)
        else:
            changed.append(x)
            cp(xtmp,xold)
    for x in old:
        if x not in tmp:
            xold = join(base1,code,x)
            changed.append(x)
            rm(xold)
    return changed

def merge_diffs(base,out,diffs,prefix="M_"):
    dirs = [x
            for x in listdir(base)
            if isdir(join(base,x)) and not x.startswith(prefix)]
    M = {}
    for x in diffs:
        M[x] = []
        for code in dirs: 
            path = join(base,code,x)
            if exists(path):
                M[x].append(code)
    merge_json(M,base,prefix+out)
        
def merge(base,out,zoom,prefix="M_"):
    dirs = [x
            for x in listdir(base)
            if isdir(join(base,x)) and not x.startswith(prefix)]
    M = {}
    for code in dirs: 
        path = join(base,code)
        for y in get_geojson(path,zoom):
            M.setdefault(y,[]).append(code)
    merge_json(M,base,prefix+out)
        
def merge_json(M,base,out):
    print "BO",base,out
    if True:
        NEWM = {}
        check = set()
        for path in M:
            if not M[path]:
                ps = path.split("/")
                newpath = "/".join(ps[1:])                
                check.add(newpath)
            for code in M[path]:
                ps = path.split("/")
                newpath = "/".join(ps[1:])
                newcode = code+"/"+ps[0]
                NEWM.setdefault(newpath,[]).append(newcode)
        for x in check:
            if x not in NEWM:
                NEWM[x] = []
        M = NEWM
            
    for k in M:
        new = join(base,out,k)
        makedirs(dirname(new))
        if len(M[k]) == 0:
            rm(new)
        elif len(M[k]) == 1:
            old = join(base,M[k][0],k)
            cp(old,new)
        else:
            gs = [(x,geojson.load(codecs.open(join(base,x,k),encoding="utf8"))) for x in M[k]]
            x0,g = gs[0]
            for x,h in gs[1:]:
                g["features"] += h["features"]
            f = codecs.open(new,"w",encoding="utf8")
            geojson.dump(g,f,ensure_ascii=False)
            f.close()

def help(name,ret):
    print "usage:"
    print name,"[-h]"
    print "    this help message"
    print name,"(add path | update path [-m mergedir] | merge [-m mergedir]) [-b base] [-c code] [-f features] [-z zoom] [-s]"
    print "where"
    print "path     => path to gml/shp data for add/update; mergedir otherwise "
    print "base     => path to root directory                            (default '.')"
    print "mergedir => mergedir (used by merge and update)"
    print "code     => date code (only needed for irregular filenames)"
    print "feature  => comma-separated list of features, e.g AdmArea,... (default all)"
    print "zoom     => zoom factor                                       (default 18)"
    print "use option '-s' when adding shapefiles"
    exit(ret)

if __name__ == "__main__":
    from sys import argv,exit

    base = "."
    code = None
    features = []
    zoom = 18
    test = False
    shpfile = False
    mergedir = None
    path = None
    
    n = len(argv)
    if n == 1:
        help(argv[0],1)
    elif n == 2 and argv[1] == "-h":
        help(argv[0],0)
    else:
        cmd = argv[1]

    try:
        cmd = argv[1]
        assert(cmd in ("add","update","merge"))
            
        if cmd == "merge":
            off = 0
        else:
            off = 1        
            path = argv[2]        

        
        for i,opt in enumerate(argv[2+off:]):
            if opt == "-b":
                base = argv[2+off+i+1]
            elif opt == "-m":
                mergedir = argv[2+off+i+1]
            elif opt == "-c":                
                code = argv[2+off+i+1]
            elif opt == "-f":
                features = argv[2+off+i+1].split(",")
            elif opt == "-z":
                zoom = int(argv[2+off+i+1])
            elif opt == "-t":
                test = True
            elif opt == "-s":
                shpfile = True

        if exists(base):
            assert(isdir(base))

        if cmd != "add":
            assert(mergedir is not None)
            
        assert(path is None or exists(path))
        assert(1 <= zoom and zoom <= 24)

    except:
        raise
        help(argv[0],1)
        
    run(cmd=cmd,path=path,zoom=str(zoom),code=code,base=base,features=features,test=test,shpfile=shpfile,mergedir=mergedir)

