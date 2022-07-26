# -*- coding: utf-8 -*-

from re import L
import arcpy,ast
import numpy as np
import os,json,math
import pandas as pd
import datetime,uuid

arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem =  arcpy.SpatialReference(2039)

def add_field(fc,field,Type = 'TEXT'):

    TYPE = [i.name for i in arcpy.ListFields(fc) if i.name == field]
    if not TYPE:
        arcpy.AddField_management (fc, field, Type, "", "", 500)


def add_fields(layer,fields_types):
    for i in fields_types:
        add_field(layer, i[0], i[1])


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
    fields_to_add = [["IS_CURVE", "SHORT"],["Circle_X", "DOUBLE"],["Circle_Y", "DOUBLE"],["Circle_R", "DOUBLE"],["START_X", "DOUBLE"],["FINISH_X", "DOUBLE"],["MID_X", "DOUBLE"],["START_Y", "DOUBLE"],["FINISH_Y", "DOUBLE"],["MID_Y", "DOUBLE"],['KEY','DOUBLE']]

    add_fields(fc,fields_to_add)

    name_id = arcpy.Describe(fc).OIDFieldName
    num_of_curves = 0
    cursor = arcpy.UpdateCursor(fc)
    for row in cursor:
        line = row.Shape
        if IsCircle(line):
            three = get3Points(line)
            crl_params = define_circle(three[0], three[1], three[2])
            
            c_x = crl_params['center'][0]
            c_y = crl_params['center'][1]
            r   = crl_params['radius']

            row.setValue("IS_CURVE", 1)
            row.setValue("Circle_X", c_x)
            row.setValue("Circle_Y", c_y)
            row.setValue("Circle_R", r)

            row.setValue("START_X"   , three[0][0])
            row.setValue("FINISH_X"  , three[2][0])
            row.setValue("MID_X"     , three[1][0])
            row.setValue("START_Y"   , three[0][1])
            row.setValue("FINISH_Y"  , three[2][1])
            row.setValue("MID_Y"     , three[1][1])

            row.setValue("MID_Y"     , three[1][1])
            row.setValue("KEY"       , row.getValue(name_id))
            
            cursor.updateRow(row)
            num_of_curves += 1
        else:
            row.setValue("IS_CURVE", 0)
            cursor.updateRow(row)

    del cursor
    return num_of_curves



def Get_Curves_as_dict(fc,precision_X,precision_Y):

    fields     = ['SHAPE@','START_X','FINISH_X','MID_X','START_Y','FINISH_Y','MID_Y']
    dict_start = {}
    dict_end   = {}
    with arcpy.da.SearchCursor(fc,fields) as cursor:
        for row in cursor:
            if row[2]:
                if row[0].pointCount > 8:
                    template  = {'c': [[row[2],row[5]], [row[3],row[6]]]}
                    key_start = str(round_up(row[1],precision_X)) + '_' + str(round_up(row[4],precision_Y)) 
                    key_end   = str(round_up(row[2],precision_X)) + '_' + str(round_up(row[5],precision_Y))

                    dict_start [key_start] = template
                    dict_end   [key_end]   = template

    return dict_start,dict_end


def generateCurvesV2(poly,curves):

    def get_curve_from_poly(curve1):
        '''[INFO] - get the start XY of the curvee as key in x-y foramt, and the end XY and mid XY as "c" paramters
                INPUT  - arcpy geometry
                Output - x-y: {'c': [x,y],[x,y]}
                        (start)     (end)     (mid)
        '''
        curve1 = curve1['curveRings'][0]
        all_curves = []
        for i in range(len(curve1)):
            array_temp = []
            geojson_polygon = {"curveRings": [], u'spatialReference': {u'wkid': 2039, u'latestWkid': 2039}}
            if type(curve1[i]) == dict:
                if type(curve1[i-1]) == list:
                    'If normal list of [x,y] before curve'
                    array_temp.append(curve1[i-1])
                    array_temp.append(curve1[i])
                    geojson_polygon['curveRings'].append(array_temp)


                    all_curves.append(geojson_polygon)
                else:
                    'if curve before the curve'
                    array_temp.append(curve1[i-1]['c'][0])
                    array_temp.append(curve1[i])
                    geojson_polygon['curveRings'].append(array_temp)

                    all_curves.append(geojson_polygon)

        return all_curves


    gdb  = os.path.dirname(curves)
    name = os.path.basename(curves)

    if arcpy.Exists(curves):
        arcpy.Delete_management(curves)
    arcpy.CreateFeatureclass_management (gdb,name,'POLYGON')

    iCursor = arcpy.da.InsertCursor (curves, ["SHAPE@"])

    with arcpy.da.SearchCursor(poly,["SHAPE@"]) as sCursor:
        for row in sCursor:
            j = json.loads(row[0].JSON)
            # print (j)
            if 'curve' in str(j):
                curves_ = get_curve_from_poly(j)
                for curve in curves_:
                    polygon = arcpy.AsShape(curve,True)
                    iCursor.insertRow([polygon])
    del iCursor
    del sCursor
    arcpy.RepairGeometry_management(curves)


