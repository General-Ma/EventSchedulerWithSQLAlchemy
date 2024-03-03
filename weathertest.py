# -*- coding: utf-8 -*-
"""
Created on Fri Apr  7 19:28:40 2023

@author: General Ma
"""
import requests
from datetime import datetime
import pandas as pd
import geopandas as gpd


df = pd.read_csv('georef-australia-state-suburb.csv',sep=';')

place = df[df['Official Name Suburb'] == 'Maroubra']
lat = place['Geo Point'].iloc[0].split(', ')[0]
lon = place['Geo Point'].iloc[0].split(', ')[1]
print(lon,lat)


def weatherAPI():
    url = "http://www.7timer.info/bin/api.pl?" + 'lon=' + str(lon) +'&lat=' + str(lat) + '&product=civil&output=json'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
    return data

stamp = datetime.now()
time = stamp.strftime('%Y%m%d%H')
print(time)


res = weatherAPI()
target_time = (int(time) - int(res['init']))

for forecast in res['dataseries']:
    if forecast['timepoint'] > target_time - 3 and forecast['timepoint'] <= target_time:
        print(forecast)
        print(forecast['wind10m']['speed'])

'''

def holidayAPI():
    holiday_name = "*Not a holiday*"
    now = datetime.now()
    year = now.strftime('%Y')
    date = now.strftime('%Y-%m-%d')
    state = 'AU-' + 'NSW'
    url = "https://date.nager.at/api/v2/publicholidays/" + year + "/AU"
    response = requests.get(url)
    if response.status_code == 200:
        res = response.json()
        for holiday in res:
            if holiday['date'] == date and (holiday['counties'] == None or state in holiday['counties']):
                holiday_name = holiday['name']
    return holiday_name

res = holidayAPI()
print(res)

df_au = pd.read_csv('au.csv')    
cities = ['Sydney', 'Melbourne', 'Brisbane', 'Perth']
geo_dict = {}
for city in cities:
    city_info = df_au[df_au['city'] == city]
    lon = city_info.iloc[0,2]
    lat = city_info.iloc[0,1]
    geo_dict.update({city:(float(lon),float(lat))})
print(geo_dict)

now = datetime.now()
default_date = now.strftime('%d-%m-%Y')
date_query = '13-05-2023'
date_obj = datetime.strptime(date_query, '%d-%m-%Y')
date = date_obj.strftime('%Y%m%d')
print(date)

for k,v in geo_dict.items():
    print(k,v[0]) 
'''