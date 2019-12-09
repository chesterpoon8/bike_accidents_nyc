import pandas as pd
import numpy as np
import datetime as dt
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import folium
from folium import plugins
from datetime import datetime
import os
import json
import requests
import time
from app_token import app_token
from bs4 import BeautifulSoup
from crash import Crash

def main():

    """
    *********************************************
    Extract and clean data from nyc open data
    *********************************************
    """
    APP_TOKEN = app_token()
    base_url = "https://data.cityofnewyork.us/resource/h9gi-nx95.json?$$app_token={}".format(APP_TOKEN)
    url = base_url + "{}"
    cnt_url = base_url + "{}{}" # select , where

    where_inj = "&$where=number_of_cyclist_injured>0.0&$limit=50000"
    where_kill = "&$where=number_of_cyclist_killed>0.0"

    inj_df = pd.read_json(url.format(where_inj))
    killed_df = pd.read_json(url.format(where_kill))

    def dt(date,time):
        date = pd.to_datetime(date).dt.date
        time = pd.to_datetime(time).dt.time
        return date,time

    # so frustrating. NYC open data changed columns from "accident" to "crash"

    killed_df.crash_date, killed_df.crash_time = dt(killed_df.crash_date,
                                                      killed_df.crash_time)
    inj_df.crash_date, inj_df.crash_time = dt(inj_df.crash_date,
                                                inj_df.crash_time)

    killed_df = killed_df.rename(columns={'crash_date':'accident_date','crash_time':'accident_time'})
    inj_df = inj_df.rename(columns={'crash_date':'accident_date','crash_time':'accident_time'})

    df = (pd
          .concat([inj_df,killed_df])
          .drop(columns='location')
          .drop_duplicates()
          .reset_index(drop=True)
         )
    df.vehicle_type_code1 = df.vehicle_type_code1.apply(lambda x :str(x).upper())
    df.vehicle_type_code2 = df.vehicle_type_code2.apply(lambda x :str(x).upper())

    df['Accident Year'] = df.accident_date.apply(lambda x: x.year)
    df['Accident Month'] = df.accident_date.apply(lambda x: x.month)
    df['Accident Hour'] = df.accident_time.apply(lambda x: x.hour)

    def create_df(group):
        return (df
                .groupby(group)
                .collision_id.count()
                .reset_index()
                .rename(columns={'collision_id':'Number of Accidents'})
               )

    """
    *********************************************
    Create figures for month and hour data
    *********************************************
    """

    crash_mo_yr = create_df(['Accident Year','Accident Month'])
    crash_hr = create_df('Accident Hour')
    crash_mo_hr = create_df(['Accident Month','Accident Hour'])

    killed_df['accident_year'] = killed_df.accident_date.apply(lambda x: x.year)
    killed_df['accident_month'] = killed_df.accident_date.apply(lambda x: x.month)
    killed_df['accident_hr'] = killed_df.accident_time.apply(lambda x: x.hour)

    mo_fig = px.area(crash_mo_yr, x="Accident Month", y="Number of Accidents",animation_frame="Accident Year",
                     range_y=[0,800], range_x=[1,12])
    mo_fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 1000
    mo_fig.layout.title = "Bicycle Accidents by Month for Each Year"

    pio.write_html(mo_fig, file="app/static/mo_fig.html", auto_play=False)

    hr_fig = px.area(crash_mo_hr, x="Accident Hour", y="Number of Accidents",animation_frame="Accident Month",
                     range_y=[0,400], range_x=[0,23])
    hr_fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 1000
    hr_fig.layout.title = "Bicycle Accidents by Hour For Each Month"

    pio.write_html(hr_fig, file="app/static/hr_fig.html", auto_play=False)

    """
    *********************************************
    Extract data from citibike files - all trips
    *********************************************
    """

    fdir = './agg_trip'
    agg_files = os.listdir(fdir)
    agg_df = pd.read_csv(fdir + '/' + agg_files[0]).iloc[:,[0,1]]
    for i in range(1,len(agg_files)):
        agg_df = agg_df.append(pd.read_csv(fdir + '/' + agg_files[i]).iloc[:,[0,1]])
    agg_df.Date = pd.to_datetime(agg_df.Date).dt.date
    agg_df = agg_df.rename(columns={'Trips over the past 24-hours (midnight to 11:59pm)':'Number of Trips'})
    agg_df = agg_df.sort_values('Date')

    fig = px.line(agg_df, x='Date', y='Number of Trips', title="Number of CitiBike Trips by Day", hover_name='Date')
    pio.write_html(fig, file="app/static/fig.html", auto_play=False)


    """
    *********************************************
    Using 9/25/2019 to map common citibike routes
    *********************************************
    """

    high_day = pd.read_csv('./app/static/high_day.csv')
    coord092519 = high_day[['start station name','start station id','start station latitude',
                    'start station longitude','end station name','end station id',
                    'end station latitude',
                    'end station longitude']].copy()
    coord092519['id'] = (coord092519['start station name'] +
                          coord092519['end station name'])
    coord092519 = coord092519.groupby(['start station name','start station id','start station latitude',
                                       'start station longitude',
                                       'end station name','end station id','end station latitude',
                                      'end station longitude']).id.count().reset_index()

    coord092519['filt'] = coord092519.apply(lambda x: 'y' if x['start station name'] == x['end station name'] else '',
                                           axis=1)
    coord092519 = coord092519[coord092519.filt != 'y'].reset_index(drop=True)

    cohort = coord092519[coord092519.id >= 4]
    cohort = cohort.rename(columns={'id':'count'})
    cohort['id'] = cohort['start station id'].apply(str) + '-' + cohort['end station id'].apply(str)

    routes = pd.read_csv('./app/static/backup_route_file.csv')
    routes = routes[routes.geojson != '{"message":"Too Many Requests"}'].reset_index(drop=True)

    cohort_df = pd.merge(cohort,routes[['id','geojson']],on='id',how='inner')
    cohort_df = cohort_df[['geojson']].drop_duplicates()

    geojson = list(cohort_df.geojson)
    gjson = []
    for i in range(len(geojson)):
        gjson.append(json.loads(geojson[i])['routes'][0]['geometry']['coordinates'])

    for i in gjson:
        for j in i:
            j.reverse()

    """
    *********************************************
    mapping the accidents
    *********************************************
    """

    loc_df = df[['borough','latitude','longitude','on_street_name','off_street_name','accident_date']].copy()
    loc_df = loc_df[(pd.isna(loc_df.latitude) == False) &
                    (loc_df.latitude != 0) &
                    (loc_df.longitude != 0)
                   ]
    loc_df.on_street_name = loc_df.on_street_name.str.strip()
    loc_df.off_street_name = loc_df.off_street_name.str.strip()
    loc_df.accident_date = loc_df.accident_date.apply(str)
    loc_df['lat_lon_list'] = loc_df.apply(lambda x: [x.longitude,x.latitude], axis=1)
    loc_df = loc_df.sort_values('accident_date').reset_index(drop=True)

    intersect_df = loc_df.copy()
    intersect_df['intersection'] = intersect_df.on_street_name + ';' + intersect_df.off_street_name
    intersect_df.intersection = intersect_df.intersection.apply(
        lambda x: ' & '.join(sorted(x.split(';'))) if pd.isna(x) == False else x)

    dang_int = (intersect_df
                 .groupby(['borough','intersection'])['accident_date']
                 .count()
                 .reset_index()
                 .sort_values('accident_date', ascending=False)
                 .rename(columns={'accident_date':'Number of Bike Accidents'})
                )



    # For the table
    dang_int_viz = (dang_int[dang_int['Number of Bike Accidents'] >= 10]
                .copy()
                .reset_index(drop=True)
                .rename(columns={'borough':'Borough','intersection':'Intersection'})
               )

    for i in dang_int_viz.index:
        Crash(dang_int_viz.iloc[i].Borough,
              dang_int_viz.iloc[i].Intersection).create_map().save('app/static/crash_maps/'+
                                                                   dang_int_viz.iloc[i].Borough+
                                                                   dang_int_viz.iloc[i].Intersection.replace(' ','_')+
                                                                   '.html')

    dang_int_viz.Intersection = dang_int_viz.apply(lambda x: '<a href={} target="iframe_map">{}</a>'.format('../static/crash_maps/'+
                                                                                                            x.Borough+x.Intersection.replace(' ','_')+
                                                                                                            '.html',
                                                                                                            x.Intersection), axis=1)

    html = """<table border="1" class="dataframe">
    <thead>
    <tr style="text-align: right;">
    <th>Borough</th>
    <th>Intersection</th>
    <th>Number of Bike Accidents</th>
    </tr>
    </thead>
    <tbody>
    """
    for i in dang_int_viz.index:
        html = (html +
                '<tr><td>'+
                dang_int_viz.iloc[i].Borough+'</td><td>'+
                dang_int_viz.iloc[i].Intersection+'</td><td>'+
                str(dang_int_viz.iloc[i]['Number of Bike Accidents'])+'</td></tr>')
    html = html+"</tbody></table>"
    html = BeautifulSoup(html,"lxml")

    html.body.insert(0,BeautifulSoup('<link rel="stylesheet" href="/static/style.css">',"lxml"))

    with open('app/static/crash_table.html', 'w') as f:
        f.write(str(html))

    lat_lon = intersect_df[['intersection','lat_lon_list']].copy()
    lat_lon.lat_lon_list = lat_lon.lat_lon_list.apply(lambda x: str(round(x[0],5)) + ';' + str(round(x[1],5)))
    lat_lon = lat_lon.drop_duplicates().reset_index(drop=True)
    lat_lon.lat_lon_list = lat_lon.lat_lon_list.apply(lambda x: [float(i) for i in x.split(';')])
    for i in lat_lon.index:
        lat_lon.lat_lon_list[i].reverse()

    dang_int = pd.merge(dang_int, lat_lon,
                        on='intersection', how='left')

    dang_int.to_csv('app/static/dang_int.csv', index=False)

    dang_int_10 = (dang_int[(dang_int['Number of Bike Accidents'] >= 10) &
                           (dang_int['Number of Bike Accidents'] < 15)]
                  .reset_index(drop=True))
    dang_int_15 = (dang_int[(dang_int['Number of Bike Accidents'] >= 15) &
                           (dang_int['Number of Bike Accidents'] < 20)]
                  .reset_index(drop=True))
    dang_int_20 = (dang_int[dang_int['Number of Bike Accidents'] >= 20]
                  .reset_index(drop=True))

    features = [
        {
            'type': 'Feature',
            'geometry': {
                'type': 'MultiPoint',
                'coordinates': list(loc_df.lat_lon_list),
            },
            'properties': {
                'times': list(loc_df.accident_date),
                'icon': 'circle',
                'iconstyle': {
                    'fillColor': 'red',
                    'fillOpacity': 0.5,
                    'stroke': 'false',
                    'radius': 5
                },
                'style': {'weight': 0.5}
            }
        }
    ]




    """
    *********************************************
    Getting the bike lanes and formatting the data
    *********************************************
    """

    bike_lanes = pd.read_json('./app/static/Bicycle Routes.geojson')

    bl_prot_json = []
    bl_stand_json = []
    for i in bike_lanes.index:
        if bike_lanes.iloc[i].features['properties']['facilitycl'] == 'I':
            for j in range(len(bike_lanes.iloc[i].features['geometry']['coordinates'])):
                bl_prot_json.append(bike_lanes.iloc[i].features['geometry']['coordinates'][j])
        else:
            for j in range(len(bike_lanes.iloc[i].features['geometry']['coordinates'])):
                bl_stand_json.append(bike_lanes.iloc[i].features['geometry']['coordinates'][j])

    for i in bl_prot_json:
        for j in i:
            j.reverse()
    for i in bl_stand_json:
        for j in i:
            j.reverse()

    """
    *********************************************
    Creating the map and interactive features
    *********************************************
    """

    nyc_map = folium.Map(location=[40.735,-73.95],zoom_start=11.5, tiles=None)
    folium.TileLayer('cartodbdark_matter',control=False).add_to(nyc_map)

    # Add bike lanes
    folium.PolyLine(bl_prot_json, weight=1, opacity=0.9, color='lime').add_to(folium
                                                         .FeatureGroup(name='Protected Bike Lanes')
                                                         .add_to(nyc_map))

    folium.PolyLine(bl_stand_json, weight=1, opacity=0.9, color='yellow').add_to(folium
                                                         .FeatureGroup(name='Non-Protected Bike Lanes')
                                                         .add_to(nyc_map))

    # Add citibike routes
    folium.PolyLine(gjson, weight=1, opacity=0.2).add_to(folium
                                                         .FeatureGroup(name='Commonly Used Citibike Routes', overlay=False)
                                                         .add_to(nyc_map))

    # Add Dangerous intersections data
    over10 = folium.FeatureGroup(name='Intersections w/10-14 Accidents', overlay=False)
    for i in dang_int_10.index:
        over10.add_child(folium.Marker(dang_int_10.lat_lon_list[i],
                                       tooltip=(dang_int_10.intersection[i] + ':\t' +
                                                str(dang_int_10['Number of Bike Accidents'][i]) +
                                                ' Accidents'
                                               ),
                                       icon=folium.Icon(color='red', prefix='fa', icon='fas fa-bicycle')
                                      )
                           )
    over15 = folium.FeatureGroup(name='Intersections w/15-19 Accidents', overlay=False)
    for i in dang_int_15.index:
        over15.add_child(folium.Marker(dang_int_15.lat_lon_list[i],
                                       tooltip=(dang_int_15.intersection[i] + ':\t' +
                                                str(dang_int_15['Number of Bike Accidents'][i]) +
                                                ' Accidents'
                                               ),
                                       icon=folium.Icon(color='red', prefix='fa', icon='fas fa-bicycle')
                                      )
                           )
    over20 = folium.FeatureGroup(name='Intersections w/20 or More Accidents', overlay=False)
    for i in dang_int_20.index:
        over20.add_child(folium.Marker(dang_int_20.lat_lon_list[i],
                                       tooltip=(dang_int_20.intersection[i] + ':\t' +
                                                str(dang_int_20['Number of Bike Accidents'][i]) +
                                                ' Accidents'
                                               ),
                                       icon=folium.Icon(color='red', prefix='fa',icon='fas fa-bicycle')
                                      )
                           )

    nyc_map.add_child(over10)
    nyc_map.add_child(over15)
    nyc_map.add_child(over20)

    plugins.TimestampedGeoJson(
                {
                    'type': 'FeatureCollection',
                    'features': features
                },
                period='P1M',
                add_last_point=True,
                auto_play=True,
                loop=False,
                max_speed=2,
                loop_button=True,
                date_options='YYYY-MM-DD',
                time_slider_drag_update=True,
                duration='P1M'
            ).add_to(nyc_map)

    folium.LayerControl().add_to(nyc_map)
    nyc_map.save('app/static/map_nyc.html')

    """
    *********************************************
    Bike crash causes
    *********************************************
    """
    # Decided not to use the below for now.  Could use it in the future...

    bike_list = ['BIKE','BICYCLE','E-BIK','BICYCLE','BYCIC']
    cause_df = df[((pd.isna(df.contributing_factor_vehicle_3) == True) &
                   ((df.vehicle_type_code1.isin(bike_list) == True) |
                    (df.vehicle_type_code2.isin(bike_list) == True))
                  )]

    cause_df = cause_df[(cause_df.vehicle_type_code1.isin(bike_list) == False) |
                        (cause_df.vehicle_type_code2.isin(bike_list) == False)]

    def bike_cause(x):
        if x.vehicle_type_code1 in bike_list:
            return x.contributing_factor_vehicle_1
        else:
            return x.contributing_factor_vehicle_2

    def veh_cause(x):
        if x.vehicle_type_code1 not in bike_list:
            return x.contributing_factor_vehicle_1
        else:
            return x.contributing_factor_vehicle_2

    cause_df['bike_cause'] = cause_df.apply(bike_cause, axis=1)
    cause_df['veh_cause'] = cause_df.apply(veh_cause, axis=1)

    # remove Unspecified from dataset. Not useful

    bike_cause_df = (cause_df
                     .groupby('bike_cause')
                     .collision_id.count()
                     .reset_index()
                     .sort_values('collision_id', ascending=False)
                     .head(15)
                     .reset_index(drop=True)
                    )
    bike_cause_df = bike_cause_df[bike_cause_df.bike_cause != 'Unspecified']

    veh_cause_df = (cause_df
                     .groupby('veh_cause')
                     .collision_id.count()
                     .reset_index()
                     .sort_values('collision_id', ascending=False)
                     .head(15)
                     .reset_index(drop=True)
                    )
    veh_cause_df = veh_cause_df[veh_cause_df.veh_cause != 'Unspecified']



if __name__ == "__main__":
    main()