def PtsToPolygon(pts):
    point = arcpy.Point()
    array = arcpy.Array()
    for point in pts:
        array.add(point)
    array.add(array.getObject(0))

    polygon = arcpy.Polygon(array, arcpy.SpatialReference("Israel TM Grid"))
    return polygon


def Split_List_by_value(list1,value,del_value = False):

    list_index = [n for n,val in enumerate(list1) if val == value]

    list_index.append(len(list1))

    list_val = []
    num = 0
    for i in list_index:
        list_val.append(list1[num:i])
        num = + i

    if del_value:
        for i in list_val:
            for n in i:
                if n is None:
                        i.remove(value)
    return list_val



def round_up(number, decimals=3):

    if not isinstance(decimals, int):
        raise TypeError("decimal places must be an integer")
    elif decimals < 0:
        raise ValueError("decimal places has to be 0 or more")
    elif decimals == 0:
        return math.ceil(number)

    factor = 10 ** decimals
    return math.ceil(number * factor) / factor


def Polygon_order(fc_poly):
    data_poly = {}
    with arcpy.da.SearchCursor(fc_poly,'SHAPE@') as cursor:
        for row in cursor:
            for part in row[0]:
                num = 0
                for pnt in part:
                    if pnt:
                        key = str(round_up(pnt.X,1)) + '_' + str(round_up(pnt.Y,1))
                        data_poly[key] = num
                        num +=1
    return data_poly

def Polygon_order2(fc_poly):
    data_poly = {}
    num = 0
    with arcpy.da.SearchCursor(fc_poly,'SHAPE@') as cursor:
        for row in cursor:
            for part in row[0]:
                for pnt in part:
                    if pnt:
                        key = str(round_up(pnt.X,1)) + '_' + str(round_up(pnt.Y,1))
                        if key in data_poly:
                            pass
                        else:
                            data_poly[key] = num
                            num +=1
    return data_poly


def Fix_Line_order(fc_line,fc_poly,order = 1):
    data_poly = Polygon_order(fc_poly)
    if order == 2:
        data_poly =Polygon_order2(fc_poly)

    lines=arcpy.UpdateCursor(fc_line)
    for ln in lines:
        if ln.shape.partCount > 1: 
            print ("Warning: multiple parts! extra parts are automatically trimmed!")
        lp= ln.shape.getPart(0)
        if ln.START_X:
            key_start  = str(round_up(ln.START_X,1))  + '_' + str(round_up(ln.START_Y,1))
            key_end    = str(round_up(ln.FINISH_X,1)) + '_' + str(round_up(ln.FINISH_Y,1))

            if  (key_start in data_poly) and (key_end in data_poly):
                if not data_poly[key_start] < data_poly[key_end]:
                    print ('Update')
                    rPnts=arcpy.Array()
                    for i in range(len(lp)): rPnts.append(lp[len(lp)-i-1])
                    rPoly=arcpy.Polyline(rPnts)
                    ln.shape= rPoly
        lines.updateRow(ln)

    del lines

