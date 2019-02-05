from shapely.geometry import MultiPolygon,Polygon,LinearRing,LineString,Point
from math import floor,hypot
import random
from shapely.validation import explain_validity
from shapely.ops import cascaded_union
import random

def iv_idx(xy):
    """return smallest i such that xy[:i] is invalid or -1 o/w"""
    n = len(xy)

    for i in range(3,n+1):
        L = LinearRing(xy[:i])
        if not L.is_valid:
            return i
    else:
        return -1

def fix_poly(s,mdic):
    return s.buffer(0,0)

def fix_mpoly(s,mdic):
    return s.buffer(0,0)

def fix_ls(s,mdic):
    xy = zip(*s.xy)
    newxy = [xy[0]]
    for z in xy[1:]:
        if z != newxy[-1]:
            newxy.append(z)
        else:
            d = 1e-6
            newz = (z[0] + d,z[1])
            while z == newz:
                d *= 2
                newz = (z[0] + d,z[1])
            newxy.append(newz)
            mdic[newz] = z
    return LineString(newxy)

def fix_lr(s,mdic,ints=None):
    return Polygon(s).buffer(0,0).exterior
