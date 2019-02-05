from os.path import join,exists,basename,abspath,normpath
from os import listdir,system,environ,unlink
from lxml import etree as ET
from random import randint
import json
import geojson
import shapely
import codecs
from shapely.geometry import mapping, shape
from shapely.validation import explain_validity
from more_itertools import chunked
import zipfile as zf
from collections import OrderedDict as OD
from rtree import index
from rtree.core import RTreeError
from sys import exit
from fixpoly import fix_mpoly, fix_poly, fix_lr, fix_ls

from utils import u_rmall as rmall,u_tmpdir as tmpdir,u_getfiles as getfiles

__Enc__ = ('utf-8', 'euc_jp', 'euc_jis_2004', 'euc_jisx0213',
        'shift_jis', 'shift_jis_2004','shift_jisx0213',
        'iso2022jp', 'iso2022_jp_1', 'iso2022_jp_2', 'iso2022_jp_3',
        'iso2022_jp_ext','latin_1', 'ascii')

__dtype__ = ('AdmArea','AdmBdry','AdmPt','Anno','BldA','BldL','BldSbl','Cntr',
        'CommBdry','CommPt','Cstline','ElevPt','GCP','LUSbl','Monument','PwPlnt',
        'PwTrnsmL','RailCL','RailTrCL','RdCL','RdCompt','RdEdg','RTwr','RvrCL',
        'SBAPt','SBBdry','SpcfArea','TrfStrct','TrfTnnEnt','VegeClassL','VLine',
        'WA','WL','WoodRes','WStrA','WStrL','DEM','dem')

__ftype__ = ('alti')

__itype__ = ('altiAcc','dimension')