def Check_number_of_curves(path_polygon_copy,poly_line,curves_number):

    def Count_per_precision(path_polygon_copy,dict_start,dict_end,precision_X,precision_Y):
        with arcpy.da.SearchCursor(path_polygon_copy,['SHAPE@','OBJECTID']) as Ucursor:
            for row in Ucursor:
                count_curves = 0
                geom         = row[0]
                area_before  = geom.area
                inside_parts = False
                other_parts = []
                # if not suspecte_curve(geom,dict_start,dict_end):
                #     continue
                part_new   = []
                geojson_polygon = {"curveRings": [], u'spatialReference': {u'wkid': 2039, u'latestWkid': 2039}}
                for part in geom:
                    other_parts_temp = []
                    counter          = 0
                    # check if in curve = False
                    in_curve = False
                    for pnt in part:
                        if counter == 0:
                            pnt_first = [pnt.X,pnt.Y]
                            part_new.append(pnt_first)
                        if not pnt:
                            inside_parts = True
                            continue
                        if inside_parts:
                            other_parts_temp.append([pnt.X,pnt.Y])
                        key = str(round_up(pnt.X,precision_X)) + '_' + str(round_up(pnt.Y,precision_Y))
                        # if point in dict
                        if key in dict_start and inside_parts == False:
                            count_curves += 1
                            # if point in dict get the curve and add to array
                            if key not in dict_end:
                                part_new.append([pnt.X,pnt.Y])
                            part_new.append(dict_start[key])
                            in_curve = True
                        # check if coords is in the end of the part, if does, get the point back to array 
                        elif key in dict_end and inside_parts == False:
                            in_curve = False
                            if key in dict_start:
                                count_curves += 1
                                part_new.append(dict_start[key])
                                in_curve = True
                        # if coords in the curve willl not put them back
                        elif in_curve:
                            pass
                        # bring points back to polygon
                        else:
                            if inside_parts == False:
                                part_new.append([pnt.X,pnt.Y])

                        counter += 1
                    other_parts.append(other_parts_temp)
                    

                check_first(part_new,pnt_first,dict_start,precision_X,precision_Y)

                if other_parts:
                    other_parts.insert(0,part_new)
                    geojson_polygon['curveRings'] = other_parts
                else:
                    geojson_polygon['curveRings'].append(part_new)
                
                try:
                    polygon    = arcpy.AsShape(geojson_polygon,True)
                    area_after = polygon.area
                    diff       = abs(area_before-area_after)
                    prec       = abs(((area_after/area_before)*100) - 100)
                    if count_curves == 0:
                        return 0,999.0
                    ratio      = diff/count_curves
                    print (ratio)
                    print (precision_X,precision_Y)
                    return count_curves,ratio
                except:
                    print_arcpy_message('Error building geometry!',2)
                    return 0,999.0
                
    dict_start4,dict_end4 = Get_Curves_as_dict (poly_line,1,1)
    dict_start6,dict_end6 = Get_Curves_as_dict (poly_line,2,2)

    count_curves4,ratio4         = Count_per_precision (path_polygon_copy,dict_start4 ,dict_end4 ,1,1)
    count_curves6,ratio6         = Count_per_precision (path_polygon_copy,dict_start6 ,dict_end6,2,2)

    data_all = [[ratio6,count_curves6,[2,2]],[ratio4,count_curves4,[1,1]]]

    for i in data_all:
        if i[0] < 0.09:
            if  i[1] <= curves_number:
                print_arcpy_message('precison is: {}'.format(str(i[2])))
                return i[2]
    return [2,2]



