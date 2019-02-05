from os.path import join,exists,basename,splitext
import math
import pyproj
import json
import geojson
import globalmaptiles
import codecs
from load import loader
from shapely.geometry import mapping,box
from datetime import datetime as dt

from utils import u_makedirs as makedirs

def conv_latlon(lat,lon,inv=None):
    if inv is None:
        src_proj = pyproj.Proj(init="epsg:4612")
        dst_proj = pyproj.Proj(init="epsg:3857")
    else:
        dst_proj = pyproj.Proj(init="epsg:4612")
        src_proj = pyproj.Proj(init="epsg:3857")
    nlon,nlat = pyproj.transform(src_proj,dst_proj,lon,lat)
    return (nlat,nlon)

# get latlon on bottom-left corner of a mesh
def get_latlon(code):
    if len(code) < 4:
        print("code is too short!")
    lat = float(code[0:2]) / 1.5
    lon = float(code[2:4]) + 100.0

    if len(code) >= 6:
        lat += float(code[4]) * 5.0 / 60.0
        lon += float(code[5]) * 7.5 / 60.0
    if len(code) >= 8:
        lat += float(code[6]) * 30.0 / 3600.0
        lon += float(code[7]) * 45.0 / 3600.0
    if len(code) >= 9:
        if code[8] == "2" or code[8] == "4":
            lon += 22.5 / 3600.0
        if code[8] == "3" or code[8] == "4":
            lat += 15.0 / 3600.0
    return (lat,lon)

#get latlon on all corners
def get_latlon_corners(code):
    minlat,minlon = get_latlon(code)
    if len(code) == 4:
        maxlat = minlat + 40.0/60.0
        maxlon = minlon + 1.0
    elif len(code) == 6:
        maxlat = minlat + 5.0/60.0
        maxlon = minlon + 7.5/60.0
    elif len(code) == 8:
        maxlat = minlat + 30.0/3600.0
        maxlon = minlon + 45.0/3600.0
    elif len(code) == 9:
        maxlat = minlat + 15.0/3600.0
        maxlon = minlon + 22.5/3600.0
    return (minlat,maxlat,minlon,maxlon)

def get_tile_id_corner(code,zoom):
    if not isinstance(zoom,int):
        zoom=int(zoom)
    if code[0] == 'code':
        minlat,maxlat,minlon,maxlon = get_latlon_corners(code[1])
    elif code[0] == 'corner':
        minlon,maxlon,minlat,maxlat = code[1][0][0],code[1][0][1],code[1][1][0],code[1][1][1]
    min_my,min_mx = conv_latlon(minlat,minlon)
    max_my,max_mx = conv_latlon(maxlat,maxlon)

    mercator = globalmaptiles.GlobalMercator()
    min_tx,min_ty = mercator.MetersToTile(min_mx,min_my,zoom)
    max_tx,max_ty = mercator.MetersToTile(max_mx,max_my,zoom)

    return [[min_tx,max_tx],[min_ty,max_ty]]

def get_clip_bound(x,y,z):
    mercator = globalmaptiles.GlobalMercator()
    bounds = mercator.TileBounds( x, y, z)
    return bounds

def conv_proj(obj,coord_tab):
    ret,coord_tab = rec_in_conv_proj(obj['geometry']['coordinates'],coord_tab)
    obj['geometry']['coordinates'] = ret
    return obj,coord_tab

def in_conv_proj(obj,coord_tab,inv=None):
    if not isinstance(obj,list):
        if obj in coord_tab:
            return coord_tab[obj]
    y,x = conv_latlon(obj[1],obj[0],inv=inv)
    return (x,y)

def rec_in_conv_proj(obj,coord_tab,inv=None):
    if isinstance(obj[0],float):
        res = in_conv_proj(obj,coord_tab,inv)
        if inv is None and not res in coord_tab:
            coord_tab[res] = (obj[0],obj[1])
        return res,coord_tab
    elif not obj is None:
        ret = []
        for o in obj:
            z,coord_tab = rec_in_conv_proj(o,coord_tab,inv)
            ret.append(z)
        return ret,coord_tab

def fix_coords(coords,mdic):
    if isinstance(coords[0],float):
        coords = tuple(coords)
        if coords in mdic:
            return mdic[coords]
        else:
            return coords
    else:
        return [fix_coords(x,mdic) for x in coords]
    
def inv_conv_proj(obj,coord_tab,mdic):
    newobj = {'geometry':{}}
    newobj['properties'] = obj['properties']
    newobj['type'] = obj['type']
    newobj['geometry']['type'] = obj['geometry']['type']
    coords = fix_coords(obj['geometry']['coordinates'],mdic)
    newobj['geometry']['coordinates'],coord_tab = rec_in_conv_proj(coords,coord_tab,1)
    return newobj