class loader:
    def __init__(self,path,shpfile=False):
        self.path = normpath(abspath(path))
        self.gobj = {}
        self.code = None

        if shpfile:
            dpath = tmpdir("tmp",basename(path).split(".")[0])
            if path.lower().endswith(".zip"):
                self.get_code()
                system("cd " + dpath + "; unzip " + self.path)
            else:
                assert(self.path.lower().endswith(".shp"))
                system("cd " + dpath + "; cp " + self.path[:-4]+"*" + " .")
            shpfiles = getfiles(dpath,".shp")
            for x in shpfiles:
                p = join(dpath,x)
                geop = p[:-3] + "geojson"
                if "SHAPE_ENCODING" not in environ or not environ["SHAPE_ENCODING"]:
                    environ["SHAPE_ENCODING"] = "cp932"
                cmd = "ogr2ogr -f GeoJSON " + geop + " " + p
                print "running",cmd
                system(cmd)
                bs = basename(p).split("-")
                if len(bs) > 4:
                    f = bs[3]
                else:
                    f = 'shapefile'

                if self.code is None:
                    if len(bs) > 4 and len(bs[3]) in (4,6,8) and set(bs[3]) in set("0123456789"):
                        self.code = ['code',bs[3]]
                    else:
                        self.code = ['corner', self.get_corner(p)]
                elif self.code[0] == 'corner':
                    self.code[1] = self.get_corner(p,self.code[1])

                fgeo = open(geop,'r')
                data, enc = self.detect_enc(fgeo.read())

                geo = geojson.load(codecs.open(geop,encoding=enc))
                self.gobj.setdefault(f,[]).extend(geo["features"])
            rmall(dpath)
        else:
            self.file_open()
            self.get_code()

    def get_corner(self,path,o_code=None):
        s = str(randint(1,999999999999))
        tmp = "log_" + s
        cmd = "ogrinfo -al -so " + path + "> " + tmp
        system(cmd)
        for l in open(tmp):
            if l.startswith('Extent:'):
                for x in '()-,': l = l.replace(x,'')
                l = l.split()
                assert(len(l) == 5)
                code = [[float(l[1]),float(l[3])],[float(l[2]),float(l[4])]]
                break
        unlink(tmp)

        if not o_code is None:
            code[0][0] = min(code[0][0],o_code[0][0])
            code[1][0] = min(code[1][0],o_code[1][0])
            code[0][1] = max(code[0][1],o_code[0][1])
            code[1][1] = max(code[1][1],o_code[1][1])

        return code

    def get_code(self,fname=None):
        if fname is None:
            fname = self.path
        f = basename(fname).split('-')
        if len(f) > 3:
            self.code = ['code',f[2]]

    def file_open(self):
        if self.path.endswith('.zip'):
            self.zip_file_open()
        elif self.path.endswith('.xml'):
            self.xml_file_open()

    def detect_enc(self,data):
        for enc in __Enc__:
            try:
                data = data.decode(enc)
                encode = enc
                break
            except:
                pass
        if isinstance(data,unicode):
            return data,encode
        else:
            raise EncodingError

    def xml_file_open(self):
        print 'Start file Load..' + self.path
        f = open(self.path,'r')
        data, enc = self.detect_enc(f.read())
        self.load(data,enc,self.chk_dtype(self.path))

    def zip_file_open(self):
        zfile = zf.ZipFile(self.path)
        for l in zfile.namelist():
            if not self.chk_dtype(l) == 'NULL':
                print self.chk_dtype(l)
                f = zfile.open(l)
                print 'Start file Load..' + l
                data, enc = self.detect_enc(f.read())
                print("DETECTED:",l,enc)
                self.load(data,enc,self.chk_dtype(l))

    def clip_tag(self,str):
        if not '}' in str:
            return str
        else:
            return str[str.find('}')+1:].strip()

    def ns_clean(self):
        n_dic = {}
        for k,v in self.ns.items():
            if not k is None:
                n_dic[k]=v
        self.ns = n_dic

    def chk_types(self,obj):
        if 'properties' in obj:
            for k,v in obj['properties'].items():
                if k in __ftype__:
                    try:
                        obj['properties'][k] = float(v)
                    except:
                        obj['properties'][k] += '(Real)'
                if k in __itype__:
                    try:
                        obj['properties'][k] = int(v)
                    except:
                        obj['properties'][k] += '(int)'
        else:
            for i in range(len(obj)):
                obj[i] = self.chk_types(obj[i])
        return obj


    def load(self,data,enc,dtype):
        parser = ET.XMLParser(ns_clean=True,recover=True,encoding=enc,huge_tree=True)
        root = ET.fromstring(data.encode(enc),parser=parser)
        self.ns = root.nsmap
        self.ns_clean()
        l_obj = []
        for child in root:
            for k,v in child.attrib.items():
                if 'id' == k[-2:]:
                    if dtype == "DEM" or dtype=="dem":
                        l_obj = self.parse_dem_obj(child)
                    else:
                        obj = self.parse_obj(child,dtype)
                        if isinstance(obj,list):
                            l_obj += obj
                        else:
                            l_obj.append(obj)
        if dtype in self.gobj:
            self.gobj[dtype].extend(l_obj)
        else:
            self.gobj[dtype] = l_obj

    def parse_dem_obj(self,obj):
        dic = OD()
        dic['type'] = 'Feature'
        pro = OD()
        pro['class'] = 'DEMPt'
        for child in obj:
            ctag = self.clip_tag(child.tag)
            if ctag == 'coverage':
                vs = child.find('.//gml:tupleList',self.ns).text.split()
                low_xy = child.find('.//gml:low',self.ns).text.split()
                high_xy = child.find('.//gml:high',self.ns).text.split()
                min_xy = child.find('.//gml:lowerCorner',self.ns).text.split()
                max_xy = child.find('.//gml:upperCorner',self.ns).text.split()
                order = child.find('.//gml:sequenceRule',self.ns).attrib["order"] 
                sp = tuple(int(x) for x in child.find('.//gml:startPoint',self.ns).text.split())
                
                n_low = [int(x) for x in low_xy]
                n_high = [int(x) for x in high_xy]
                ns = [x-y+1 for x,y in zip(n_high,n_low)]
                mins = [float(x) for x in min_xy]
                maxs = [float(x) for x in max_xy]
                
                orders = (order[0],order[2]) #Get order

                if order == "+x-y":
                    if sp != (0,0):
                        offset = sp[0] + ns[0] * sp[1] 
                        vs = offset * [u"データなし,-9999."] + vs
                else:
                    xr = range(ns[0]) if "+x" in order else range(ns[0]-1,-1,-1)
                    yr = range(ns[1]) if "-y" in order else range(ns[1]-1,-1,-1)
                    newvs = ns[0] * ns[1] * [u"データなし,-9999."]
                    started = False
                    vidx = 0
                    for x in xr:
                        for y in yr:
                            if not started and x == sp[0] and y == sp[1]:
                                started = True
                            if started:
                                newvs[x+ns[0]*y] = vs[vidx]
                                vidx += 1
            else:
                i = u''
                for l in child.itertext():
                    i += l
        ret = []
        delta = [maxs[0]-mins[0],maxs[1]-mins[1]]
        num = 0
        nvs = len(vs)
        for col in range(ns[1]):
            for row in range(ns[0]):
                new = dict(dic)
                pro2 = dict(pro)
                if orders[0] == "+":
                    x = mins[1] + (float(row)/float(ns[0])*float(delta[1]))
                else:
                    x = maxs[1] - (float(row)/float(ns[0])*float(delta[1]))
                if orders[1] == '+':
                    y = mins[0] + (float(col)/float(ns[1]))*float(delta[0])
                else:
                    y = maxs[0] - (float(col)/float(ns[1]))*float(delta[0])
                new['geometry'] = OD()
                new['geometry']['type'] = 'Point'
                new['geometry']['coordinates'] = (x,y)
                pro2['type'],pro2['alti'] = vs[num].split(',') if num < nvs else (u"データなし","-9999.")
                new['properties'] = pro2
                ret.append(new)
                num += 1
        ret = self.chk_types(ret)
        return ret

    def parse_obj(self,obj,dtype):
        dic = OD((('type','Feature'),('geometry',OD()),('properties',OD())))
        dic['properties']['class'] = dtype
        for child in obj:
            ctag = self.clip_tag(child.tag)
            if ctag in ['pos','area','loc']:
                if ctag == 'area':
                    dic['geometry']['type'] = 'Polygon'
                    dic['geometry']['coordinates'] = self.get_polygon_coord(child)
                else:
                    if ctag == 'pos':
                        dic['geometry']['type'] = 'Point'
                    elif ctag == 'loc':
                        dic['geometry']['type'] = 'LineString'
                    i = ""
                    for l in child.itertext():
                        i += l
                    l = list(chunked(i.strip().split(),2))
                    i = [[float(xy[1]),float(xy[0])] for xy in l]

                    if len(i) == 1:
                        dic['geometry']['coordinates'] = i[0]
                    else:
                        dic['geometry']['coordinates'] = i
            elif child.text is not None and not child.text.strip() == '':
                dic['properties'][ctag]=child.text
            else:
                i = ''
                for l in child.itertext():
                    i += l
                dic['properties'][ctag]=i.strip()
        dic = self.chk_types(dic)
        return dic

    def get_polygon_coord(self,obj):
        #get exterior coords
        coord = []
        i = ""
        ext = obj.find('.//gml:exterior',self.ns)
        for l in ext.itertext():
            i += l
        l = list(chunked(i.strip().split(),2))
        coord.append([[float(xy[1]),float(xy[0])] for xy in l])
        #get interior coords
        inte = obj.findall('.//gml:interior',self.ns)
        if not inte:
            return coord
        else:
            for i in inte:
                j = ""
                for l in i.itertext():
                    j += l
                l = list(chunked(j.strip().split(),2))
                coord.append([[float(xy[1]),float(xy[0])] for xy in l])
        return coord

    def chk_dtype(self,path):
        fname = basename(path)
        for i in __dtype__:
            if i in fname:
                return i
        return 'NULL'

    def rindex(self,feature,mdic,rtree=False,shpfile=True):
        val = self.gobj[feature]
        if rtree:
            idx = index.Index()
        for i,y in enumerate(val):
            k = "geometry"
            g = y[k]
            gc = g["coordinates"]
            if y[k]["type"] == "Polygon":
                if shpfile:
                    try:
                        if len(gc) == 1:
                            s = shapely.geometry.Polygon(gc[0])
                        else:
                            s = shapely.geometry.Polygon(gc[0],gc[1:])
                    except:
                        print "Y",y
                        print "GC",gc
                        raise

                else:
                    coords = [tuple(w) for w in gc]
                    # need to deal with holes properly
                    ps = [[]]
                    for x in coords:
                        t = tuple(x)
                        if ps[-1] and t == ps[-1][0]:
                            ps[-1].append(t)
                            assert(len(ps[-1]) > 2)
                            ps.append([])
                        else:
                            ps[-1].append(t)
                    if ps[-1] != []:
                        print "Y",y
                        print "PS",ps
                    assert(not ps[-1])
                    ps.pop()
                    if len(ps) > 1:
                        s = shapely.geometry.Polygon(ps[0],ps[1:])
                    else:
                        s = shapely.geometry.Polygon(ps[0])
            elif y[k]["type"] == "LineString":
                coords = [tuple(w) for w in gc]
                s = shapely.geometry.LineString(coords)
            elif y[k]["type"] == "Point":
                s = shapely.geometry.Point(tuple(gc))
            else:
                if not shpfile:
                    raise NotImplementedError(y[k]["type"])
                if y[k]["type"] == "MultiPoint":
                    
                    ss = []
                    for x in gc:
                        stmp = shapely.geometry.Point(tuple(x))
                        ss.append(stmp)
                    s = shapely.geometry.MultiPoint(ss)
                elif y[k]["type"] == "MultiLineString":
                    ss = []
                    for x in gc:
                        coords =  [tuple(w) for w in x]
                        stmp = shapely.geometry.LineString(coords)
                        ss.append(stmp)
                    s = shapely.geometry.MultiLineString(ss)
                elif y[k]["type"] == "MultiPolygon":
                    ss = []
                    for x in gc:
                        if len(x) == 1:
                            stmp = shapely.geometry.Polygon(x[0])
                        else:
                            stmp = shapely.geometry.Polygon(x[0],x[1:])
                        ss.append(stmp)
                    s = shapely.geometry.MultiPolygon(ss)
                else:
                    raise NotImplementedError(y[k]["type"])
                
            if not s.is_valid:
                if y[k]["type"] == "Polygon": # fix invalid polygons
                    s = fix_poly(s,mdic)                   
                elif y[k]["type"] == "LineString":
                    s = fix_ls(s,mdic)
                elif y[k]["type"] == "MultiPolygon": # fix invalid polygons
                    s = fix_mpoly(s,mdic)
                else:
                    raise ValueError(s.wkt)

            if s.is_valid:
                y[k]["shapely"] = s
                if rtree:
                    try:
                        idx.insert(i,s.bounds)
                    except RTreeError:
                        pass
            else:
                print("STILL INVALID")                
                            
        if rtree:
            return idx

    def extract2(self,bounds,vals,idx):
        box = shapely.geometry.box(*bounds)
        ret = []
        for i in idx.intersection(bounds):
            y = vals[i]
            s = y["geometry"]["shapely"]
            try:
                if not box.disjoint(s):
                    res = box.intersection(s)
                    geo = mapping(res) 
                    if 'geometries' in geo:
                        for x in geo['geometries']:
                            newy = OD(y)
                            newy[u'geometry'] = x
                            newy["properties"] = y["properties"]
                            ret.append(newy)
                    else:
                        newy = OD(y)
                        newy[u'geometry'] = geo
                        ret.append(newy)
            except:
                print("YYY",y["geometry"])
                raise
        return ret

    def extract3(self,bxs,vals):
        ret = {}

        for y in vals:
            s = y["geometry"]["shapely"]
            tmp = {}
            for xid,yid,box in bxs:
                try:
                    if not box.disjoint(s):
                        tmp[xid,yid] = box.intersection(s)
                except:
                    print("SSS",s.type)
                    print("SSS",s.boundary.coords)
                    print("YYY",y["geometry"])
                    raise
            for (xid,yid) in tmp.keys():
                newy = OD(y)
                newy['geometry'] = mapping(tmp[xid,yid])
                ret.setdefault((xid,yid),[]).append(newy)
        return ret