def Update_Curves(path_polygon_copy,dict_start,dict_end,precision_X,precision_Y,dict_points):

    with arcpy.da.UpdateCursor(path_polygon_copy,['SHAPE@','OBJECTID']) as Ucursor:
        for row in Ucursor:
            count_curves = 0
            geom         = row[0]
            area_before  = geom.area
            # part_count   = row[0].partCount
            inside_parts = False
            # if not suspecte_curve(geom,dict_start,dict_end):
            #     continue
            part_new    = []
            other_parts = []
            geojson_polygon = {"curveRings": [], u'spatialReference': {u'wkid': 2039, u'latestWkid': 2039}}
            for part in geom:
                other_parts_temp = []
                counter          = 0
                # check if in curve = False
                in_curve = False
                for pnt in part:
                    if counter == 0:
                        pnt_first = [pnt.X,pnt.Y]
                        part_new.append(pnt_first)
                    if not pnt:
                        inside_parts = True
                        continue
                    if inside_parts:
                        other_parts_temp.append([pnt.X,pnt.Y])
                    # get key as curve dicts
                    key = str(round_up(pnt.X,precision_X)) + '_' + str(round_up(pnt.Y,precision_Y))
                    key2 = str(round_up(pnt.X,3)) + '_' + str(round_up(pnt.Y,3))
                    if key2 in dict_points and inside_parts == False:
                        if dict_points[key2][0] < 0.5:
                            print_arcpy_message ("CHanging KEY")
                            ptx = dict_points[key2][1][0]
                            pty = dict_points[key2][1][1]
                            key = str(round(ptx,precision_X)) +'_'+ str(round(pty,precision_Y))
                            part_new.append([ptx,pty])
                    # if point in dictַ
                    
                    if key in dict_start and inside_parts == False:
                        count_curves += 1
                        # if point in dict get the curve and add to array
                        if key not in dict_end and counter != 0:
                            part_new.append([pnt.X,pnt.Y])
                        else:
                            print ('curve after curve')
                        part_new.append(dict_start[key])
                        in_curve = True
                    # check if coords is in the end of the part, if does, get the point back to array 
                    elif key in dict_end:
                        in_curve = False
                    # if coords in the curve willl not put them back
                    elif in_curve:
                        pass
                    # bring points back to polygon
                    else:
                        if inside_parts == False:
                            part_new.append([pnt.X,pnt.Y])
                        
                    counter += 1
                other_parts.append(other_parts_temp)
                        
            check_first(part_new,pnt_first,dict_start,precision_X,precision_Y)
            
            if other_parts:
                other_parts.insert(0,part_new)
                geojson_polygon['curveRings'] = other_parts
            else:
                geojson_polygon['curveRings'].append(part_new)
            
            try:
                polygon = arcpy.AsShape(geojson_polygon,True)
                if polygon.partCount != row[0].partCount:
                    print_arcpy_message ('Part count is not the same')
                    OptionB = False
                    return OptionB
                
                row[0]  = polygon
                area_after = polygon.area
                diff  = abs(area_before-area_after)
                prec  = abs(((area_after/area_before)*100) - 100)
                ratio = diff/count_curves
                print ('number of curves: {}'.format(count_curves))
                print (ratio)

                if (prec > 0.05) and (diff > 0.125) and (ratio > 0.1):
                    print ('Other Option')
                    OptionB = True
                    pass
                else:
                    OptionB = False
                    print_arcpy_message ('Curves have been successfully inserted')
                    Ucursor.updateRow(row)
            except:
                OptionB = False
                print_arcpy_message('Error building geometry!',2)

    del Ucursor
    return OptionB

def Create_GDB(fgdb_name):
    GDB_file = os.path.dirname(fgdb_name)
    GDB_name = os.path.basename(fgdb_name)
    if os.path.exists(fgdb_name):
        return fgdb_name
    fgdb_name = str(arcpy.CreateFileGDB_management(GDB_file, GDB_name, "CURRENT"))
    return fgdb_name


def Create_featrue_class(name_fc,fields = [], type_ = 'POLYGON'):
    gdb  =  os.path.dirname(name_fc)
    name =  os.path.basename(name_fc)
    arcpy.CreateFeatureclass_management(gdb,name,type_)
    if fields:
        for i in fields: add_field(name_fc,i)
    return name_fc


def Check_vertices(fc):
    count = 0
    with arcpy.da.SearchCursor(fc,['SHAPE@']) as cursor:
        for row in cursor:
            count += row[0].pointCount
    return float(count)

def Check_area(fc):
    sum = 0
    with arcpy.da.SearchCursor(fc,['SHAPE@AREA']) as cursor:
        for row in cursor:
            sum += row[0]
    return float(sum)

def delete_features(list_to_delete):
    for i in list_to_delete:
        try:
            arcpy.Delete_management(i)
        except:
            print ("Coudnt delete: {}".format(i))



def print_arcpy_message(msg,status = 1):
    '''
    return a message :
    
    print_arcpy_message('sample ... text',status = 1)
    [info][08:59] sample...text
    '''
    msg = str(msg)
    
    if status == 1:
        prefix = '[info]'
        msg = prefix + str(datetime.datetime.now()) +"  "+ msg
        # print (msg)
        arcpy.AddMessage(msg)
        
    if status == 2 :
        prefix = '[!warning!]'
        msg = prefix + str(datetime.datetime.now()) +"  "+ msg
        print (msg)
        arcpy.AddWarning(msg)
            
    if status == 0 :
        prefix = '[!!!err!!!]'
        
        msg = prefix + str(datetime.datetime.now()) +"  "+ msg
        print (msg)
        arcpy.AddWarning(msg)
        msg = prefix + str(datetime.datetime.now()) +"  "+ msg
        print (msg)
        arcpy.AddWarning(msg)
            
        warning = arcpy.GetMessages(1)
        error   = arcpy.GetMessages(2)
        arcpy.AddWarning(warning)
        arcpy.AddWarning(error)
            
    if status == 3 :
        prefix = '[!FINISH!]'
        msg = prefix + str(datetime.datetime.now()) + " " + msg
        print (msg)
        arcpy.AddWarning(msg) 

    
