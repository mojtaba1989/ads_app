import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Template
import base64
from io import BytesIO
import folium
import plotly.graph_objects as go
import numpy as np
import os

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)


class report_Generator:
    def __init__(self, main_dict, gps_dict) -> None:
        pass
        self.main_dict = main_dict
        self.gps = gps_dict

    def create_map(self):
        route = [[lat, lon] for lat, lon in self.gps.values()]
        center = [np.mean([P[0] for P in route]),
                  np.mean([P[1] for P in route])]
        self.map = folium.Map(location=center, zoom_start=18)
        folium.PolyLine(route,
                        color="blue",
                        weight=8,
                        opacity=1,
                        smooth_factor=0).add_to(self.map)
        bound = [[np.min([P[0] for P in route]), np.min([P[1] for P in route])],
                 [np.max([P[0] for P in route]), np.max([P[1] for P in route])]]
        self.map.fit_bounds(bound)

    def create_plots(self):
        self.plot_list = []
        if 'plots' not in self.main_dict.keys():
            return
        for plt in self.main_dict['plots']:
            time = []
            y = []
            for file in self.main_dict['topics'][plt[1]]:
                file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.' + plt[1])
                data = pd.read_csv(file_path)
                if plt[2] in data.columns and 'time' in data.columns:
                    for i in range(len(data)):
                        time.append(data['time'][i])
                        y.append(data[plt[2]][i])
                else:
                    continue
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=time, y=y, mode='lines+markers', name='y = x²'))
            fig.update_layout(title='Interactive Line Plot',
                            xaxis_title='x',
                            yaxis_title='y')

            self.plot_list.append(fig.to_html(full_html=False, include_plotlyjs='cdn'))
            


    def create_html(self):
        with open(os.path.join(dir_path, 'report_template.html'), 'r') as f:
            self.html_template = f.read()

        
    def generate_report(self):
        self.create_html()
        self.create_map()
        self.create_plots()
        html_content = Template(self.html_template).render(
            map_html=self.map._repr_html_(),
            plots = self.plot_list,
            info = self.main_dict['info']

        )

        with open('report.html', 'w') as f:
            f.write(html_content)
