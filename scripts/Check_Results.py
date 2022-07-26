
import arcpy,os,uuid

def Feature_to_polygon(path,Out_put):

    dif_name  = str(uuid.uuid4())[::5]
    path_diss = arcpy.Dissolve_management(path,r'in_memory\Dissolve_temp' + dif_name)


    def Split_List_by_value(list1,value,del_value = False):
         list_index = []
         for n, val in enumerate(list1):
              if val == value:
                   list_index.append(n)

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

            
    polygon = []
    cursor = arcpy.SearchCursor(path_diss)
    for row in cursor:
        geom = row.shape
        for part in geom:
            num = 0
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

def del_geom(path):
    data      = [str(row[0].centroid.X) + "_" + str(row[0].centroid.Y) for row in arcpy.da.SearchCursor(path,['SHAPE@'])]
    to_delete = set()
    with arcpy.da.UpdateCursor(path,['SHAPE@']) as cursor:
        for row in cursor:
            key   = str (row[0].centroid.X) + "_" + str (row[0].centroid.Y)
            count = data.count(key)
            if count > 1:
                if key in to_delete:
                    cursor.deleteRow()
            to_delete.add(key)


def topology_basic(final):

    gdb = os.path.dirname(final)
    memory        = r'in_memory'
    random_name   = str(uuid.uuid4())[::5]
    Diss          = memory + '\\' + 'dissolve'                + random_name
    feat_to_poly  = memory + '\\' + 'Feature_to_poly'         + random_name
    topo_holes    = gdb + '\\' + 'Topolgy_Check_holes'     + random_name
    topo_inter    = gdb + '\\' + 'Topolgy_Check_intersect' + random_name
    error_polygon = final + '_Errors'          


    arcpy.Dissolve_management                 (final,Diss)
    Feature_to_polygon                        (Diss,feat_to_poly)
    Delete_polygons                           (feat_to_poly,Diss,topo_holes)

    arcpy.Intersect_analysis([final],topo_inter)

    arcpy.Delete_management(Diss)
    arcpy.Delete_management(feat_to_poly)


final = r'C:\Users\Administrator\Desktop\Tool_Curves\Results\Results_Time_15_55.gdb\Gush_5480'


topology_basic(final)