def Get_Time():
    now = datetime.datetime.now()
    return 'Time_' + str(now.hour) +'_'+ str(now.minute) 

def Get_date():
    now = datetime.datetime.now()
    return 'date_' + str(now.day) +'_'+ str(now.month) + '_' + str(now.year)


def Feature_to_polygon(path,Out_put):

    dif_name  = str(uuid.uuid4())[::5]
    path_diss = arcpy.Dissolve_management(path,r'in_memory\Dissolve_temp' + dif_name)
            
    polygon = []
    cursor = arcpy.SearchCursor(path_diss)
    for row in cursor:
        geom = row.shape
        for part in geom:
            for pt in part:
                if pt:
                    polygon.append([pt.X,pt.Y])
                else:
                    polygon.append(None)

    poly    = Split_List_by_value(polygon,None,True)            
    feature = arcpy.CopyFeatures_management(path,Out_put)

    for i in poly[1:]:
        array = arcpy.Array()
        for n in i:
            array.add(arcpy.Point(n[0],n[1]))
        polygon      = arcpy.Polygon(array, arcpy.SpatialReference("Israel TM Grid"))
        in_rows      = arcpy.InsertCursor(feature)
        in_row       = in_rows.newRow()
        in_row.Shape = polygon
        in_rows.insertRow(in_row)
        
    arcpy.RepairGeometry_management(Out_put)
    return Out_put	


def Delete_polygons(fc,del_layer,Out_put):


    fc = arcpy.CopyFeatures_management(fc,Out_put)

    count_me = int(str(arcpy.GetCount_management(del_layer)))
    if count_me > 0:
        temp = 'in_memory' +'\\'+'_temp'
        arcpy.Dissolve_management(del_layer,temp)
        geom_del = [row.shape for row in arcpy.SearchCursor (temp)][0]
        Ucursor  = arcpy.UpdateCursor (Out_put)
        for row in Ucursor:
            geom_up     = row.shape
            new_geom    = geom_up.difference(geom_del)
            try:
                row.shape = new_geom
                Ucursor.updateRow (row)
            except:
                pass
        del Ucursor
        arcpy.Delete_management(temp)
    else:
        pass

    up_cursor = arcpy.UpdateCursor(Out_put)
    for row in up_cursor:
        geom = row.shape
        if geom.area == 0:
            up_cursor.deleteRow(row)
    del up_cursor
    
    arcpy.RepairGeometry_management(Out_put)
    return Out_put

def topology_basic(final):

    gdb  = os.path.dirname(final)
    name = os.path.basename(final)
    memory        = r'in_memory'
    Diss          = memory + '\\' + 'dissolve'               
    feat_to_poly  = memory + '\\' + 'Feature_to_poly'         
    topo_holes    = gdb    + '\\' + name +'_holes'    
    topo_inter    = gdb    + '\\' + name +'_overlap'    

    arcpy.Dissolve_management                 (final,Diss)
    Feature_to_polygon                        (Diss,feat_to_poly)
    Delete_polygons                           (feat_to_poly,Diss,topo_holes)

    arcpy.Intersect_analysis([final],topo_inter)

    arcpy.Delete_management(Diss)
    arcpy.Delete_management(feat_to_poly)

    return topo_holes,topo_inter
    


def distance(pt_1, pt_2):
    pt_1 = np.array((pt_1[0], pt_1[1]))
    pt_2 = np.array((pt_2[0], pt_2[1]))
    return np.linalg.norm(pt_1-pt_2)

def closest_node(node, nodes):
    pt = []
    dist1 = 9999999
    for j in nodes:
        n = j[0]
        if distance(node, n) <= dist1:
            dist1 = distance(node, n)
            pt = j[1] 
    return pt

