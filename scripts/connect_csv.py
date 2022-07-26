
import pandas as pd
import os

def Sum_csv(file_out_put):

	list_csv = []
	for root, dirs, files in os.walk(str(file_out_put)):
		for file in files:
			if file.endswith('.csv'):
				if  'all' not in file:
					if 'Topo' not in file:
						list_csv.append(root + '\\' + file)
	return list_csv


def Sum_csv_topo(file_out_put):

	list_csv = []
	for root, dirs, files in os.walk(str(file_out_put)):
		for file in files:
			if file.endswith('.csv'):
				if  'all' not in file:
					if 'Topo' in file:
						list_csv.append(root + '\\' + file)
	return list_csv


def bigger_then_0(number):
	if number > 0:
		return 1
	return 0

file_out_put = r'C:\Users\Administrator\Desktop\Tool_Curves\Results'

csv_list = Sum_csv(file_out_put)

csv_topo = Sum_csv_topo(file_out_put)

################  create sum of  csvs for parcel################

fields = ['GUSH','PARCEL','sum vrtx before','sum vrtx after','Prec of change vrtx'\
          ,'sum area before','sum area after','sum area precentage','precision']

df_all = pd.DataFrame(columns=fields)
for i in csv_list:
    df      = pd.read_csv(i)
    df_all  = pd.concat([df_all,df])


df_all['Worked'] = df_all['Prec of change vrtx'].apply(lambda x:bigger_then_0(x))
gb_sum           = df_all.groupby('GUSH')['Worked'].sum().reset_index()
gb_count         = df_all.groupby('GUSH')['Worked'].count().reset_index()
gb_all           = gb_count.merge(gb_sum,on = 'GUSH')

gb_all['prc curves completed'] =  (gb_all['Worked_y']/gb_all['Worked_x'])*100


df_all = df_all.merge(gb_all,on = 'GUSH')
df_all = df_all.drop(['Unnamed: 0','Worked_x',  'Worked_y'], axis=1)

df_all.to_csv          (file_out_put + '\\' + 'all.csv')


################  create sum of  csvs for Gush  ################

fields_gush = ['GUSH','holes','intersects','curves','vertices before','vertices afetr']

df_all_gush = pd.DataFrame(columns=fields_gush)
for i in csv_topo:
    df_gush      = pd.read_csv(i)
    df_all_gush  = pd.concat([df_all_gush,df_gush])

df_all_gush['Worked'] = df_all_gush['curves'].apply(lambda x:bigger_then_0(x))
df_all_gush           = df_all_gush.drop(['Unnamed: 0'], axis=1)
df_all_gush           = df_all_gush[df_all_gush['Worked'] > 0]


df_all_gush.to_csv    (file_out_put + '\\' + 'Topo_all.csv')