def json_dump(dic,out,dpath,z,x,y):
    mercator = globalmaptiles.GlobalMercator()
    idx,idy = mercator.GoogleTile(x,y,z)
    l = None
    for k,v in dic.items():
        if not v:
            continue
        path = join(out,dpath,k,str(z),str(idx))
        makedirs(path)
        ###For HazardMap Start###
        HM_dic = {u'A31_001':u'DepCd',u'A31_002':u'JurisFclCd',u'A31_009':u'Area',u'A31_010':u'Rvr',u'A31_011':u'Depth',u'A31_012':u'Lv',u'A31_013':u'Date',u'A31_014':u'TypeCd'}
        for i in range(len(v)):
            for ik,iv in HM_dic.items():
                if ik in v[i][u'properties']:
                    v[i][u'properties'][iv] = v[i][u'properties'][ik]
                    del v[i][u'properties'][ik]
                    if ik == u'A31_011':
                        try:
                            v[i][u'properties'][iv] = float(v[i][u'properties'][iv])
                        except:
                            if v[i][u'properties'][iv] == '':
                                v[i][u'properties'][iv] = None
                    elif ik in [u'A31_001',u'A31_002',u'A31_014']:
                        try:
                            v[i][u'properties'][iv] = int(v[i][u'properties'][iv])
                        except:
                            if v[i][u'properties'][iv] == '':
                                v[i][u'properties'][iv] = None
                        if ik == u'A31_001' and v[i][u'properties'][iv] == 1:
                            v[i][u'properties'][iv] = None



        ####For HazardMap End##
        json_dic = {'type':'FeatureCollection', 'features':v}
        try:
            txt = json.dumps(json_dic,indent=2,ensure_ascii=False)
        except:
            print("V",bytes(v)[:1200])
            raise
        p = join(path,str(idy)+'.geojson')
        fw = codecs.open(p,'w','utf-8')
        fw.write(txt)
        fw.close()

def main_shp(zoom,path,out,features=None,test=False):
    assert( path.endswiths(".shp"))
    geopath = path[:-3] + "geojson"
    cmd = "ogr2ogr -f GeoJSON " + geopath + " " + path
    system(cmd)
    gobj = geojson.load(geopath)

        
def main(zoom,path,out,features=None,test=False,code=None,shpfile=False):
    start = dt.now()
    a = loader(path,shpfile)
    print "TIME LOAD:",dt.now() - start
    if code is None:
        if a.code[0] == 'code':
            code = ['code',a.code[1]]
            dpath = str(a.code[1])
        elif a.code[0] == 'corner':
            code = ['corner',a.code[1]]
            dpath = ''
        else:
            raise ValueError("illegal code type")
    else:
        dpath = code
        code = ['code',code]
        
    trng = get_tile_id_corner(code,zoom)

    # check featurelist
    for x in features:
        if x not in a.gobj.keys():
            print("X",x)
            print("FS",sorted(features))
            print("KS",sorted(a.gobj.keys()))
        assert(x in a.gobj.keys())

    # convert coordinates
    coord_tab = {}
    for f in a.gobj:
        if not features or f in features:
            for i in range(len(a.gobj[f])):
                a.gobj[f][i],coord_tab = conv_proj(a.gobj[f][i],coord_tab)

    # generate index
    idx = {}
    vals = {}
    mdic = {}
    for f in a.gobj:
        if not features or f in features:                
            idx[f] = a.rindex(f,mdic,rtree=not test)
            vals[f] = a.gobj[f]
    print "TIME INDEX:",dt.now() - start
    # generate bounds
    bs = []
    bxs = []
    for xid in range(trng[0][0],trng[0][1]+1):
        for yid in range(trng[1][0],trng[1][1]+1):
            bounds = get_clip_bound(xid,yid,int(zoom))
            bs.append((xid,yid,tuple(bounds)))
            bxs.append((xid,yid,box(*bounds)))

    res = {}        
    if test:
        for f in vals:
            tmp = a.extract3(bxs,vals[f])"
            for xid,yid in tmp.keys():
                res[xid,yid,f] = tmp[xid,yid]
    else:
        for xid,yid,bounds in bs:
            res[xid,yid] = {}
            for f in vals:
                res[xid,yid][f] = a.extract2(bounds,vals[f],idx[f])
    print "TIME EXTRACT:",dt.now() - start
    for k in res:
        for kk in res[k]:
            res[k][kk] = [inv_conv_proj(x,coord_tab,mdic) for x in res[k][kk]]

    print "TIME COORD:",dt.now() - start
    for xid in range(trng[0][0],trng[0][1]+1):
        for yid in range(trng[1][0],trng[1][1]+1):
            dumpres = res[xid,yid]
            if dumpres:
                json_dump(dumpres,out,dpath,int(zoom),xid,yid)

    print "TIME DUMP:",dt.now() - start
    return code
