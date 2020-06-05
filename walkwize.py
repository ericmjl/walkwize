import streamlit as st
import pydeck as pdk
import pandas as pd
import networkx as nx
import osmnx as ox
import numpy as np
import scipy

sca

def get_node_df(location):
	#Inputs: location as tuple of coords (lat, lon)
	#Returns: 1-line dataframe to display an icon at that location on a map

	#Location of Map Marker icon
	icon_data = {
		"url": "https://img.icons8.com/plasticine/100/000000/marker.png",
		"width": 128,
		"height":128,
		"anchorY": 128}

	return pd.DataFrame({'lat':[location[0]], 'lon':[location[1]], 'icon_data': [icon_data]})

def get_text_df(text, location):
	#Inputs: text to display and location as tuple of coords (lat, lon)
	#Returns: 1-line dataframe to display text at that location on a map
	return pd.DataFrame({'lat':[location[0]], 'lon':[location[1]], 'text':text})

############################################################################

def make_iconlayer(df):
	# #Inputs: df with [lat, lon, icon_data]
	# #Returns: pydeck IconLayer
	# return pdk.Layer(
	#     type='IconLayer',
	#     data=df,
	#     get_icon='icon_data',
	#     get_size=4,
	#     pickable=True,
	#     size_scale=15,
	#     get_position='[lon, lat]')
	return

def make_textlayer(df, color_array):
	#Inputs: df with [lat, lon, text] and font color as str([R,G,B]) - yes '[R,G,B]'
	#Returns: pydeck TextLayer
	return pdk.Layer(
	    type='TextLayer',
	    data=df,
	    get_text='text',
	    get_size=4,
	    pickable=True,
	    size_scale=6,
	    getColor = color_array,
	    get_position='[lon, lat]')

def make_linelayer(df, color_array):
	#Inputs: df with [startlat, startlon, destlat, destlon] and font color as str([R,G,B]) - yes '[R,G,B]'
	#Plots lines between each line's [startlon, startlat] and [destlon, destlat]
	#Returns: pydeck LineLayer
	return pdk.Layer(
	    type='LineLayer',
	    data=df,
	    getSourcePosition = '[startlon, startlat]',
	    getTargetPosition = '[destlon, destlat]',
	    getColor = color_array,
	    getWidth = '5')


def make_pedlayer(df, color_array):

	return pdk.Layer(
		"HeatmapLayer",
		data=df,
		opacity=0.3,
		#get_position=["centroid_y", "centroid_x"],
		get_position=["longitude", "latitude"],
		aggregation="mean",
		get_weight="total_of_directions")
		#get_weight="ped_rate")



############################################################################

@st.cache(suppress_st_warning=True, allow_output_mutation=True, show_spinner=False)
def get_map_data():
	#Returns: map as graph from graphml
	#Cached by Streamlit
	G = ox.graph_from_bbox(-37.8061,-37.8200,144.9769, 144.9569, network_type='walk')

	gdf_nodes, gdf_edges = ox.utils_graph.graph_to_gdfs(G, nodes=True, edges=True, node_geometry=True, fill_edge_geometry=True)
	gdf_edges['centroid_x'] = gdf_edges.apply(lambda r: r.geometry.centroid.x, axis=1)
	gdf_edges['centroid_y'] = gdf_edges.apply(lambda r: r.geometry.centroid.y, axis=1)

	ped_stations = pd.read_json("https://data.melbourne.vic.gov.au/resource/h57g-5234.json")
	ped_stations.set_index("sensor_id",inplace=True)

	ped_current = pd.read_json("https://data.melbourne.vic.gov.au/resource/d6mv-s43h.json")
	ped_current = ped_current.groupby('sensor_id')['total_of_directions'].sum().to_frame()
	ped_current = ped_current.join(ped_stations[['latitude','longitude']])


	gdf_edges['ped_rate'] = scipy.interpolate.griddata(np.array(tuple(zip(ped_current['latitude'], ped_current['longitude']))),np.array(ped_current['total_of_directions']),np.array(tuple(zip(gdf_edges['centroid_y'], gdf_edges['centroid_x']))), method='linear',rescale=False,fill_value=0)

	return G, gdf_nodes, gdf_edges, ped_current, ped_stations



############################################################################

def get_map_bounds(gdf_nodes, route1, route2):
	#Inputs: node df, and two lists of nodes along path
	#Returns: Coordinates of smallest rectangle that contains all nodes
	max_x = -1000
	min_x = 1000
	max_y = -1000
	min_y = 1000

	for i in (route1 + route2):
		row = gdf_nodes.loc[i]
		temp_x = row['x']
		temp_y = row['y']

		max_x = max(temp_x, max_x)
		min_x = min(temp_x, min_x)
		max_y = max(temp_y, max_y)
		min_y = min(temp_y, min_y)

	return min_x, max_x, min_y, max_y

def nodes_to_lats_lons(nodes, path_nodes):
	#Inputs: node df, and list of nodes along path
	#Returns: 4 lists of source and destination lats/lons for each step of that path for LineLayer
	#S-lon1,S-lat1 -> S-lon2,S-lat2; S-lon2,S-lat2 -> S-lon3,S-lat3...
	source_lats = []
	source_lons = []
	dest_lats = []
	dest_lons = []

	for i in range(0,len(path_nodes)-1):
		source_lats.append(nodes.loc[path_nodes[i]]['y'])
		source_lons.append(nodes.loc[path_nodes[i]]['x'])
		dest_lats.append(nodes.loc[path_nodes[i+1]]['y'])
		dest_lons.append(nodes.loc[path_nodes[i+1]]['x'])

	return (source_lats, source_lons, dest_lats, dest_lons)



