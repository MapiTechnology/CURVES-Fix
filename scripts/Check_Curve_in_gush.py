import arcpy,os
import pandas as  pd
import numpy as np


def get3Points(line):
    for part in line:
        if len(part) > 2:
            length = len(part)
            return [[part[0].X, part[0].Y],[part[int(length/2)].X, part[int(length/2)].Y] ,[part[length - 1].X, part[length-1].Y]]
        else:
            return []

def define_circle(p1, p2, p3):
    """
    Returns the center and radius of the circle passing the given 3 points.
    In case the 3 points form a line, returns (None, infinity).
    """
    temp = p2[0] * p2[0] + p2[1] * p2[1]
    bc   = (p1[0] * p1[0] + p1[1] * p1[1] - temp) / 2
    cd   = (temp - p3[0] * p3[0] - p3[1] * p3[1]) / 2
    det  = (p1[0] - p2[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p2[1])

    if abs(det) < 1.0e-6:
        return []

    # Center of circle
    cx = (bc*(p2[1] - p3[1]) - cd*(p1[1] - p2[1])) / det
    cy = ((p1[0] - p2[0]) * cd - (p2[0] - p3[0]) * bc) / det

    radius = np.sqrt((cx - p1[0])**2 + (cy - p1[1])**2)
    return {'center':(cx, cy), 'radius': radius}

def IsOnCircle(x1, y1, a, b, r):
    if round((x1 - a)*(x1 - a) + (y1 - b) * (y1 - b), 1) == round(r*r, 1):
        return True
    else:
        return False

def IsCircle(line):
    is_circle = False
    three = get3Points(line)
    if len(three) > 0:
        crl_params = define_circle(three[0], three[1], three[2])
        if crl_params:
            a = crl_params['center'][0]
            b = crl_params['center'][1]
            r = crl_params['radius']
            # if ratio > ... not circle
            for part in line:
                for pt in part:
                    if IsOnCircle(pt.X, pt.Y, a, b, r):
                        is_circle = True
                    else:
                        is_circle = False
        else:
            is_circle = False
            print ('coudnt calculate circle')
    else:
        is_circle = False
    return is_circle

def Find_Curves(fc):
    cursor = arcpy.SearchCursor(fc)
    for row in cursor:
        line = row.Shape
        if IsCircle(line):
            del cursor
            return True
    del cursor
    return False

def Exists_in_csv(csv):
    if os.path.exists(csv):
        df_exists          = pd.read_csv(csv)
        return list(df_exists.values[:,1])
    else:
        return []

def Create_GDB(fgdb_name):
    GDB_file = os.path.dirname(fgdb_name)
    GDB_name = os.path.basename(fgdb_name)
    if os.path.exists(fgdb_name):
        arcpy.Delete_management(fgdb_name)
    fgdb_name = str(arcpy.CreateFileGDB_management(GDB_file, GDB_name, "CURRENT"))
    return fgdb_name

path_polygon = r'C:\Users\Administrator\Desktop\medad\python\Work\Tool_Curves\data\kadaster.gdb\PARCEL_ALL_02'
line_fc_line = r'C:\Users\Administrator\Desktop\medad\python\Work\Tool_Curves\data\kadaster.gdb\Parcel_line'

csv = r'C:\Users\Administrator\Desktop\medad\python\Work\Tool_Curves\gush_with_curves.csv'


exists_gush  = Exists_in_csv(csv)
len_already  = len(exists_gush)
temp_folder  = r'C:\temp'
gdb_temp     = temp_folder + '\\' + 'Temp_GDB.gdb'
gdb_temp     = Create_GDB(gdb_temp)

all_gush     = set([i[0] for i in arcpy.da.SearchCursor\
             (path_polygon,['GUSH_NUM']) if int(i[0]) not in exists_gush])

total_gushs     = len(all_gush)
current         = 1
for gush in all_gush:
    print ("{}\{}".format(current,total_gushs))
    name_lyr_gush = "gush_layer" + str(gush)
    lyr_line      = "Line_layer" + str(gush)
    poly_line     = gdb_temp + '\\' + "Line_" + str(gush)
    arcpy.MakeFeatureLayer_management       (path_polygon,name_lyr_gush)
    arcpy.SelectLayerByAttribute_management (name_lyr_gush,"NEW_SELECTION","\"GUSH_NUM\" = {}".format(gush))
    arcpy.MakeFeatureLayer_management      (line_fc_line,lyr_line)
    arcpy.SelectLayerByLocation_management (lyr_line,'Have their center in',name_lyr_gush,0.1)
    arcpy.Select_analysis(lyr_line,poly_line)
    if Find_Curves(poly_line):
        arcpy.Delete_management(poly_line)
        df = pd.DataFrame(data = [[gush,1]],columns = ['GUSH','IsCurve'])
        df.to_csv(csv, mode='a', index=True, header=False)
    else:
        df = pd.DataFrame(data = [[gush,0]],columns = ['GUSH','IsCurve'])
        df.to_csv(csv, mode='a', index=True, header=False)
    current += 1