def are_collinear(p1, p2, p3):
    """return True if 3 points are collinear.
    tolerance value will decide whether lines are collinear; may need
    to adjust it based on the XY tolerance value used for feature class"""
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    x3, y3 = p3[0], p3[1]
    res = x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)
    #if -tolerance <= res <= tolerance:
    return abs(res)
        
def Get_Point_from_polygon(layer_path):
    poly = []
    poly_list = []

    rows = arcpy.SearchCursor(layer_path)
    for row in rows:
        geom = row.Shape
        for part in geom:
            for i in range(len(part)-1):
                if i > 1 and i < len(part)-1:
                    if part[i-1] and part[i] and part[i+1]:
                        [p1, p2, p3] = [[part[i-1].X,part[i-1].Y],[part[i].X,part[i].Y], [part[i+1].X,part[i+1].Y]]
                        score = are_collinear(p1, p2, p3)
                        if score > 0.01:
                            poly.append(str([float('{0:.3f}'.format(p2[0])),float('{0:.3f}'.format(p2[1]))]))
                            poly_list.append([[round(p2[0],0),round(p2[1],0)],[p2[0],p2[1]]])
    return poly,poly_list

def Find_close_vertexs(layer_path,line):
    poly,poly_list  = Get_Point_from_polygon(layer_path)
    line            = [str([round(part[0].X,3),round(part[0].Y,3)]) for i in arcpy.SearchCursor(line) for part in i.Shape if len(part) > 2]

    set1 = set(poly)
    set2 = set(line)
    ans  = set2 - set1

    dict_points = {str(k[0][0])+'-'+str(k[0][1]) :[99999] for k in poly_list}

    for i in ans:
        pt = ast.literal_eval(i)   # list of lines to check
        an = closest_node(pt,poly_list) # list of poly
        if not an:
            continue
        key = str(round(an[0],0))+'-'+str(round(an[1],0))
        if key in dict_points:
            dista = distance(pt,an)
            if dict_points[key][0] > dista:
                dict_points[key] = [dista,pt,an]

    for k,v in list(dict_points.items()):
        if len (v) == 3:
            new_key = str(round(v[2][0],3)) +'_'+ str(round(v[2][1],3))
            dict_points[new_key] = dict_points.pop(k)
        else:
            del dict_points[k]
        
    return dict_points

def Check_other_option(poly_line,poly_out,dict_points):
        Find_Curves    (poly_line)
        Fix_Line_order (poly_line,poly_out,2)
        curves_number           =  Find_Curves           (poly_line)
        precision_X,precision_Y = Check_number_of_curves (poly_out,poly_line,curves_number) # need to be upgrated
        dict_start,dict_end     = Get_Curves_as_dict     (poly_line,precision_X,precision_Y)
        Update_Curves           (poly_out,dict_start,dict_end,precision_X,precision_Y,dict_points)


def Find_gush_path(gdb):
    if gdb != '':
        arcpy.env.workspace = gdb
        list_fcs            = set([int(i.split('_')[-1]) for i in arcpy.ListFeatureClasses() if len(i.split('_')) == 2])
        return list_fcs
    return []

def get_gush_to_format(filter_gushs):
    return '(' + ''.join([i for i in filter_gushs if i.isnumeric() or i == ',']) + ')'



def check_first(part_new,pnt_first,dict_start,precision_X,precision_Y):
    key = str(round_up(pnt_first[0],precision_X)) + '_' + str(round_up(pnt_first[1],precision_Y))
    if key not in dict_start:
        if part_new[0] != pnt_first:
            print_arcpy_message ('add first point')
            part_new.insert(0,pnt_first)
        return part_new
    return part_new


print_arcpy_message ('# # #     S T A R T     # # #')

####################################################################################################################


# path_polygon  = r'C:\Users\Administrator\Desktop\Tool_Curves\data\data.gdb\pa_1'
# line_bankal   = r'C:\Users\Administrator\Desktop\Tool_Curves\data\data.gdb\Lines'
# gdb_input       = ''

# gush_to_search = '()'


path_polygon  = r'C:\Users\Administrator\Desktop\Tool_Curves\data\kadaster.gdb\PARCEL_ALL_02'
line_bankal   = r'C:\Users\Administrator\Desktop\Tool_Curves\data\kadaster.gdb\Parcel_line'
gdb_input     = r'C:\Users\Administrator\Desktop\Tool_Curves\Results\Results_Time_13_18.gdb'

gush_to_search = '()'

####################################################################


