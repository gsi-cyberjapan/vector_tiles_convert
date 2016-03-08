from os.path import join,exists,basename,splitext
import math
import pyproj
import json
import geojson
import globalmaptiles
from loadtmp import loader
from shapely.geometry import mapping,box
from datetime import datetime as dt

from utils import fmakedirs as makedirs

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
	minlat,maxlat,minlon,maxlon = get_latlon_corners(code)
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

def inv_conv_proj(obj,coord_tab):
	newobj = {'geometry':{}}
	newobj['properties'] = obj['properties']
	newobj['type'] = obj['type']
	newobj['geometry']['type'] = obj['geometry']['type']
	newobj['geometry']['coordinates'],coord_tab = rec_in_conv_proj(obj['geometry']['coordinates'],coord_tab,1)
	return newobj


def json_dump(dic,out,dpath,z,x,y):
	mercator = globalmaptiles.GlobalMercator()
	idx,idy = mercator.GoogleTile(x,y,z)
	l = None
	for k,v in dic.items():
		if l is None:
			l = v
		else:
			l.extend(v)
	        path = join(out,dpath,k,str(z),str(idx))
	        makedirs(path)
	        json_dic = {'type':'FeatureCollection', 'features':l}
	        txt = json.dumps(json_dic,indent=2,ensure_ascii=False)
	        p = join(path,str(idy)+'.geojson')
                #print "dumping",p
	        fw = open(p,'w')
	        fw.write(txt.encode('utf_8'))
	        fw.close()

def main_shp(zoom,path,out,features=None,test=False):                
        assert( path.endswiths(".shp"))
        geopath = path[:-3] + "geojson"
        cmd = "ogr2ogr -f GeoJSON " + geopath + " " + path
        system(cmd)
        gobj = geojson.load(geopath)

        
def main(zoom,path,out,features=None,test=False):
	a = loader(path)
        code = str(a.code)
	trng = get_tile_id_corner(code,zoom)

        # output folder
        dpath = splitext(basename(path))[0]
        try:
                tmp = dt.strptime(dpath[-8:],"%Y%m%d")
                if tmp.year < 1900 or tmp.year > 2100:
                        raise ValueError
                dpath = dpath[:-8].rstrip("_")
        except:
                pass

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
	start = dt.now()
        idx = {}
        vals = {}
        for f in a.gobj:
                if not features or f in features:                
	                idx[f] = a.rindex(f)
	                vals[f] = a.gobj[f]

        # generate bounds
        bs = []
        bxs = []
	for xid in range(trng[0][0],trng[0][1]+1):
		for yid in range(trng[1][0],trng[1][1]+1):
			bounds = get_clip_bound(xid,yid,zoom)
                        bs.append((xid,yid,tuple(bounds)))
                        bxs.append((xid,yid,box(*bounds)))

        res = {}        
        if test:
                for f in vals:
                        print "EXTRACT",f
                        tmp = a.extract3(bxs,vals[f],idx[f])
                        print "EXTRACT DONE"
                        for xid,yid in tmp.keys():
                                res[xid,yid,f] = tmp[xid,yid]
        else:
                for xid,yid,bounds in bs:
                        for f in vals:
                                print "EXTRACT",bounds,f
                                res[xid,yid,f] = a.extract2(bounds,vals[f],idx[f])
                                print "EXTRACT DONE"
        for k in res:
                res[k] = [inv_conv_proj(x,coord_tab) for x in res[k]]

        for xid in range(trng[0][0],trng[0][1]+1):
		for yid in range(trng[1][0],trng[1][1]+1):
                        dumpres = {f:v for (x,y,f),v in res.items() if xid == x and yid == y}
		        json_dump(dumpres,out,dpath,zoom,xid,yid)

	print "TIME:",dt.now() - start
        return dpath