############################################################################

def source_to_dest(G, gdf_nodes, gdf_edges, s, e):
	#Inputs: Graph, nodes, edges, source, end, distance to walk, pace = speed, w2 bool = avoid busy roads

	if s == '':
		#No address, default to Insight
		st.write('Source address not found, defaulting...')
		s = '440 Elizabeth St, Melbourne VIC 3000, Australia'
		start_location = ox.utils_geo.geocode(s)
	else:
		try:
			start_location = ox.utils_geo.geocode(s + ' Melbourne, Australia')
		except:
			#No address found, default to Insight
			st.write('Source address not found, defaulting...')
			s = '440 Elizabeth St, Melbourne VIC 3000, Australia'
			start_location = ox.utils_geo.geocode(s)

	if e == '':
		#No address, default to Fenway Park
		st.write('Destination address not found, defaulting...')
		e = '1 Spring St, Melbourne VIC 3000, Australia'
		end_location = ox.utils_geo.geocode(e)
	else:
		try:
			end_location = ox.utils_geo.geocode(e + ' Melbourne, Australia')
		except:
			#No address found, default to Insight
			st.write('Destination address not found, defaulting...')
			e = '1 Spring St, Melbourne VIC 3000, Australia'
			end_location = ox.utils_geo.geocode(e)

	#Get coordinates from addresses
	start_coords = (start_location[0], start_location[1])
	end_coords = (end_location[0], end_location[1])

	#Snap addresses to graph nodes
	start_node = ox.get_nearest_node(G, start_coords)
	end_node = ox.get_nearest_node(G, end_coords)

	lengths = {}
	ped_rates = {}
	factor = 1
	for row in gdf_edges.itertuples():
		u = getattr(row,'u')
		v = getattr(row,'v')
		key = getattr(row, 'key')
		length = getattr(row, 'length')
		ped_rate = getattr(row, 'ped_rate')
		lengths[(u,v,key)] = length
		ped_rates[(u,v,key)] = ped_rate

	optimized = {}
	for key in lengths.keys():
		#temp = int(lengths[key])
		temp = (int(lengths[key])*(int(ped_rates[key]+1)))
		optimized[key] = temp





	#Generate new edge attribute
	nx.set_edge_attributes(G, optimized, 'optimized')

	#Path of nodes
	optimized_route = nx.shortest_path(G, start_node, end_node, weight = 'optimized')


	shortest_route = nx.shortest_path(G, start_node, end_node, weight = 'length')
	short_start_lat, short_start_lon, short_dest_lat, short_dest_lon = nodes_to_lats_lons(gdf_nodes, shortest_route)
	short_df = pd.DataFrame({'startlat':short_start_lat, 'startlon':short_start_lon, 'destlat': short_dest_lat, 'destlon':short_dest_lon})
	short_layer = make_linelayer(short_df, '[160,160,160]')

	#This finds the bounds of the final map to show based on the paths
	min_x, max_x, min_y, max_y = get_map_bounds(gdf_nodes, shortest_route, optimized_route)

	#These are lists of origin/destination coords of the paths that the routes take
	opt_start_lat, opt_start_lon, opt_dest_lat, opt_dest_lon = nodes_to_lats_lons(gdf_nodes, optimized_route)


	#Move coordinates into dfs
	opt_df = pd.DataFrame({'startlat':opt_start_lat, 'startlon':opt_start_lon, 'destlat': opt_dest_lat, 'destlon':opt_dest_lon})

	COLOR_BREWER_RED = [[255,247,236],[254,232,200],
		[253,212,158],[253,187,132],
		[252,141,89],[239,101,72],
		[215,48,31],[179,0,0],[127,0,0]]

	start_node_df = get_node_df(start_location)
	icon_layer = make_iconlayer(start_node_df)
	optimized_layer = make_linelayer(opt_df, '[0,0,179]')
	ped_layer = make_pedlayer(ped_current,COLOR_BREWER_RED)
	#ped_layer = make_pedlayer(gdf_edges[['centroid_x','centroid_y','ped_rate']],COLOR_BREWER_RED)


	# type(gdf_edges)
	# type(ped_current)
	#
	# gdf_edges
	st.pydeck_chart(pdk.Deck(
		map_style="mapbox://styles/mapbox/light-v9",
		initial_view_state=pdk.ViewState(latitude = -37.81375, longitude = 144.9669, zoom=13.5),
		layers=[short_layer, optimized_layer, ped_layer]))


	st.write('The shortest past is shown in grey. The blue path will avoid people.')
	return







############################################################################

G, gdf_nodes, gdf_edges, ped_current, ped_stations = get_map_data()


st.title("WalkWize")
st.header("*Take the path least traveled.*")
st.markdown("Let's plan your walk.")

input1 = st.text_input('Where do you want to start?')
input2 = st.text_input('And where will you end?')

COLOR_BREWER_RED = [[255,247,236],[254,232,200],[253,212,158],[253,187,132],[252,141,89],[239,101,72],[215,48,31],[179,0,0],[127,0,0]]

ped_layer = make_pedlayer(ped_current,COLOR_BREWER_RED)


submit = st.button('Find route', key=1)
if not submit:
	st.pydeck_chart(pdk.Deck(
		map_style="mapbox://styles/mapbox/light-v9",
		initial_view_state=pdk.ViewState(latitude = -37.81375, longitude = 144.9669, zoom=13.5),
		layers=[ped_layer]))
else:
	with st.spinner('Routing...'):
		source_to_dest(G, gdf_nodes, gdf_edges, input1, input2)
