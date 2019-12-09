import pandas as pd
import folium
from bs4 import BeautifulSoup

dang_int = pd.read_csv('app/static/dang_int.csv')
dang_int.lat_lon_list = dang_int.lat_lon_list.apply(lambda x: [float(x.split(', ')[0][1:]),
                                                               float(x.split(', ')[1][:-1])])


def initialize_map(coordinates):
    nyc_map = folium.Map(location=coordinates,zoom_start=16, tiles=None)
    folium.TileLayer('cartodbdark_matter',control=False).add_to(nyc_map)
    return nyc_map


class Crash:
    def __init__(self, borough, intersection):
        self.borough = borough
        self.intersection = intersection
        self.df = dang_int[(dang_int['intersection'] == self.intersection) &
                     (dang_int['borough'] == self.borough)
                    ].reset_index(drop=True)


    def create_map(self):
        m = initialize_map(self.df.iloc[0].lat_lon_list)
        for i in self.df.index:
            folium.Marker(self.df.iloc[i].lat_lon_list,
                          tooltip=(self.df.intersection[i] + ':\t' +
                                   str(self.df['Number of Bike Accidents'][i]) +
                                   ' Accidents'
                                  ),
                          icon=folium.Icon(color='red', prefix='fa', icon='fas fa-bicycle')
                          ).add_to(m)
        return m