# path_polygon     = arcpy.GetParameterAsText(0) 
# line_bankal      = arcpy.GetParameterAsText(1) 
# gdb_input        = arcpy.GetParameterAsText(2) 
# gush_to_search   = get_gush_to_format(arcpy.GetParameterAsText(3))


scriptPath     = os.path.abspath (__file__)
folder_basic   = os.path.dirname (scriptPath)
folder_data    = folder_basic + "\\" + "data"
folder_temp    = folder_basic + "\\" + "Temp"
folder_results = folder_basic + "\\" + "Results"
GDB_name       = r'Results_'  +  Get_Time()
new_gdb        = True

if gdb_input == '':
    gdb_input = folder_results + '\\' + GDB_name
    new_gdb   = False
gdb_full_path  = Create_GDB(gdb_input)


gdb_temp       = folder_temp + '\\' + 'Temp_GDB.gdb'
if arcpy.Exists(gdb_temp):
    arcpy.Delete_management(gdb_temp)
gdb_temp  = Create_GDB(gdb_temp)

dict_data_log   = []
data_parcel_log = []


if gush_to_search == '()':
    all_gushes = set([i[0] for i in arcpy.da.SearchCursor(path_polygon,['GUSH_NUM'])])
else:
    all_gushes = set([i[0] for i in arcpy.da.SearchCursor(path_polygon,['GUSH_NUM'],"\"GUSH_NUM\" IN {}".format(gush_to_search))])

if new_gdb:
    set_of_gushes = Find_gush_path(gdb_input)
    all_gushes     = all_gushes - set_of_gushes

