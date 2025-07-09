import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Template
import base64
from io import BytesIO
import folium
import plotly.graph_objects as go
import numpy as np
import os

from PyQt5.QtWidgets import QApplication, QFileDialog


file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)

def get_closest(key, dict):
        try:
            return key, dict[key]
        except:
            key_n = min(dict.keys(), key=lambda x: abs(int(x) - int(key)))
            return key_n, dict[key_n]

folium_icon_colors = [
    'red',
    'blue',         # default
    'green',
    'purple',
    'orange',
    'darkred',
    'lightred',
    'beige',
    'darkblue',
    'darkgreen',
    'cadetblue',
    'darkpurple',
    'white',
    'pink',
    'lightblue',
    'lightgreen',
    'gray',
    'black',
    'lightgray'
]

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
        
        self.scen_list = [self.main_dict['scenarios'][key][1] for key in self.main_dict['scenarios']]
        self.scen_list = np.unique(self.scen_list)
        self.scen_dict = {}
        for id, sc in enumerate(self.scen_list):
            self.scen_dict[sc] = {'color': folium_icon_colors[id], 'locs': [],
                             'mrk_grp': folium.FeatureGroup(name=sc, show=True)}
        
        for key in self.main_dict['scenarios'].keys():
            loc = get_closest(int(key), self.gps)[1]
            self.scen_dict[self.main_dict['scenarios'][key][1]]['locs'].append(loc)
        
        for key in self.scen_dict.keys():
            for loc in self.scen_dict[key]['locs']:
                folium.Marker(loc,
                               popup=key, 
                               icon=folium.Icon(color=self.scen_dict[key]['color'])
                               ).add_to(self.scen_dict[key]['mrk_grp'])
            self.scen_dict[key]['mrk_grp'].add_to(self.map)
        folium.LayerControl(collapsed=False).add_to(self.map)

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
            fig.update_layout(xaxis_title='time (s)',
                            yaxis_title=plt[2])

            self.plot_list.append(fig.to_html(full_html=False, include_plotlyjs='cdn'))
            
    def create_html(self):
        with open(os.path.join(dir_path, 'report_template.html'), 'r') as f:
            self.html_template = f.read()

    def create_piechart(self):
        fig, ax = plt.subplots()
        sizes = [len(self.scen_dict[key]['locs']) for key in self.scen_dict.keys()]
        labels = [key for key in self.scen_dict.keys()]
        colors = [self.scen_dict[key]['color'] for key in self.scen_dict.keys()]
        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax.axis('equal') 

        # Save to base64 string
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()

        # HTML-safe image
        self.pie_data = f"data:image/png;base64,{encoded}"

    def create_vehicle_dynamics(self):
        self.vehicle_dynamics = {}
        if "ssc_velocity" in self.main_dict['topics'].keys():
            time = []
            speed = []
            for file in self.main_dict['topics']['ssc_velocity']:
                file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.' + 'ssc_velocity')
                data = pd.read_csv(file_path)
                if 'velocity' in data.columns and 'time' in data.columns:
                    for i in range(len(data)):
                        time.append(data['time'][i])
                        speed.append(data['velocity'][i])
                else:
                    continue
            speed = np.array(speed)
            time = np.array(time)
            threshold = 0.3
            stopped = speed < threshold
            stop_segments = np.diff(stopped.astype(int)) == 1
            num_full_stops = np.sum(stop_segments)

            # self.vehicle_dynamics['Average Speed m/s'] = f"{np.mean(speed[speed>0]):.f}"
            # self.vehicle_dynamics['Average Speed kph'] = f"{np.mean(speed[speed>0])*3.6:.f}"
            self.vehicle_dynamics['Average Speed (mph)'] = f"{np.mean(speed[speed>0])*2.23694:.01f}"
            self.vehicle_dynamics['Maximum Speed (mph)'] = f"{np.max(speed)*2.23694:.01f}"
            self.vehicle_dynamics['Number of full stops'] = f"{num_full_stops}"
        else:
            self.vehicle_dynamics['Average Speed (mph)'] = f"not available"
            self.vehicle_dynamics['Maximum Speed (mph)'] = f"not available"
            self.vehicle_dynamics['Number of full stops'] = f"not available"

        if "ssc_velocity" in self.main_dict['topics'].keys():
            time = []
            accel = []
            for file in self.main_dict['topics']['ssc_velocity']:
                file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.' + 'ssc_velocity')
                data = pd.read_csv(file_path)
                if 'acceleration' in data.columns and 'time' in data.columns:
                    for i in range(len(data)):
                        time.append(data['time'][i])
                        accel.append(data['acceleration'][i])
                else:
                    continue

            accel = np.array(accel)
            time = np.array(time)
            self.vehicle_dynamics['Maximum Acceleration (m/s/s)'] = f"{np.max(accel):.01f}"
            self.vehicle_dynamics['Maximum Decceleration (m/s/s)'] = f"{np.min(accel):.01f}"
        else:
            self.vehicle_dynamics['Maximum Acceleration (m/s/s)'] = f"not available"
            self.vehicle_dynamics['Maximum Decceleration (m/s/s)'] = f"not available"

        if "vehi_steering_report" in self.main_dict['topics'].keys():
            time = []
            vs = []
            for file in self.main_dict['topics']['vehi_steering_report']:
                file_path = os.path.join(self.main_dict['pwd'], 'csv', file + '.' + 'vehi_steering_report')
                data = pd.read_csv(file_path)
                if 'steering_wheel_angle' in data.columns and 'time' in data.columns:
                    for i in range(len(data)):
                        time.append(data['time'][i])
                        vs.append(data['steering_wheel_angle'][i])
                else:
                    continue
            vs = np.array(vs)
            time = np.array(time)/1E9

            steering_rate = np.diff(vs) / np.diff(time)
            self.vehicle_dynamics['Maximum Steering Rate (rad/s)'] = f"{np.max(np.abs(steering_rate)):.01f}"
        else:
            self.vehicle_dynamics['Maximum Steering Rate (rad/s)'] = f"not available"
       
    def generate_report(self):
        self.create_html()
        self.create_map()
        self.create_plots()
        self.create_piechart()
        self.create_vehicle_dynamics()

        html_content = Template(self.html_template).render(
            map_html=self.map._repr_html_(),
            plots = self.plot_list,
            info = self.main_dict['info'],
            pie_data = self.pie_data,
            vehicle_dynamics = self.vehicle_dynamics
        )

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save Report",
            "report.html",  # default file name
            "HTML Files (*.html);;All Files (*)"
        )

        if file_path:
            print("File will be saved to:", file_path)
            with open(file_path, 'w') as f:
                f.write(html_content)
        else:
            pass
