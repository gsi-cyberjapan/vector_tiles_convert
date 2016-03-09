from os.path import join,exists,basename,abspath,normpath
from os import listdir,system
from lxml import etree as ET
import json
import geojson
import shapely
import codecs
from shapely.geometry import mapping, shape
from more_itertools import chunked
import zipfile as zf
from collections import OrderedDict as OD
from rtree import index
from sys import exit

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
            system("cd " + dpath + "; unzip " + self.path)
            shpfiles = getfiles(dpath,".shp")
            for x in shpfiles:
                p = join(dpath,x)
                geop = p[:-3] + "geojson"
                cmd = "ogr2ogr -f GeoJSON " + geop + " " + p
                print "running",cmd
                system(cmd)
                bs = basename(p).split("-")
                f = bs[3]
                if self.code is None:
                    self.code = bs[2]
                geo = geojson.load(codecs.open(geop,encoding="shift_jisx0213"))
                self.gobj.setdefault(f,[]).extend(geo["features"])
            rmall(dpath)
        else:
            self.file_open()
            self.get_code()

    def get_code(self,fname=None):
        if fname is None:
            fname = self.path
        f = basename(fname).split('-')
        if len(f) > 3:
            self.code = f[2]

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
        f = open(self.path,'r')
        data, enc = self.detect_enc(f.read())
        self.load(data,enc,self.chk_dtype(self.path))

    def zip_file_open(self):
        zfile = zf.ZipFile(self.path)
        for l in zfile.namelist():
            if not self.chk_dtype(l) == 'NULL':
                print self.chk_dtype(l)
                f = zfile.open(l)
                data, enc = self.detect_enc(f.read())
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
        print 'Start file Load..'
        parser = ET.XMLParser(ns_clean=True,recover=True,encoding=enc)
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
                        l_obj.append(self.parse_obj(child,dtype))
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
                n_xy = child.find('.//gml:high',self.ns).text.split()
                min_xy = child.find('.//gml:lowerCorner',self.ns).text.split()
                max_xy = child.find('.//gml:upperCorner',self.ns).text.split()
                ns = [int(x) for x in n_xy]
                mins = [float(x) for x in min_xy]
                maxs = [float(x) for x in max_xy]
            else:
                i = ''
                for l in child.itertext():
                    i += l
        ret = []
        delta = [maxs[0]-mins[0],maxs[1]-mins[1]]
        num = 0
        for col in range(ns[0]):
            for row in range(ns[1]):
                new = dict(dic)
                pro2 = dict(pro)
                y = mins[0] + (float(col)/float(ns[0]))*float(delta[0])
                x = mins[1] + (float(row)/float(ns[1]))*float(delta[1])
                new['geometry'] = OD()
                new['geometry']['type'] = 'Point'
                new['geometry']['coordinates'] = (x,y)
                pro2['alti'] = vs[num].split(',')[1]
                pro2['type'] = vs[num].split(',')[0]
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
            elif not child.text.strip() == '':
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

    def rindex(self,feature,rtree=False,shpfile=True):
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
                raise NotImplementedError(y[k]["type"])
            if not s.is_valid: # fix invalid polygons
                s = s.buffer(0)
            y[k]["shapely"] = s
            if rtree:
                idx.insert(i,s.bounds)
        if rtree:
            return idx

    def extract2(self,bounds,vals,idx):
        box = shapely.geometry.box(*bounds)
        ret = []

        for i in idx.intersection(bounds): # rtree
            y = vals[i]                    # rtree
        #for y in vals:                    # !rtree
            s = y["geometry"]["shapely"]
            try:
                if not box.disjoint(s):
                    newy = OD(y)
                    res = box.intersection(s)
                    newy['geometry'] = mapping(res)
                    ret.append(newy)
            except:
                print("SSS",s.type)
                print("SSS",s.boundary.coords)
                print("YYY",y["geometry"])
                raise
        return ret

    def extract3(self,bxs,vals):
        ret = {}

        for y in vals:                    # !rtree
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