for gush in all_gushes:
    dict_data_log_temp = []

    dict_data_log_temp.append(gush)
    print_arcpy_message (" WORKING ON GUSH: {}".format(gush))

    gush_fc_gush   = gdb_temp   + '\\' + 'Fc_'    + str(gush)
    line_fc_line   = gdb_temp   + '\\' + 'Fc_Line'+ str(gush)

    Fc_name_       = 'Gush_'       + str(gush) 
    line_gush      = 'LineGush'    + str(gush)
    Fc_            = gdb_full_path + '\\' + Fc_name_ 
    Fc_curve       = gdb_full_path + '\\' + line_gush

    name_lyr_gush  = 'Poly_copy_' + str(gush)

    # Create_featrue_class(Fc_     ,fields = [], type_ = 'POLYGON')
    Create_featrue_class(Fc_curve,fields = [], type_ = 'POLYGON')

    arcpy.MakeFeatureLayer_management       (path_polygon,name_lyr_gush)
    arcpy.SelectLayerByAttribute_management (name_lyr_gush,"NEW_SELECTION","\"GUSH_NUM\" = {}".format(gush))
    arcpy.Select_analysis                   (name_lyr_gush,gush_fc_gush)

    arcpy.MakeFeatureLayer_management       (line_bankal,line_gush)
    arcpy.SelectLayerByLocation_management  (line_gush,'Have their center in',gush_fc_gush,0.1)
    arcpy.Select_analysis                   (line_gush,line_fc_line)

    arcpy.Select_analysis                   (gush_fc_gush,Fc_,"\"OBJECTID\" = -1")

    number_of_parts = int(str(arcpy.GetCount_management(gush_fc_gush)))

    print_arcpy_message ('total parcels in gush: {}'.format(str(arcpy.GetCount_management(gush_fc_gush))))

    vertices_before = 0
    vertices_afetr  = 0
    for i in range(1,int(str(arcpy.GetCount_management(gush_fc_gush))) + 1):

        print_arcpy_message (" WORKING ON OBJECT: {}".format(i))
        name_lyr = 'Poly_copy' + str(i) + '_' + str(gush)
        lyr_line = 'line_lyr'  + str(i) + '_' + str(gush)

        poly_out  = gdb_temp + '\\' + 'Num_'   + str(i) +'_'+ str(gush)
        poly_line = gdb_temp + '\\' + 'Line'   + str(i) +'_'+ str(gush)
        out_name  = gdb_temp + '\\' + 'Curves' + str(i) +'_'+ str(gush)

        arcpy.MakeFeatureLayer_management       (gush_fc_gush,name_lyr)
        arcpy.SelectLayerByAttribute_management (name_lyr,"NEW_SELECTION","\"OBJECTID\" = {}".format(i))

        arcpy.MakeFeatureLayer_management      (line_fc_line,lyr_line)
        arcpy.SelectLayerByLocation_management (lyr_line,'Have their center in',name_lyr,0.1)

        if arcpy.Exists(poly_out):
            arcpy.Delete_management(poly_out)
        arcpy.Select_analysis(name_lyr,poly_out)

        if arcpy.Exists(poly_line):
            arcpy.Delete_management(poly_line)
        arcpy.Select_analysis(lyr_line,poly_line)

        if arcpy.Exists(out_name):
            arcpy.Delete_management(out_name)

        Parcel = [i[0] for i in arcpy.da.SearchCursor(poly_out,['PARCEL'])][0]
        print_arcpy_message (" PARCEL NUMBER: {}".format(Parcel))


        Find_Curves    (poly_line)
        Fix_Line_order (poly_line,poly_out)
        curves_number =  Find_Curves    (poly_line)
        precision_X,precision_Y = Check_number_of_curves(poly_out,poly_line,curves_number) 
        dict_start,dict_end = Get_Curves_as_dict (poly_line,precision_X,precision_Y)

        if not dict_start:
            arcpy.Append_management(poly_out,Fc_,'NO_TEST')
            delete_features([poly_line,poly_out])
            print_arcpy_message ('No curves Found')
            continue

        parcel_log_temp    = []
        parcel_log_temp.append(gush)    # parcel gush
        parcel_log_temp.append(Parcel)  # parcel parcel

        area_before  = Check_area     (poly_out)
        count_before = Check_vertices (poly_out)
        dict_points  = Find_close_vertexs (poly_out,poly_line)

        optionB      = Update_Curves                 (poly_out,dict_start,dict_end,precision_X,precision_Y,dict_points)
        if optionB:
            Check_other_option(poly_line,poly_out,dict_points)
        count_after  = Check_vertices (poly_out)
        area_after   = Check_area     (poly_out)

        vertices_before += count_before
        vertices_afetr  += count_after

        precentage      = abs(((float(count_after)/float(count_before)) * 100) - 100)
        precentage_area = abs(((float(area_after)/float(area_before))   * 100) - 100)

        parcel_log_temp.append(count_before)  # parcel vertices before
        parcel_log_temp.append(count_after)   # parcel vertices after
        parcel_log_temp.append(precentage)    # parcel vertices precentage

        parcel_log_temp.append(area_before)      # parcel area before
        parcel_log_temp.append(area_after)       # parcel area after
        parcel_log_temp.append(precentage_area)  # parcel area precentage

        parcel_log_temp.append(str(precision_X) +'_'+ str(precision_Y)) # precision

        arcpy.Append_management(poly_out,Fc_,'NO_TEST')
        generateCurvesV2(poly_out,out_name)
        arcpy.Append_management(out_name,Fc_curve,'NO_TEST')

        # delete_features([poly_out,poly_line,out_name])

        data_parcel_log.append(parcel_log_temp   )

        del name_lyr
        del lyr_line
        del poly_out

    topo_holes,topo_inter = topology_basic(Fc_)
    delete_features([gush_fc_gush,line_fc_line])

    number_of_holes     = int(str(arcpy.GetCount_management(topo_holes)))
    number_of_inter     = int(str(arcpy.GetCount_management(topo_inter)))
    number_of_curves    = int(str(arcpy.GetCount_management(Fc_curve)))

    if number_of_curves == 0:
        print_arcpy_message ('No Curves in GUSH !! delete all gush filels')
        delete_features     ([Fc_,Fc_curve,topo_holes,topo_inter])
        continue

    col     = ['GUSH','holes','intersects','curves','vertices before','vertices afetr']
    df_topo = pd.DataFrame(data =[[gush,number_of_holes,number_of_inter,number_of_curves,vertices_before,vertices_afetr]] ,columns = col)

    df2     = pd.DataFrame(data_parcel_log ,columns = ['GUSH','PARCEL','sum vrtx before','sum vrtx after','Prec of change vrtx'\
                                                ,'sum area before','sum area after','sum area precentage','precision'])

    df_topo.to_csv  (folder_results + '\\' + 'Topo_' + GDB_name +  '_' + str(gush) +'.csv')
    df2.to_csv      (folder_results + '\\' + GDB_name +  '_' + str(gush) +'.csv')

    del df2
    del df_topo


print_arcpy_message (' F I N I S H')